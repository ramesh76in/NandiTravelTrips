"""
Travelport TripServices & Universal API Client
Handles LowFareSearch, Air Availability, TripServices PNR Retrieval, and Schema Mapping
"""
import os
import re
import base64
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests

from .schemas import FlightItem, FlightSegment
from .flights_data import get_airport_by_code

logger = logging.getLogger(__name__)

# Airline Name mapping
AIRLINE_NAMES = {
    "6E": "IndiGo",
    "AI": "Air India",
    "UK": "Vistara",
    "SG": "SpiceJet",
    "QP": "Akasa Air",
    "EK": "Emirates",
    "SQ": "Singapore Airlines",
    "BA": "British Airways",
    "QR": "Qatar Airways",
    "LH": "Lufthansa",
    "EY": "Etihad Airways",
    "AF": "Air France",
    "KL": "KLM",
    "AA": "American Airlines",
    "UA": "United Airlines",
    "DL": "Delta Air Lines",
}


def parse_duration_minutes(duration_str: str) -> tuple[str, int]:
    """
    Parses duration string in minutes (e.g. '135') or ISO 'PT2H15M'
    """
    if not duration_str:
        return "2h 00m", 120

    if duration_str.isdigit():
        total_mins = int(duration_str)
        hours = total_mins // 60
        mins = total_mins % 60
        return (f"{hours}h {mins}m" if mins > 0 else f"{hours}h"), total_mins

    hours_match = re.search(r"(\d+)H", duration_str)
    mins_match = re.search(r"(\d+)M", duration_str)
    hours = int(hours_match.group(1)) if hours_match else 0
    mins = int(mins_match.group(1)) if mins_match else 0
    total_mins = (hours * 60) + mins
    return (f"{hours}h {mins}m" if mins > 0 else f"{hours}h"), total_mins


def _load_env_if_present():
    env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if "#" in v and not (v.startswith('"') or v.startswith("'")):
                        v = v.split("#")[0].strip()
                    v = v.strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v


