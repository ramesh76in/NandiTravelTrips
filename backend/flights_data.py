"""
Realistic Flight Data Generator and Airport Database for Nandi Travel Trips
"""
import hashlib
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from .schemas import Airport, FlightItem, FlightSegment


AIRPORTS_DB: List[Dict[str, str]] = [
    {"city": "Delhi", "code": "DEL", "airport": "Indira Gandhi International Airport", "country": "India"},
    {"city": "Mumbai", "code": "BOM", "airport": "Chhatrapati Shivaji Maharaj International Airport", "country": "India"},
    {"city": "Bengaluru", "code": "BLR", "airport": "Kempegowda International Airport", "country": "India"},
    {"city": "Hyderabad", "code": "HYD", "airport": "Rajiv Gandhi International Airport", "country": "India"},
    {"city": "Chennai", "code": "MAA", "airport": "Chennai International Airport", "country": "India"},
    {"city": "Kolkata", "code": "CCU", "airport": "Netaji Subhas Chandra Bose International Airport", "country": "India"},
    {"city": "Jaipur", "code": "JAI", "airport": "Jaipur International Airport", "country": "India"},
    {"city": "Ahmedabad", "code": "AMD", "airport": "Sardar Vallabhbhai Patel International Airport", "country": "India"},
    {"city": "Goa", "code": "GOI", "airport": "Goa International Airport (Dabolim)", "country": "India"},
    {"city": "Pune", "code": "PNQ", "airport": "Pune International Airport", "country": "India"},
    {"city": "Kochi", "code": "COK", "airport": "Cochin International Airport", "country": "India"},
    {"city": "Dubai", "code": "DXB", "airport": "Dubai International Airport", "country": "UAE"},
    {"city": "Singapore", "code": "SIN", "airport": "Singapore Changi Airport", "country": "Singapore"},
    {"city": "London", "code": "LHR", "airport": "Heathrow Airport", "country": "United Kingdom"},
    {"city": "New York", "code": "JFK", "airport": "John F. Kennedy International Airport", "country": "USA"},
    {"city": "Bangkok", "code": "BKK", "airport": "Suvarnabhumi Airport", "country": "Thailand"},
]

AIRLINES_DOMESTIC = [
    {"name": "IndiGo", "code": "6E", "base_price": 4200, "color": "#00205B"},
    {"name": "Air India", "code": "AI", "base_price": 4800, "color": "#ED1B24"},
    {"name": "Vistara", "code": "UK", "base_price": 5200, "color": "#581845"},
    {"name": "SpiceJet", "code": "SG", "base_price": 3900, "color": "#ED1C24"},
    {"name": "Akasa Air", "code": "QP", "base_price": 4100, "color": "#FF671F"},
]

AIRLINES_INTERNATIONAL = [
    {"name": "Emirates", "code": "EK", "base_price": 28000, "color": "#D71921"},
    {"name": "Singapore Airlines", "code": "SQ", "base_price": 32000, "color": "#00205B"},
    {"name": "Air India", "code": "AI", "base_price": 24000, "color": "#ED1B24"},
    {"name": "British Airways", "code": "BA", "base_price": 45000, "color": "#075AAA"},
    {"name": "IndiGo", "code": "6E", "base_price": 18000, "color": "#00205B"},
]


def get_airport_by_code(code: str) -> Dict[str, str]:
    code_upper = code.upper().strip()
    for a in AIRPORTS_DB:
        if a["code"] == code_upper:
            return a
    return {"city": code_upper, "code": code_upper, "airport": f"{code_upper} Airport", "country": "International"}


