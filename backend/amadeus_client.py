"""
Amadeus Self-Service Flight Offers Search API Client
Handles OAuth2 token caching, flight search, and schema mapping
"""
import os
import re
import time
import logging
from typing import List, Dict, Any, Optional
import requests

from .schemas import FlightItem, FlightSegment
from .flights_data import get_airport_by_code

logger = logging.getLogger(__name__)

# Standard Airline Name Dictionary Fallbacks
AIRLINE_NAMES = {
    "6E": "IndiGo",
    "AI": "Air India",
    "UK": "Vistara",
    "SG": "SpiceJet",
    "QP": "Akasa Air",
    "G8": "Go First",
    "I5": "AirAsia India",
    "IX": "Air India Express",
    "EK": "Emirates",
    "SQ": "Singapore Airlines",
    "BA": "British Airways",
    "QR": "Qatar Airways",
    "LH": "Lufthansa",
    "EY": "Etihad Airways",
    "AF": "Air France",
    "KL": "KLM Royal Dutch Airlines",
    "AA": "American Airlines",
    "UA": "United Airlines",
    "DL": "Delta Air Lines",
}


def parse_iso_duration(iso_duration: str) -> tuple[str, int]:
    """
    Parses ISO 8601 duration e.g. 'PT2H15M', 'PT135M', 'PT1H' into ('2h 15m', 135)
    """
    if not iso_duration:
        return "2h 00m", 120

    hours_match = re.search(r"(\d+)H", iso_duration)
    mins_match = re.search(r"(\d+)M", iso_duration)

    hours = int(hours_match.group(1)) if hours_match else 0
    mins = int(mins_match.group(1)) if mins_match else 0
    total_mins = (hours * 60) + mins

    if hours > 0 and mins > 0:
        formatted = f"{hours}h {mins}m"
    elif hours > 0:
        formatted = f"{hours}h"
    else:
        formatted = f"{mins}m"

    return formatted, total_mins


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


