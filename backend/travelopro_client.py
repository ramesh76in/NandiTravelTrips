"""Travelopro Flight API client.

Implements the documented Travelopro Availability and Revalidate workflow.
Credentials are read from environment variables and are never hard-coded.
"""
import json
import logging
import os
from pathlib import Path
import time
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

import requests

from .flights_data import get_airport_by_code
from .schemas import FlightItem, FlightSegment

# Dedicated provider log. Keep this independent from Django so it also works when
# the client is imported by the FastAPI service.
_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("travelopro.api")
logger.setLevel(logging.INFO)
logger.propagate = False
if not any(isinstance(h, logging.FileHandler) and Path(getattr(h, "baseFilename", "")).name == "travelopro_api.log" for h in logger.handlers):
    _handler = logging.FileHandler(_LOG_DIR / "travelopro_api.log", encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logger.addHandler(_handler)

AIRLINE_NAMES = {
    "6E": "IndiGo", "AI": "Air India", "UK": "Vistara", "SG": "SpiceJet",
    "QP": "Akasa Air", "G8": "Go First", "I5": "AirAsia India", "IX": "Air India Express",
    "EK": "Emirates", "SQ": "Singapore Airlines", "BA": "British Airways",
    "QR": "Qatar Airways", "LH": "Lufthansa", "EY": "Etihad Airways", "AF": "Air France",
    "KL": "KLM", "AA": "American Airlines", "UA": "United Airlines", "DL": "Delta Air Lines",
}


def parse_duration_string(duration_val: Any) -> Tuple[str, int]:
    if duration_val is None or str(duration_val).strip() == "":
        return "0h", 0
    value = str(duration_val).strip()
    if value.isdigit():
        total = int(value)
    elif ":" in value and not value.startswith("PT"):
        parts = value.split(":")
        total = int(parts[0]) * 60 + int(parts[1]) if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit() else 0
    else:
        h = re.search(r"(\d+)H", value.upper())
        m = re.search(r"(\d+)M", value.upper())
        total = (int(h.group(1)) if h else 0) * 60 + (int(m.group(1)) if m else 0)
    return f"{total // 60}h {total % 60}m" if total % 60 else f"{total // 60}h", total


def _load_env_if_present() -> None:
    """Small local .env loader so the existing project remains dependency-light."""
    env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.exists(env_file):
        return
    with open(env_file, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if "#" in value and not (value.startswith("'") or value.startswith('"')):
                value = value.split("#", 1)[0].strip()
            value = value.strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


def _amount(value: Any) -> float:
    if isinstance(value, dict):
        value = value.get("Amount") or value.get("amount") or value.get("value") or 0
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _first(mapping: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


class TraveloproClient:
    """Client for the documented Travelopro AeroVE5 API.

    Uses a shared HTTP session so repeated searches can reuse TCP/TLS
    connections. The provider remains the source of truth for live fares.
    """

    _http_session = requests.Session()
    _http_session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})
    _ip_cache = None
    _ip_cache_until = 0.0
    _ip_lock = threading.Lock()

    def __init__(self, env: Optional[str] = None):
        _load_env_if_present()
        self.env = (env or os.environ.get("TRAVELOPRO_ENV", "test")).strip().lower()
        self.user_id = os.environ.get("TRAVELOPRO_USER_ID", "").strip()
        self.user_password = os.environ.get("TRAVELOPRO_USER_PASSWORD", "").strip()
        self.access = os.environ.get("TRAVELOPRO_ACCESS", "Test").strip() or "Test"
        self.ip_mode = os.environ.get("TRAVELOPRO_IP_MODE", "manual").strip().lower() or "manual"
        self.ip_address = os.environ.get("TRAVELOPRO_IP_ADDRESS", "").strip()
        self.base_url = os.environ.get(
            "TRAVELOPRO_BASE_URL", "https://travelnext.works/api/aeroVE5"
        ).rstrip("/")
        self.timeout = int(os.environ.get("TRAVELOPRO_TIMEOUT", "30"))

    @property
    def is_configured(self) -> bool:
        return bool(self.user_id and self.user_password and self.access and (self.ip_mode == "auto" or self.ip_address))

    def configuration_status(self) -> Dict[str, Any]:
        return {
            "configured": self.is_configured,
            "environment": self.env,
            "access": self.access,
            "base_url": self.base_url,
            "has_user_id": bool(self.user_id),
            "has_user_password": bool(self.user_password),
            "ip_mode": self.ip_mode,
            "has_ip_address": "auto" if self.ip_mode == "auto" else bool(self.ip_address),
        }

    def _resolve_ip_address(self) -> str:
        if self.ip_mode != "auto":
            if not self.ip_address:
                raise RuntimeError("Travelopro IP address is not configured")
            return self.ip_address
        now = time.monotonic()
        with self._ip_lock:
            if self._ip_cache and now < self._ip_cache_until:
                self.ip_address = self._ip_cache
                return self.ip_address
            try:
                response = self._http_session.get(
                    "https://api.ipify.org",
                    params={"format": "json"},
                    headers={"Accept": "application/json"},
                    timeout=min(self.timeout, 10),
                )
                response.raise_for_status()
                discovered = str(response.json().get("ip") or "").strip()
                if not discovered:
                    raise ValueError("No public IP returned")
                self._ip_cache = discovered
                self._ip_cache_until = now + 600
                self.ip_address = discovered
                logger.info("TRAVELOPRO AUTO IP | public_ip=%s | cache_seconds=600", discovered)
                return discovered
            except (requests.RequestException, ValueError, TypeError) as exc:
                logger.exception("TRAVELOPRO AUTO IP FAILED | error=%s", exc)
                raise RuntimeError(
                    "Unable to discover the current public IP. Check internet access or use manual IP mode."
                ) from exc

    def _auth_payload(self) -> Dict[str, str]:
        return {
            "user_id": self.user_id,
            "user_password": self.user_password,
            "access": self.access,
            "ip_address": self._resolve_ip_address(),
        }

    @staticmethod
    def _redact(value: Any) -> Any:
        sensitive = {"user_password", "password", "api_key", "api_secret", "authorization", "token"}
        if isinstance(value, dict):
            return {k: ("***REDACTED***" if k.lower() in sensitive else TraveloproClient._redact(v)) for k, v in value.items()}
        if isinstance(value, list):
            return [TraveloproClient._redact(v) for v in value]
        return value

    def _post(self, path: str, payload: Dict[str, Any], correlation_id: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        safe_payload = self._redact(payload)
        started = time.perf_counter()
        logger.info("TRAVELOPRO REQUEST | correlation_id=%s | method=POST | url=%s | payload=%s", correlation_id or "-", url, json.dumps(safe_payload, default=str, separators=(",", ":")))
        try:
            response = self._http_session.post(url, json=payload, timeout=self.timeout)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            logger.info("TRAVELOPRO RESPONSE | correlation_id=%s | path=%s | status=%s | elapsed_ms=%s | bytes=%s", correlation_id or "-", path, response.status_code, elapsed_ms, len(response.content))
            if response.status_code >= 400:
                logger.warning("TRAVELOPRO RESPONSE BODY | path=%s | body=%s", path, response.text[:5000])
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            body = response.text[:5000] if "response" in locals() else ""
            logger.exception("TRAVELOPRO HTTP ERROR | path=%s | status=%s | body=%s", path, getattr(response, "status_code", "unknown"), body)
            raise RuntimeError(f"Travelopro {path} returned HTTP {response.status_code}: {body}") from exc
        except requests.RequestException as exc:
            logger.exception("TRAVELOPRO CONNECTION ERROR | path=%s | error=%s", path, exc)
            raise RuntimeError(f"Unable to connect to Travelopro {path}: {exc}") from exc
        except ValueError as exc:
            logger.exception("TRAVELOPRO INVALID JSON | path=%s | error=%s", path, exc)
            raise RuntimeError(f"Travelopro {path} returned invalid JSON") from exc

    def _journey_type(self, return_date: Optional[str], trip_type: Optional[str]) -> str:
        # Explicit UI trip_type always wins. The search form can retain a return
        # date even when the user switches back to OneWay, so never infer Return
        # from return_date when trip_type explicitly says ONEWAY.
        raw = (trip_type or "").strip().upper().replace("-", "_")
        if raw in ("MULTICITY", "MULTI_CITY", "CIRCLE"):
            return "Circle"
        if raw in ("ONEWAY", "ONE_WAY"):
            return "OneWay"
        if raw in ("ROUNDTRIP", "ROUND_TRIP", "RETURN", "ROUND"):
            return "Return"
        # Backward-compatible inference only when trip_type is missing/unknown.
        return "Return" if return_date else "OneWay"

    def _class_name(self, travel_class: str) -> str:
        return {
            "ECONOMY": "Economy",
            "PREMIUM_ECONOMY": "PremiumEconomy",
            "PREMIUMECONOMY": "PremiumEconomy",
            "BUSINESS": "Business",
            "FIRST": "First",
        }.get((travel_class or "ECONOMY").upper(), "Economy")

    def search_flights(
        self,
        origin_code: str,
        destination_code: str,
        departure_date: str,
        return_date: Optional[str] = None,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        travel_class: str = "ECONOMY",
        non_stop: bool = False,
        currency: str = "INR",
        max_results: int = 50,
        trip_type: Optional[str] = None,
        airline_code: Optional[str] = None,
        fare_type: str = "Regular",
        correlation_id: Optional[str] = None,
    ) -> Optional[List[FlightItem]]:
        if not self.is_configured:
            logger.warning("Travelopro is not configured: missing required credentials/IP")
            return None

        journey_type = self._journey_type(return_date, trip_type)
        od_info: List[Dict[str, Any]] = [{
            "departureDate": departure_date,
            "airportOriginCode": origin_code.upper().strip(),
            "airportDestinationCode": destination_code.upper().strip(),
        }]
        if journey_type == "Return":
            od_info[0]["returnDate"] = return_date

        payload: Dict[str, Any] = {
            **self._auth_payload(),
            "requiredCurrency": currency.upper(),
            "journeyType": journey_type,
            "OriginDestinationInfo": od_info,
            "class": self._class_name(travel_class),
            "adults": max(1, adults),
            "childs": max(0, children),
            "infants": max(0, infants),
        }
        payload["directFlight"] = 1 if non_stop else 0
        payload["multipleBrandedFares"] = os.environ.get("TRAVELOPRO_MULTIPLE_BRANDED_FARES", "true").strip().lower() in ("1", "true", "yes", "on")
        fare_type_map = {"regular": 1, "student": 2, "armed force": 3, "armed forces": 3, "senior citizen": 4}
        payload["fareType"] = fare_type_map.get(str(fare_type or "Regular").strip().lower(), 1)
        if airline_code:
            payload["airlineCode"] = airline_code.upper().strip()
        # The documented availability request does not expose directFlight in the excerpt we have.
        # Therefore we don't send the old, undocumented boolean field.

        provider_started = time.perf_counter()
        data = self._post("availability", payload, correlation_id=correlation_id)
        provider_elapsed_ms = round((time.perf_counter() - provider_started) * 1000, 1)
        parse_started = time.perf_counter()
        flights = self.parse_availability_response(data, travel_class=travel_class, max_results=max_results)
        parse_elapsed_ms = round((time.perf_counter() - parse_started) * 1000, 1)
        logger.info(
            "TRAVELOPRO AVAILABILITY PIPELINE | correlation_id=%s | provider_ms=%s | parse_ms=%s | flights=%s",
            correlation_id or "-", provider_elapsed_ms, parse_elapsed_ms, len(flights)
        )
        if non_stop:
            flights = [flight for flight in flights if flight.stops == 0]
        return flights[:max_results]

    def revalidate(
        self,
        session_id: str,
        fare_source_code: str,
        fare_source_code_inbound: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.is_configured:
            raise RuntimeError("Travelopro is not configured")
        payload: Dict[str, Any] = {
            "session_id": session_id,
            "fare_source_code": fare_source_code,
        }
        if fare_source_code_inbound:
            payload["fare_source_code_inbound"] = fare_source_code_inbound
        return self._post("revalidate", payload)

    def get_fare_rules(self, session_id: str, fare_source_code: str) -> Dict[str, Any]:
        """Fare-rule endpoint is not assumed here until the supplied booking docs define it."""
        raise NotImplementedError(
            "Use the documented Travelopro fare-rules endpoint once its request schema is enabled."
        )

    def create_booking(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Intentionally disabled until the exact supplied booking request schema is wired."""
        raise NotImplementedError(
            "Travelopro booking is not yet enabled. Complete Availability + Revalidate testing first."
        )

    def parse_availability_response(self, data: Dict[str, Any], travel_class: str = "ECONOMY", max_results: int = 50) -> List[FlightItem]:
        response = data.get("AirSearchResponse") or data.get("airSearchResponse") or data
        session_id = response.get("session_id") or response.get("SessionId") or response.get("SessionID") or ""
        result = response.get("AirSearchResult") or response.get("airSearchResult") or {}
        fare_itineraries = result.get("FareItineraries") or result.get("fareItineraries") or []

        flights: List[FlightItem] = []
        for index, wrapper in enumerate(_as_list(fare_itineraries)):
            if len(flights) >= max_results:
                break
            fare_itinerary = wrapper.get("FareItinerary") or wrapper.get("fareItinerary") or wrapper
            if not isinstance(fare_itinerary, dict):
                continue

            origin_dest_options = _as_list(fare_itinerary.get("OriginDestinationOptions"))
            segments: List[FlightSegment] = []
            stop_cities: List[str] = []
            total_stops = 0

            for od in origin_dest_options:
                if not isinstance(od, dict):
                    continue
                total_stops += int(od.get("TotalStops") or 0)
                for seg_wrapper in _as_list(od.get("OriginDestinationOption")):
                    seg = seg_wrapper.get("FlightSegment") if isinstance(seg_wrapper, dict) else None
                    if not isinstance(seg, dict):
                        continue
                    origin = str(_first(seg, "DepartureAirportLocationCode", "departureAirportLocationCode", default=""))
                    destination = str(_first(seg, "ArrivalAirportLocationCode", "arrivalAirportLocationCode", default=""))
                    airline_code = str(_first(seg, "MarketingAirlineCode", "marketingAirlineCode", default=""))
                    airline_name = str(_first(seg, "MarketingAirlineName", "marketingAirlineName", default="") or AIRLINE_NAMES.get(airline_code, airline_code))
                    operating = seg.get("OperatingAirline") or {}
                    equipment = str(_first(operating, "Equipment", "equipment", default="") or "")
                    duration_text, duration_minutes = parse_duration_string(_first(seg, "JourneyDuration", "journeyDuration", default=0))
                    segments.append(FlightSegment(
                        airline=airline_name,
                        airline_code=airline_code,
                        flight_number=str(_first(seg, "FlightNumber", "flightNumber", default="")),
                        origin=origin,
                        origin_city=self._city(origin),
                        destination=destination,
                        destination_city=self._city(destination),
                        departure_time=str(_first(seg, "DepartureDateTime", "departureDateTime", default="")),
                        arrival_time=str(_first(seg, "ArrivalDateTime", "arrivalDateTime", default="")),
                        duration=duration_text,
                        duration_minutes=duration_minutes,
                        aircraft=equipment or "",
                    ))

            if not segments:
                continue

            # Stops are also represented on each OriginDestinationOption.
            if total_stops == 0 and len(segments) > 1:
                total_stops = max(0, len(segments) - 1)
            if total_stops > 0:
                stop_cities = [s.origin_city for s in segments[1:]]

            branded = _as_list(fare_itinerary.get("BrandedFares"))
            # Standard responses can put AirItineraryFareInfo directly on FareItinerary.
            if not branded and fare_itinerary.get("AirItineraryFareInfo"):
                branded = [{"AirItineraryFareInfo": fare_itinerary["AirItineraryFareInfo"]}]
            if not branded:
                branded = [{}]

            for fare_index, brand in enumerate(branded):
                fare_info = brand.get("AirItineraryFareInfo") or {}
                totals = fare_info.get("ItinTotalFares") or {}
                base = _amount(totals.get("BaseFare"))
                tax = _amount(totals.get("TotalTax"))
                total = _amount(totals.get("TotalFare"))
                if total <= 0:
                    total = base + tax

                fare_breakdown = _as_list(fare_info.get("FareBreakdown"))
                baggage_checkin, baggage_cabin = self._baggage(fare_breakdown)
                fare_class_details = brand.get("FareClassDetails") or []
                class_detail = self._fare_class_detail(fare_class_details)
                seats = self._seats(class_detail)
                refundable = str(fare_info.get("IsRefundable", "")).lower() in ("true", "yes", "1")
                fare_source_code = str(fare_info.get("FareSourceCode") or "")
                fare_source_code_inbound = str(fare_info.get("FareSourceCodeInbound") or "") or None

                first = segments[0]
                last = segments[-1]
                item_id = f"TP_{session_id}_{index}_{fare_index}"
                flight = FlightItem(
                    id=item_id,
                    airline=first.airline,
                    airline_code=first.airline_code,
                    flight_number=first.flight_number,
                    origin=first.origin,
                    origin_city=first.origin_city,
                    destination=last.destination,
                    destination_city=last.destination_city,
                    departure_time=first.departure_time,
                    arrival_time=last.arrival_time,
                    duration=self._total_duration(segments),
                    duration_minutes=sum(s.duration_minutes for s in segments),
                    stops=total_stops,
                    stop_cities=stop_cities,
                    travel_class=travel_class,
                    seats_available=seats,
                    refundable=refundable,
                    baggage_cabin=baggage_cabin or "Not specified",
                    baggage_checkin=baggage_checkin or "Not specified",
                    base_price=base,
                    taxes=tax,
                    final_price=total,
                    segments=segments,
                    provider="travelopro",
                    session_id=session_id,
                    fare_source_code=fare_source_code,
                    fare_source_code_inbound=fare_source_code_inbound,
                    validating_airline_code=str(fare_itinerary.get("ValidatingAirlineCode") or ""),
                    ticket_type=str(fare_itinerary.get("TicketType") or ""),
                    passport_mandatory=bool(fare_itinerary.get("IsPassportMandatory")) if fare_itinerary.get("IsPassportMandatory") is not None else False,
                    required_fields_to_book=_as_list(fare_info.get("RequiredFieldsToBook") or fare_itinerary.get("RequiredFieldsToBook")),
                    fare_type=str(fare_info.get("FareType") or ""),
                    res_book_desig_code=str(class_detail.get("ResBookDesigCode") or ""),
                    cabin_class_code=str(class_detail.get("CabinClassCode") or ""),
                    cabin_class_text=str(class_detail.get("CabinClassText") or ""),
                )
                flights.append(flight)

        return flights

    def _city(self, code: str) -> str:
        try:
            info = get_airport_by_code(code)
            return info.get("city", code)
        except Exception:
            return code

    def _baggage(self, breakdown: List[Any]) -> Tuple[str, str]:
        checked, cabin = "", ""
        for item in breakdown:
            if not isinstance(item, dict):
                continue
            checked_values = item.get("Baggage") or []
            cabin_values = item.get("CabinBaggage") or []
            if not checked and checked_values:
                checked = ", ".join(str(v) for v in _as_list(checked_values) if v)
            if not cabin and cabin_values:
                cabin = ", ".join(str(v) for v in _as_list(cabin_values) if v)
        return checked, cabin

    def _fare_class_detail(self, details: List[Any]) -> Dict[str, Any]:
        for group in details:
            if not isinstance(group, dict):
                continue
            values = _as_list(group.get("FareClassDetail"))
            for detail in values:
                if isinstance(detail, dict):
                    return detail
        return {}

    def _seats(self, detail: Dict[str, Any]) -> int:
        seats = detail.get("SeatsRemaining") or {}
        try:
            return int(seats.get("Number") if isinstance(seats, dict) else seats)
        except (TypeError, ValueError):
            return 0

    def _total_duration(self, segments: List[FlightSegment]) -> str:
        minutes = sum(s.duration_minutes for s in segments)
        return f"{minutes // 60}h {minutes % 60}m" if minutes % 60 else f"{minutes // 60}h"
