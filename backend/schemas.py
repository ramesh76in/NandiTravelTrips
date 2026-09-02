"""
Pydantic Schemas for Nandi Travel Trips API
"""
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class Airport(BaseModel):
    code: str
    city: str
    airport: str
    country: str


class PriceBreakdown(BaseModel):
    base_fare: float
    taxes_and_fees: float
    discount: float = 0.0
    final_price: float
    currency: str = "INR"


class FlightSegment(BaseModel):
    airline: str
    airline_code: str
    flight_number: str
    origin: str
    origin_city: str
    destination: str
    destination_city: str
    departure_time: str
    arrival_time: str
    duration: str
    duration_minutes: int
    aircraft: str = "Boeing 737 / Airbus A320"


class FlightItem(BaseModel):
    id: str
    airline: str
    airline_code: str
    flight_number: str
    origin: str
    origin_city: str
    destination: str
    destination_city: str
    departure_time: str
    arrival_time: str
    duration: str
    duration_minutes: int
    stops: int = 0
    stop_cities: List[str] = []
    travel_class: str = "ECONOMY"
    seats_available: int = 9
    refundable: bool = True
    baggage_cabin: str = "7 Kg"
    baggage_checkin: str = "15 Kg"
    base_price: float
    taxes: float
    final_price: float
    segments: List[FlightSegment] = []
    provider: str = "simulation"
    session_id: Optional[str] = None
    fare_source_code: Optional[str] = None
    fare_source_code_inbound: Optional[str] = None
    validating_airline_code: Optional[str] = None
    ticket_type: Optional[str] = None
    passport_mandatory: bool = False
    required_fields_to_book: List[Any] = []
    fare_type: Optional[str] = None
    res_book_desig_code: Optional[str] = None
    cabin_class_code: Optional[str] = None
    cabin_class_text: Optional[str] = None


class FlightSearchRequest(BaseModel):
    origin_code: str = Field(..., min_length=3, max_length=4)
    destination_code: str = Field(..., min_length=3, max_length=4)
    departure_date: str
    return_date: Optional[str] = None
    trip_type: str = "ONEWAY"
    travel_class: str = "ECONOMY"
    adults: int = Field(default=1, ge=1, le=9)
    children: int = Field(default=0, ge=0, le=9)
    infants: int = Field(default=0, ge=0, le=9)
    fare_type: str = "Regular"
    promo_code: Optional[str] = None
    non_stop: bool = False
    max_price: Optional[float] = None
    airlines: Optional[List[str]] = None
    sort_by: str = "cheapest"  # cheapest, fastest, earliest


class FlightSearchResponse(BaseModel):
    status: str = "success"
    origin: str
    origin_city: str
    destination: str
    destination_city: str
    departure_date: str
    return_date: Optional[str] = None
    trip_type: str
    total_results: int
    data_source: Optional[str] = "simulation"
    gds_provider: Optional[str] = "auto"
    flights: List[FlightItem]


class Passenger(BaseModel):
    title: str = "Mr"
    first_name: str
    last_name: str
    gender: str = "Male"
    date_of_birth: Optional[str] = None
    passport_number: Optional[str] = None
    passenger_type: str = "adult"  # adult, child, infant


class BookingRequest(BaseModel):
    flight_id: str
    passengers: List[Passenger]
    email: str
    phone: str
    fare_type: str = "Regular"
    promo_code: Optional[str] = None


class BookingResponse(BaseModel):
    status: str = "confirmed"
    booking_id: str
    pnr: str
    flight: FlightItem
    passengers: List[Passenger]
    total_amount: float
    contact_email: str
    contact_phone: str
    booking_date: str