class AmadeusClient:
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        env: str = "test",
    ):
        _load_env_if_present()
        self.client_id = client_id if client_id is not None else os.environ.get("AMADEUS_CLIENT_ID", "").strip()
        self.client_secret = client_secret if client_secret is not None else os.environ.get("AMADEUS_CLIENT_SECRET", "").strip()
        self.env = (env or os.environ.get("AMADEUS_ENV", "test")).lower()

        if self.env == "production":
            self.base_url = "https://api.amadeus.com"
        else:
            self.base_url = "https://test.api.amadeus.com"

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def get_access_token(self) -> Optional[str]:
        """
        Retrieves or refreshes OAuth2 Bearer Access Token
        """
        if not self.is_configured:
            return None

        # Return cached token if valid for at least 60 more seconds
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        token_url = f"{self.base_url}/v1/security/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            response = requests.post(token_url, data=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self._access_token = data.get("access_token")
                expires_in = data.get("expires_in", 1799)
                self._token_expires_at = time.time() + expires_in
                return self._access_token
            else:
                logger.error(f"Amadeus OAuth failed ({response.status_code}): {response.text}")
                return None
        except Exception as e:
            logger.error(f"Exception during Amadeus OAuth token request: {e}")
            return None

    def search_flight_offers(
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
        Executes Amadeus Flight Offers Search API (v2)
        """
        token = self.get_access_token()
        if not token:
            return None

        search_url = f"{self.base_url}/v2/shopping/flight-offers"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        # Travel class mapping for Amadeus (ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST)
        class_map = {
            "ECONOMY": "ECONOMY",
            "PREMIUM_ECONOMY": "PREMIUM_ECONOMY",
            "BUSINESS": "BUSINESS",
            "FIRST": "FIRST",
        }
        amadeus_class = class_map.get(travel_class.upper(), "ECONOMY")

        params: Dict[str, Any] = {
            "originLocationCode": origin_code.upper().strip(),
            "destinationLocationCode": destination_code.upper().strip(),
            "departureDate": departure_date.strip(),
            "adults": max(1, adults),
            "travelClass": amadeus_class,
            "currencyCode": currency,
            "max": max_results,
        }

        if children > 0:
            params["children"] = children
        if infants > 0:
            params["infants"] = infants
        if return_date:
            params["returnDate"] = return_date.strip()
        if non_stop:
            params["nonStop"] = "true"

        try:
            response = requests.get(search_url, params=params, headers=headers, timeout=12)
            if response.status_code == 200:
                json_data = response.json()
                return self.parse_amadeus_response(json_data, travel_class)
            else:
                logger.warning(
                    f"Amadeus Flight Search API returned status {response.status_code}: {response.text}"
                )
                return None
        except Exception as e:
            logger.error(f"Error calling Amadeus Flight Search API: {e}")
            return None

    def parse_amadeus_response(
        self, data: Dict[str, Any], requested_class: str = "ECONOMY"
    ) -> List[FlightItem]:
        """
        Transforms Amadeus raw JSON response into standard FlightItem models
        """
        offers = data.get("data", [])
        dictionaries = data.get("dictionaries", {})
        carrier_dict = dictionaries.get("carriers", {})

        flight_items: List[FlightItem] = []

        for offer in offers:
            try:
                offer_id = str(offer.get("id", "0"))
                price_info = offer.get("price", {})
                grand_total = float(price_info.get("grandTotal", price_info.get("total", 0)))
                base_price = float(price_info.get("base", grand_total * 0.88))
                taxes = round(grand_total - base_price, 2)

                itineraries = offer.get("itineraries", [])
                if not itineraries:
                    continue

                # Take outward itinerary
                outward = itineraries[0]
                total_duration_iso = outward.get("duration", "")
                formatted_duration, duration_mins = parse_iso_duration(total_duration_iso)

                segments_raw = outward.get("segments", [])
                if not segments_raw:
                    continue

                first_seg = segments_raw[0]
                last_seg = segments_raw[-1]

                origin_code = first_seg.get("departure", {}).get("iataCode", "")
                destination_code = last_seg.get("arrival", {}).get("iataCode", "")

                dep_at = first_seg.get("departure", {}).get("at", "")
                arr_at = last_seg.get("arrival", {}).get("at", "")

                dep_time = dep_at.split("T")[1][:5] if "T" in dep_at else "08:00"
                arr_time = arr_at.split("T")[1][:5] if "T" in arr_at else "10:30"

                carrier_code = first_seg.get("carrierCode", "")
                carrier_name = (
                    carrier_dict.get(carrier_code)
                    or AIRLINE_NAMES.get(carrier_code)
                    or f"Airline {carrier_code}"
                )
                carrier_name = carrier_name.title()

                flight_num = f"{carrier_code}-{first_seg.get('number', '101')}"
                stops_count = len(segments_raw) - 1

                stop_cities = []
                for s in segments_raw[:-1]:
                    stop_iata = s.get("arrival", {}).get("iataCode", "")
                    stop_cities.append(get_airport_by_code(stop_iata)["city"])

                origin_info = get_airport_by_code(origin_code)
                dest_info = get_airport_by_code(destination_code)

                # Checked baggage allowance
                baggage_checkin = "15 Kg"
                traveler_pricings = offer.get("travelerPricings", [])
                if traveler_pricings:
                    fare_details = traveler_pricings[0].get("fareDetailsBySegment", [])
                    if fare_details:
                        bags_info = fare_details[0].get("includedCheckedBags", {})
                        if "weight" in bags_info:
                            baggage_checkin = f"{bags_info['weight']} {bags_info.get('weightUnit', 'Kg')}"
                        elif "quantity" in bags_info:
                            baggage_checkin = f"{bags_info['quantity']} Piece(s)"

                # Segments list
                segments_parsed: List[FlightSegment] = []
                for seg in segments_raw:
                    s_carrier = seg.get("carrierCode", "")
                    s_carrier_name = (
                        carrier_dict.get(s_carrier)
                        or AIRLINE_NAMES.get(s_carrier)
                        or s_carrier
                    ).title()
                    s_dep = seg.get("departure", {}).get("at", "")
                    s_arr = seg.get("arrival", {}).get("at", "")
                    s_dur_str, s_dur_mins = parse_iso_duration(seg.get("duration", ""))
                    s_orig = seg.get("departure", {}).get("iataCode", "")
                    s_dest = seg.get("arrival", {}).get("iataCode", "")

                    segments_parsed.append(
                        FlightSegment(
                            airline=s_carrier_name,
                            airline_code=s_carrier,
                            flight_number=f"{s_carrier}-{seg.get('number', '')}",
                            origin=s_orig,
                            origin_city=get_airport_by_code(s_orig)["city"],
                            destination=s_dest,
                            destination_city=get_airport_by_code(s_dest)["city"],
                            departure_time=s_dep.split("T")[1][:5] if "T" in s_dep else "",
                            arrival_time=s_arr.split("T")[1][:5] if "T" in s_arr else "",
                            duration=s_dur_str,
                            duration_minutes=s_dur_mins,
                            aircraft=seg.get("aircraft", {}).get("code", "Airbus / Boeing"),
                        )
                    )

                seats_avail = offer.get("numberOfBookableSeats", 7)

                flight_item = FlightItem(
                    id=f"AM_{offer_id}_{origin_code}_{destination_code}",
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
                    seats_available=seats_avail,
                    refundable=not offer.get("pricingOptions", {}).get("refundableFare", False) is False,
                    baggage_cabin="7 Kg",
                    baggage_checkin=baggage_checkin,
                    base_price=round(base_price, 2),
                    taxes=round(taxes, 2),
                    final_price=round(grand_total, 2),
                    segments=segments_parsed,
                )
                flight_items.append(flight_item)

            except Exception as e:
                logger.error(f"Error parsing individual Amadeus offer: {e}")
                continue

        return flight_items

    def confirm_flight_price(self, flight_offer_raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Confirms price and seat availability for a selected flight offer via Amadeus Flight Offers Price API
        POST /v1/shopping/flight-offers/pricing
        """
        token = self.get_access_token()
        if not token:
            return None

        url = f"{self.base_url}/v1/shopping/flight-offers/pricing"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "data": {
                "type": "flight-offers-pricing",
                "flightOffers": [flight_offer_raw] if isinstance(flight_offer_raw, dict) else flight_offer_raw
            }
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=12)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Amadeus Flight Offers Price failed ({response.status_code}): {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error calling Amadeus Flight Offers Price API: {e}")
            return None

    def create_flight_order(
        self, flight_offer_raw: Dict[str, Any], travelers: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Creates a flight booking order via Amadeus Flight Create Orders API
        POST /v1/booking/flight-orders
        """
        token = self.get_access_token()
        if not token:
            return None

        url = f"{self.base_url}/v1/booking/flight-orders"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "data": {
                "type": "flight-order",
                "flightOffers": [flight_offer_raw] if isinstance(flight_offer_raw, dict) else flight_offer_raw,
                "travelers": travelers,
            }
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code in (200, 201):
                return response.json()
            else:
                logger.warning(f"Amadeus Flight Order creation failed ({response.status_code}): {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error calling Amadeus Flight Order API: {e}")
            return None

    def search_locations(self, keyword: str, sub_type: str = "AIRPORT,CITY") -> Optional[List[Dict[str, Any]]]:
        """
        Searches airports and cities via Amadeus Location Search API
        GET /v1/reference-data/locations
        """
        token = self.get_access_token()
        if not token:
            return None

        url = f"{self.base_url}/v1/reference-data/locations"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        params = {"keyword": keyword.strip(), "subType": sub_type}

        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
            return None
        except Exception as e:
            logger.error(f"Error calling Amadeus Reference Data Locations: {e}")
            return None