def generate_flights(
    origin_code: str,
    destination_code: str,
    departure_date: str,
    travel_class: str = "ECONOMY",
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    fare_type: str = "Regular",
    promo_code: Optional[str] = None,
    non_stop: bool = False,
) -> List[FlightItem]:
    origin_info = get_airport_by_code(origin_code)
    dest_info = get_airport_by_code(destination_code)

    is_international = origin_info["country"] != "India" or dest_info["country"] != "India"
    airlines_pool = AIRLINES_INTERNATIONAL if is_international else AIRLINES_DOMESTIC

    # Seed deterministic pseudo-random generator based on date and route
    seed_str = f"{origin_code}_{destination_code}_{departure_date}"
    seed_hash = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % 100000
    rng = random.Random(seed_hash)

    class_multipliers = {
        "ECONOMY": 1.0,
        "PREMIUM_ECONOMY": 1.45,
        "BUSINESS": 2.6,
        "FIRST": 4.2,
    }
    class_mult = class_multipliers.get(travel_class.upper(), 1.0)

    fare_discounts = {
        "Regular": 1.0,
        "Student": 0.90,       # 10% off
        "Senior Citizen": 0.88, # 12% off
        "Armed Forces": 0.85,   # 15% off
    }
    fare_mult = fare_discounts.get(fare_type, 1.0)

    # Schedules across the day
    time_slots = [
        ("06:00", "08:15", 135, 0),
        ("08:30", "10:40", 130, 0),
        ("11:15", "14:45", 210, 1),
        ("13:00", "15:10", 130, 0),
        ("15:45", "19:20", 215, 1),
        ("17:30", "19:40", 130, 0),
        ("19:50", "22:00", 130, 0),
        ("21:30", "23:45", 135, 0),
        ("23:15", "04:30", 315, 1),
    ]

    flights: List[FlightItem] = []
    
    for idx, (dep, arr, duration_mins, stops) in enumerate(time_slots):
        if non_stop and stops > 0:
            continue

        airline = airlines_pool[idx % len(airlines_pool)]
        flight_num = f"{airline['code']}-{rng.randint(200, 999)}"
        flight_id = f"FL_{origin_code}_{destination_code}_{idx}_{seed_hash % 1000}"

        hours = duration_mins // 60
        mins = duration_mins % 60
        duration_str = f"{hours}h {mins}m" if mins > 0 else f"{hours}h"

        # Price calculation with realistic variance
        base_airline_price = airline["base_price"] * (1.0 + (rng.randint(-15, 25) / 100.0))
        base_total = round(base_airline_price * class_mult * fare_mult, 2)
        taxes = round(base_total * 0.12, 2)  # 12% GST + Airport fees
        final_price = round(base_total + taxes, 2)

        # Apply promo code discount if valid
        if promo_code and promo_code.strip().upper() in ["NANDI10", "SPECIAL10", "FLYHIGH"]:
            final_price = round(final_price * 0.90, 2)

        stop_cities = []
        if stops == 1:
            hub = "DEL" if origin_code != "DEL" and destination_code != "DEL" else "BOM"
            stop_cities = [get_airport_by_code(hub)["city"]]

        # Cabin & check-in baggage
        baggage_cabin = "7 Kg" if travel_class == "ECONOMY" else "10 Kg"
        baggage_checkin = "15 Kg" if travel_class == "ECONOMY" else ("25 Kg" if travel_class == "PREMIUM_ECONOMY" else "35 Kg")

        segments = [
            FlightSegment(
                airline=airline["name"],
                airline_code=airline["code"],
                flight_number=flight_num,
                origin=origin_code,
                origin_city=origin_info["city"],
                destination=destination_code,
                destination_city=dest_info["city"],
                departure_time=dep,
                arrival_time=arr,
                duration=duration_str,
                duration_minutes=duration_mins,
                aircraft="Airbus A320neo" if stops == 0 else "Boeing 737-800",
            )
        ]

        flight_item = FlightItem(
            id=flight_id,
            airline=airline["name"],
            airline_code=airline["code"],
            flight_number=flight_num,
            origin=origin_code,
            origin_city=origin_info["city"],
            destination=destination_code,
            destination_city=dest_info["city"],
            departure_time=dep,
            arrival_time=arr,
            duration=duration_str,
            duration_minutes=duration_mins,
            stops=stops,
            stop_cities=stop_cities,
            travel_class=travel_class.upper(),
            seats_available=rng.randint(3, 18),
            refundable=bool(idx % 2 == 0),
            baggage_cabin=baggage_cabin,
            baggage_checkin=baggage_checkin,
            base_price=base_total,
            taxes=taxes,
            final_price=final_price,
            segments=segments,
        )
        flights.append(flight_item)

    return flights
