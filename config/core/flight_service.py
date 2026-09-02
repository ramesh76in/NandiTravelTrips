"""
Flight Service layer for Django Core App
Supports Multi-GDS Routing (Travelport TripServices, Amadeus API) with Local Engine Fallback
"""
import os
import logging
from typing import List, Dict, Any, Optional
from django.conf import settings
from backend.flights_data import AIRPORTS_DB, generate_flights, get_airport_by_code
from backend.travelport_client import TravelportClient
from backend.amadeus_client import AmadeusClient
from backend.travelopro_client import TraveloproClient

logger = logging.getLogger(__name__)


def search_flights_service(
    origin_code: str,
    destination_code: str,
    departure_date: str,
    return_date: Optional[str] = None,
    trip_type: str = "ONEWAY",
    travel_class: str = "ECONOMY",
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    fare_type: str = "Regular",
    promo_code: Optional[str] = None,
    non_stop: bool = False,
    sort_by: str = "cheapest",
    max_price: Optional[float] = None,
    airline_filter: Optional[List[str]] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    origin_info = get_airport_by_code(origin_code)
    dest_info = get_airport_by_code(destination_code)

    flights = None
    data_source = "simulation"
    gds_provider = getattr(settings, "GDS_PROVIDER", "auto").lower()

    # 1. Check Travelopro API if requested or in auto mode
    if gds_provider in ("travelopro", "auto"):
        travelopro = TraveloproClient()
        if travelopro.is_configured:
            try:
                tpro_flights = travelopro.search_flights(
                    origin_code=origin_code,
                    destination_code=destination_code,
                    departure_date=departure_date,
                    return_date=return_date,
                    adults=adults,
                    children=children,
                    infants=infants,
                    travel_class=travel_class,
                    non_stop=non_stop,
                    currency="INR",
                    trip_type=trip_type,
                    fare_type=fare_type,
                    correlation_id=correlation_id,
                )
                if tpro_flights:
                    flights = tpro_flights
                    data_source = "travelopro_live"
                    logger.info(f"Retrieved {len(tpro_flights)} live flights from Travelopro API")
            except Exception as e:
                logger.warning(f"Travelopro API error, trying next provider: {e}")

    # 2. Check Travelport TripServices if requested or in auto mode
    if not flights and gds_provider in ("travelport", "auto"):
        travelport = TravelportClient()
        if travelport.is_configured:
            try:
                tp_flights = travelport.search_flights(
                    origin_code=origin_code,
                    destination_code=destination_code,
                    departure_date=departure_date,
                    return_date=return_date,
                    adults=adults,
                    children=children,
                    infants=infants,
                    travel_class=travel_class,
                    non_stop=non_stop,
                    currency="INR",
                )
                if tp_flights:
                    flights = tp_flights
                    data_source = "travelport_live"
                    logger.info(f"Retrieved {len(tp_flights)} live flights from Travelport TripServices")
            except Exception as e:
                logger.warning(f"Travelport API error, trying next provider: {e}")

    # 3. Check Amadeus Flight Offers API if others didn't return or Amadeus explicitly chosen
    if not flights and gds_provider in ("amadeus", "auto"):
        amadeus = AmadeusClient()
        if amadeus.is_configured:
            try:
                amadeus_flights = amadeus.search_flight_offers(
                    origin_code=origin_code,
                    destination_code=destination_code,
                    departure_date=departure_date,
                    return_date=return_date,
                    adults=adults,
                    children=children,
                    infants=infants,
                    travel_class=travel_class,
                    non_stop=non_stop,
                    currency="INR",
                )
                if amadeus_flights:
                    flights = amadeus_flights
                    data_source = "amadeus_live"
                    logger.info(f"Retrieved {len(amadeus_flights)} live flights from Amadeus API")
            except Exception as e:
                logger.warning(f"Amadeus API error: {e}")

    # 4. Fallback to high-speed deterministic flight generator if GDS is unconfigured or unavailable
    if not flights and gds_provider == "travelopro":
        return {
            "origin_code": origin_code.upper(),
            "origin_city": origin_info["city"],
            "destination_code": destination_code.upper(),
            "destination_city": dest_info["city"],
            "departure_date": departure_date,
            "return_date": return_date,
            "trip_type": trip_type,
            "travel_class": travel_class,
            "adults": adults, "children": children, "infants": infants,
            "total_passengers": adults + children + infants,
            "fare_type": fare_type, "promo_code": promo_code, "non_stop": non_stop,
            "total_results": 0, "flights": [], "available_airlines": [],
            "min_price": 0, "max_price": 0, "data_source": "travelopro_unavailable",
        }

    if not flights:
        flights = generate_flights(
            origin_code=origin_code,
            destination_code=destination_code,
            departure_date=departure_date,
            travel_class=travel_class,
            adults=adults,
            children=children,
            infants=infants,
            fare_type=fare_type,
            promo_code=promo_code,
            non_stop=non_stop,
        )
        data_source = "simulation"

    flight_dicts = [f.model_dump() for f in flights]

    # Filter by airlines if provided
    if airline_filter:
        airlines_lower = [a.lower() for a in airline_filter]
        flight_dicts = [
            f for f in flight_dicts
            if f["airline"].lower() in airlines_lower or f["airline_code"].lower() in airlines_lower
        ]

    # Filter by price
    if max_price:
        flight_dicts = [f for f in flight_dicts if f["final_price"] <= max_price]

    # Sort
    if sort_by == "cheapest":
        flight_dicts.sort(key=lambda x: x["final_price"])
    elif sort_by == "fastest":
        flight_dicts.sort(key=lambda x: x["duration_minutes"])
    elif sort_by == "earliest":
        flight_dicts.sort(key=lambda x: x["departure_time"])

    # Unique airlines available in the results
    available_airlines = list({f["airline"] for f in flight_dicts})
    min_price = min([f["final_price"] for f in flight_dicts]) if flight_dicts else 0
    max_price_found = max([f["final_price"] for f in flight_dicts]) if flight_dicts else 0

    return {
        "origin_code": origin_code.upper(),
        "origin_city": origin_info["city"],
        "destination_code": destination_code.upper(),
        "destination_city": dest_info["city"],
        "departure_date": departure_date,
        "return_date": return_date,
        "trip_type": trip_type,
        "travel_class": travel_class,
        "adults": adults,
        "children": children,
        "infants": infants,
        "total_passengers": adults + children + infants,
        "fare_type": fare_type,
        "promo_code": promo_code,
        "non_stop": non_stop,
        "total_results": len(flight_dicts),
        "flights": flight_dicts,
        "available_airlines": available_airlines,
        "min_price": min_price,
        "max_price": max_price_found,
        "data_source": data_source,
    }


def get_all_airports() -> List[Dict[str, str]]:
    return AIRPORTS_DB


def get_flight_by_id(
    flight_id: str,
    origin_code: str = "JAI",
    destination_code: str = "BOM",
    departure_date: str = "2026-08-25",
    stored_flights: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    # Prefer the exact live offer captured during the current search. This is
    # essential for Travelopro because session_id + FareSourceCode identify the
    # provider-priced offer that must be revalidated before booking.
    for item in stored_flights or []:
        if str(item.get("id")) == str(flight_id):
            return item

    # Simulation lookup is retained only for legacy/local fallback searches.
    flights = generate_flights(
        origin_code=origin_code,
        destination_code=destination_code,
        departure_date=departure_date
    )
    for f in flights:
        if f.id == flight_id or flight_id in f.id:
            return f.model_dump()
    return None
