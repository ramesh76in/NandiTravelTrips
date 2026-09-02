"""
FastAPI Backend Application for Nandi Travel Trips
Integrated with Multi-GDS Routing (Amadeus Self-Service API & Travelport TripServices)
"""
import os
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Tuple
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    Airport,
    FlightItem,
    FlightSearchResponse,
    BookingRequest,
    BookingResponse,
)
from .flights_data import AIRPORTS_DB, generate_flights, get_airport_by_code
from .amadeus_client import AmadeusClient
from .travelport_client import TravelportClient
from .travelopro_client import TraveloproClient

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Nandi Travel Trips API",
    description="Comprehensive Flight Search, Booking, and Multi-GDS Travel Management API",
    version="2.2.0",
)

# CORS configuration supporting development & production origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:8001",
        "http://localhost:8001",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def fetch_flights_orchestrator(
    origin_code: str,
    destination_code: str,
    departure_date: str,
    return_date: Optional[str] = None,
    travel_class: str = "ECONOMY",
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    fare_type: str = "Regular",
    promo_code: Optional[str] = None,
    non_stop: bool = False,
    preferred_provider: Optional[str] = None,
) -> Tuple[List[FlightItem], str, str]:
    """
    Multi-GDS & Aggregator routing engine:
    1. Checks Travelopro if selected or auto
    2. Checks Travelport if selected or auto
    3. Checks Amadeus Self-Service API if selected or auto
    4. Falls back seamlessly to internal flight generator
    """
    gds_provider = (preferred_provider or os.environ.get("GDS_PROVIDER", "auto")).lower().strip()
    flights: Optional[List[FlightItem]] = None
    data_source = "simulation"
    active_gds = gds_provider

    # 1. Try Travelopro API
    if gds_provider in ("travelopro", "auto"):
        travelopro = TraveloproClient()
        if travelopro.is_configured:
            try:
                tpro_results = travelopro.search_flights(
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
                    trip_type=trip_type if "trip_type" in locals() else None,
                )
                if tpro_results:
                    flights = tpro_results
                    data_source = "travelopro_live"
                    active_gds = "travelopro"
                    logger.info(f"Retrieved {len(tpro_results)} live flights from Travelopro API")
            except Exception as e:
                logger.warning(f"Travelopro flight search failed: {e}")

    # 2. Try Travelport TripServices
    if not flights and gds_provider in ("travelport", "auto"):
        travelport = TravelportClient()
        if travelport.is_configured:
            try:
                tp_results = travelport.search_flights(
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
                if tp_results:
                    flights = tp_results
                    data_source = "travelport_live"
                    active_gds = "travelport"
                    logger.info(f"Retrieved {len(tp_results)} live flights from Travelport")
            except Exception as e:
                logger.warning(f"Travelport flight search failed: {e}")

    # 3. Try Amadeus Self-Service API
    if not flights and gds_provider in ("amadeus", "auto"):
        amadeus = AmadeusClient()
        if amadeus.is_configured:
            try:
                amadeus_results = amadeus.search_flight_offers(
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
                if amadeus_results:
                    flights = amadeus_results
                    data_source = "amadeus_live"
                    active_gds = "amadeus"
                    logger.info(f"Retrieved {len(amadeus_results)} live flights from Amadeus API")
            except Exception as e:
                logger.warning(f"Amadeus flight search failed: {e}")

    # 4. Simulation is allowed only when provider routing is not explicitly Travelopro.
    if not flights and gds_provider == "travelopro":
        return [], "travelopro_unavailable", "travelopro"

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

    return flights, data_source, active_gds


@app.get("/", tags=["Health"])
def root():
    return {
        "app": "Nandi Travel Trips API",
        "version": "2.2.0",
        "status": "online",
        "supported_gds": [
            "Travelopro Flight API",
            "Amadeus Self-Service API",
            "Travelport TripServices / Universal API",
        ],
        "docs_url": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/v1/gds/status", tags=["GDS Integration"])
def gds_status():
    """
    Checks configuration and connectivity status of Travelopro, Amadeus, and Travelport integrations
    """
    travelopro = TraveloproClient()
    amadeus = AmadeusClient()
    travelport = TravelportClient()

    travelopro_status = travelopro.configuration_status()

    amadeus_status = {
        "configured": amadeus.is_configured,
        "environment": amadeus.env,
        "base_url": amadeus.base_url,
        "has_client_id": bool(amadeus.client_id),
        "has_client_secret": bool(amadeus.client_secret),
    }

    travelport_status = {
        "configured": travelport.is_configured,
        "environment": travelport.env,
        "air_service_url": travelport.air_service_url,
        "target_branch": travelport.target_branch,
        "has_credentials": bool(travelport.username and travelport.password),
    }

    current_provider = os.environ.get("GDS_PROVIDER", "auto").strip().lower()

    return {
        "status": "success",
        "active_provider_setting": current_provider,
        "providers": {
            "travelopro": travelopro_status,
            "amadeus": amadeus_status,
            "travelport": travelport_status,
        },
    }


@app.get("/api/v1/airports", response_model=List[Airport], tags=["Airports"])
def list_airports(query: Optional[str] = None):
    """
    Returns list of supported airports with optional query search
    """
    if not query:
        return [Airport(**a) for a in AIRPORTS_DB]

    q = query.strip().lower()
    filtered = [
        Airport(**a) for a in AIRPORTS_DB
        if q in a["city"].lower() or q in a["code"].lower() or q in a["airport"].lower() or q in a["country"].lower()
    ]
    return filtered


@app.get("/search-flight", tags=["Flights"])
def search_flight_compat(
    origin_code: str = Query(..., description="Origin airport code e.g. JAI, DEL"),
    destination_code: str = Query(..., description="Destination airport code e.g. BOM"),
    departure_date: str = Query(..., description="Date of departure YYYY-MM-DD"),
    return_date: Optional[str] = Query(None, description="Date of return YYYY-MM-DD"),
    trip_type: str = Query("ONEWAY", description="ONEWAY, ROUNDTRIP, MULTICITY"),
    travel_class: str = Query("ECONOMY", description="ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST"),
    adults: int = Query(1, ge=1, le=9),
    children: int = Query(0, ge=0, le=9),
    infants: int = Query(0, ge=0, le=9),
    fare_type: str = Query("Regular"),
    promo_code: Optional[str] = Query(None),
    non_stop: bool = Query(False),
    provider: Optional[str] = Query(None, description="travelport, amadeus, auto, or simulation"),
):
    """
    Primary flight search endpoint with backward compatibility and GDS support
    """
    origin_info = get_airport_by_code(origin_code)
    dest_info = get_airport_by_code(destination_code)

    flights, data_source, active_gds = fetch_flights_orchestrator(
        origin_code=origin_code,
        destination_code=destination_code,
        departure_date=departure_date,
        return_date=return_date,
        travel_class=travel_class,
        adults=adults,
        children=children,
        infants=infants,
        fare_type=fare_type,
        promo_code=promo_code,
        non_stop=non_stop,
        preferred_provider=provider,
    )

    return {
        "status": "success",
        "origin": origin_code.upper(),
        "origin_city": origin_info["city"],
        "destination": destination_code.upper(),
        "destination_city": dest_info["city"],
        "departure_date": departure_date,
        "return_date": return_date,
        "trip_type": trip_type,
        "travel_class": travel_class,
        "adults": adults,
        "children": children,
        "infants": infants,
        "fare_type": fare_type,
        "data_source": data_source,
        "gds_provider": active_gds,
        "total_results": len(flights),
        "flights": [f.model_dump() for f in flights],
    }


@app.get("/api/v1/flights/search", response_model=FlightSearchResponse, tags=["Flights"])
def search_flights_v1(
    origin_code: str = Query(...),
    destination_code: str = Query(...),
    departure_date: str = Query(...),
    return_date: Optional[str] = None,
    trip_type: str = "ONEWAY",
    travel_class: str = "ECONOMY",
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    fare_type: str = "Regular",
    promo_code: Optional[str] = None,
    non_stop: bool = False,
    sort_by: str = "cheapest",  # cheapest, fastest, earliest
    max_price: Optional[float] = None,
    provider: Optional[str] = None,
):
    origin_info = get_airport_by_code(origin_code)
    dest_info = get_airport_by_code(destination_code)

    flights, data_source, active_gds = fetch_flights_orchestrator(
        origin_code=origin_code,
        destination_code=destination_code,
        departure_date=departure_date,
        return_date=return_date,
        travel_class=travel_class,
        adults=adults,
        children=children,
        infants=infants,
        fare_type=fare_type,
        promo_code=promo_code,
        non_stop=non_stop,
        preferred_provider=provider,
    )

    if max_price:
        flights = [f for f in flights if f.final_price <= max_price]

    if sort_by == "cheapest":
        flights.sort(key=lambda x: x.final_price)
    elif sort_by == "fastest":
        flights.sort(key=lambda x: x.duration_minutes)
    elif sort_by == "earliest":
        flights.sort(key=lambda x: x.departure_time)

    return FlightSearchResponse(
        status="success",
        origin=origin_code.upper(),
        origin_city=origin_info["city"],
        destination=destination_code.upper(),
        destination_city=dest_info["city"],
        departure_date=departure_date,
        return_date=return_date,
        trip_type=trip_type,
        total_results=len(flights),
        data_source=data_source,
        gds_provider=active_gds,
        flights=flights,
    )


@app.get("/api/v1/flights/{flight_id}", response_model=FlightItem, tags=["Flights"])
def get_flight_details(
    flight_id: str,
    origin_code: str = Query("DEL"),
    destination_code: str = Query("BOM"),
    departure_date: str = Query("2026-08-25"),
):
    flights, _, _ = fetch_flights_orchestrator(
        origin_code=origin_code,
        destination_code=destination_code,
        departure_date=departure_date,
    )
    for f in flights:
        if f.id == flight_id or flight_id in f.id:
            return f
    # If not found directly, return first matching flight with updated ID
    if flights:
        f = flights[0]
        f.id = flight_id
        return f
    raise HTTPException(status_code=404, detail="Flight not found")


@app.post("/api/v1/bookings/create", response_model=BookingResponse, status_code=status.HTTP_201_CREATED, tags=["Bookings"])
def create_booking(booking: BookingRequest):
    # Retrieve flight info
    flights, _, _ = fetch_flights_orchestrator("JAI", "BOM", datetime.now().strftime("%Y-%m-%d"))
    selected_flight = flights[0]
    for f in flights:
        if f.id == booking.flight_id:
            selected_flight = f
            break

    num_passengers = max(1, len(booking.passengers))
    total_amount = round(selected_flight.final_price * num_passengers, 2)

    pnr = f"NTT{uuid.uuid4().hex[:6].upper()}"
    booking_id = f"BK_{uuid.uuid4().hex[:8]}"

    return BookingResponse(
        status="confirmed",
        booking_id=booking_id,
        pnr=pnr,
        flight=selected_flight,
        passengers=booking.passengers,
        total_amount=total_amount,
        contact_email=booking.email,
        contact_phone=booking.phone,
        booking_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