class TravelportClient:
    """
    Travelport GDS TripServices and Air Shopping API Client
    """
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        target_branch: Optional[str] = None,
        env: str = "test",
    ):
        _load_env_if_present()
        self.username = username if username is not None else os.environ.get("TRAVELPORT_USERNAME", "").strip()
        self.password = password if password is not None else os.environ.get("TRAVELPORT_PASSWORD", "").strip()
        self.target_branch = target_branch if target_branch is not None else os.environ.get("TRAVELPORT_TARGET_BRANCH", "").strip()
        self.env = (env or os.environ.get("TRAVELPORT_ENV", "test")).lower()

        if self.env in ("production", "prod"):
            self.air_service_url = "https://emea.universal-api.travelport.com/B2BGateway/connect/uAPI/AirService"
            self.trip_service_url = "https://emea.universal-api.travelport.com/B2BGateway/connect/uAPI/UniversalRecordService"
        else:
            self.air_service_url = "https://emea.universal-api.pp.travelport.com/B2BGateway/connect/uAPI/AirService"
            self.trip_service_url = "https://emea.universal-api.pp.travelport.com/B2BGateway/connect/uAPI/UniversalRecordService"

    @property
    def is_configured(self) -> bool:
        """
        Returns True if Travelport credentials and Target Branch are configured
        """
        return bool(self.username and self.password and self.target_branch)

    def _get_auth_headers(self) -> Dict[str, str]:
        auth_str = f"{self.username}:{self.password}"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        return {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "TargetBranch": self.target_branch,
        }

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
        max_results: int = 20,
    ) -> Optional[List[FlightItem]]:
        """
        Executes Travelport Air Search / LowFareSearch request
        """
        if not self.is_configured:
            return None

        headers = self._get_auth_headers()
        payload = {
            "origin": origin_code.upper().strip(),
            "destination": destination_code.upper().strip(),
            "departureDate": departure_date.strip(),
            "returnDate": return_date.strip() if return_date else None,
            "passengers": {
                "adults": max(1, adults),
                "children": children,
                "infants": infants,
            },
            "cabinClass": travel_class.upper(),
            "nonStop": non_stop,
            "currency": currency,
            "maxResults": max_results,
            "targetBranch": self.target_branch,
        }

        try:
            response = requests.post(
                self.air_service_url,
                json=payload,
                headers=headers,
                timeout=12,
            )
            if response.status_code == 200:
                return self.parse_travelport_response(response.json(), travel_class)
            else:
                logger.warning(
                    f"Travelport AirSearch API returned status {response.status_code}: {response.text}"
                )
                return None
        except Exception as e:
            logger.error(f"Error connecting to Travelport TripServices API: {e}")
            return None

    def retrieve_trip(self, universal_record_locator: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves confirmed itinerary via Travelport TripServices / UniversalRecordRetrieve
        """
        if not self.is_configured:
            return None

        headers = self._get_auth_headers()
        params = {
            "locatorCode": universal_record_locator.strip().upper(),
            "targetBranch": self.target_branch,
        }

        try:
            response = requests.get(
                self.trip_service_url,
                params=params,
                headers=headers,
                timeout=10,
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Travelport Trip Retrieve failed ({response.status_code})")
                return None
        except Exception as e:
            logger.error(f"Error retrieving Travelport trip: {e}")
            return None

    def parse_travelport_response(
        self, data: Dict[str, Any], requested_class: str = "ECONOMY"
    ) -> List[FlightItem]:
        """
        Parses Travelport AirPricingSolutions / AirOffers into FlightItem models
        """
        solutions = (
            data.get("airPricingSolution")
            or data.get("airOffers")
            or data.get("AirPriceResult")
            or data.get("flights")
            or []
        )

        flight_items: List[FlightItem] = []

        for idx, item in enumerate(solutions):
            try:
                item_id = item.get("id") or item.get("key") or f"TP_{idx}"

                # Extract pricing
                total_price_str = str(
                    item.get("totalPrice")
                    or item.get("approximateTotalPrice")
                    or item.get("total_price", "4500")
                )
                total_price = float(re.sub(r"[^\d.]", "", total_price_str) or 4500.0)

                base_price_str = str(
                    item.get("basePrice")
                    or item.get("approximateBasePrice")
                    or item.get("base_price", "")
                )
                base_price = (
                    float(re.sub(r"[^\d.]", "", base_price_str))
                    if base_price_str
                    else round(total_price * 0.88, 2)
                )
                taxes = round(total_price - base_price, 2)

                # Extract segments
                segments_raw = (
                    item.get("airSegment")
                    or item.get("segments")
                    or item.get("flightSegments")
                    or []
                )

                if not segments_raw:
                    continue

                first_seg = segments_raw[0]
                last_seg = segments_raw[-1]

                origin_code = first_seg.get("origin") or first_seg.get("originLocationCode", "")
                destination_code = (
                    last_seg.get("destination") or last_seg.get("destinationLocationCode", "")
                )

                dep_time_raw = first_seg.get("departureTime") or first_seg.get("departure", "")
                arr_time_raw = last_seg.get("arrivalTime") or last_seg.get("arrival", "")

                dep_time = (
                    dep_time_raw.split("T")[1][:5]
                    if "T" in dep_time_raw
                    else dep_time_raw[:5] if len(dep_time_raw) >= 5 else "07:30"
                )
                arr_time = (
                    arr_time_raw.split("T")[1][:5]
                    if "T" in arr_time_raw
                    else arr_time_raw[:5] if len(arr_time_raw) >= 5 else "09:45"
                )

                carrier_code = (
                    first_seg.get("carrier")
                    or first_seg.get("airlineCode")
                    or first_seg.get("carrierCode", "AI")
                )
                carrier_name = (
                    first_seg.get("carrierName")
                    or AIRLINE_NAMES.get(carrier_code)
                    or f"Airline {carrier_code}"
                )
                flight_num = f"{carrier_code}-{first_seg.get('flightNumber', '101')}"

                flight_duration_raw = str(
                    item.get("totalTravelTime")
                    or first_seg.get("flightTime")
                    or first_seg.get("duration", "130")
                )
                formatted_duration, duration_mins = parse_duration_minutes(flight_duration_raw)

                stops_count = max(0, len(segments_raw) - 1)
                stop_cities = []
                for s in segments_raw[:-1]:
                    stop_code = s.get("destination") or s.get("destinationLocationCode", "")
                    if stop_code:
                        stop_cities.append(get_airport_by_code(stop_code)["city"])

                origin_info = get_airport_by_code(origin_code)
                dest_info = get_airport_by_code(destination_code)

                # Baggage allowance
                baggage_cabin = "7 Kg"
                baggage_checkin = (
                    item.get("baggageAllowance")
                    or item.get("checkedBags")
                    or "15 Kg"
                )

                # Parse segments
                segments_parsed: List[FlightSegment] = []
                for seg in segments_raw:
                    s_code = seg.get("carrier") or seg.get("carrierCode", carrier_code)
                    s_name = AIRLINE_NAMES.get(s_code, s_code)
                    s_orig = seg.get("origin") or seg.get("originLocationCode", origin_code)
                    s_dest = seg.get("destination") or seg.get("destinationLocationCode", destination_code)
                    s_dep = seg.get("departureTime") or seg.get("departure", "")
                    s_arr = seg.get("arrivalTime") or seg.get("arrival", "")
                    s_dur_str, s_dur_mins = parse_duration_minutes(
                        str(seg.get("flightTime") or seg.get("duration", "120"))
                    )

                    segments_parsed.append(
                        FlightSegment(
                            airline=s_name,
                            airline_code=s_code,
                            flight_number=f"{s_code}-{seg.get('flightNumber', '')}",
                            origin=s_orig,
                            origin_city=get_airport_by_code(s_orig)["city"],
                            destination=s_dest,
                            destination_city=get_airport_by_code(s_dest)["city"],
                            departure_time=s_dep.split("T")[1][:5] if "T" in s_dep else s_dep[:5],
                            arrival_time=s_arr.split("T")[1][:5] if "T" in s_arr else s_arr[:5],
                            duration=s_dur_str,
                            duration_minutes=s_dur_mins,
                            aircraft=seg.get("equipment", "Airbus A320 / Boeing 737"),
                        )
                    )

                flight_item = FlightItem(
                    id=f"TP_{item_id}_{origin_code}_{destination_code}",
                    airline=carrier_name,
                    airline_code=carrier_code,
                    flight_number=flight_num,
                    origin=origin_code,
                    origin_city=origin_info["city"],
                    destination=destination_code,
                    destination_city=dest_info["city"],
                    departure_time=dep_time,
                    arrival_time=arr_time,
                    duration=formatted_duration,
                    duration_minutes=duration_mins,
                    stops=stops_count,
                    stop_cities=stop_cities,
                    travel_class=requested_class.upper(),
                    seats_available=int(item.get("seatsAvailable", 8)),
                    refundable=bool(item.get("refundable", True)),
                    baggage_cabin=baggage_cabin,
                    baggage_checkin=baggage_checkin,
                    base_price=round(base_price, 2),
                    taxes=round(taxes, 2),
                    final_price=round(total_price, 2),
                    segments=segments_parsed,
                )
                flight_items.append(flight_item)

            except Exception as e:
                logger.error(f"Error parsing Travelport flight item: {e}")
                continue

        return flight_items
