"""
Unit and Integration Tests for Nandi Travel Trips API, Amadeus & Travelport Integration
"""
import unittest
from fastapi.testclient import TestClient
from backend.main import app
from backend.amadeus_client import AmadeusClient, parse_iso_duration
from backend.travelport_client import TravelportClient, parse_duration_minutes
from backend.travelopro_client import TraveloproClient, parse_duration_string


class TestNandiTravelAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_root_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "online")
        self.assertIn("version", data)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")

    def test_airports_endpoint(self):
        response = self.client.get("/api/v1/airports")
        self.assertEqual(response.status_code, 200)
        airports = response.json()
        self.assertGreaterEqual(len(airports), 10)
        codes = [a["code"] for a in airports]
        self.assertIn("DEL", codes)
        self.assertIn("BOM", codes)
        self.assertIn("JAI", codes)

    def test_airports_query_filter(self):
        response = self.client.get("/api/v1/airports?query=jaipur")
        self.assertEqual(response.status_code, 200)
        results = response.json()
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["code"], "JAI")

    def test_flight_search_compat(self):
        response = self.client.get(
            "/search-flight?origin_code=JAI&destination_code=BOM&departure_date=2026-08-25&adults=2"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["origin"], "JAI")
        self.assertEqual(data["destination"], "BOM")
        self.assertEqual(data["adults"], 2)
        self.assertGreater(len(data["flights"]), 0)
        first_flight = data["flights"][0]
        self.assertIn("airline", first_flight)
        self.assertIn("final_price", first_flight)

    def test_flight_search_v1_filters(self):
        response = self.client.get(
            "/api/v1/flights/search?origin_code=DEL&destination_code=BLR&departure_date=2026-08-28&travel_class=BUSINESS&non_stop=true&sort_by=cheapest"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        for flight in data["flights"]:
            self.assertEqual(flight["stops"], 0)
            self.assertEqual(flight["travel_class"], "BUSINESS")

    def test_booking_creation(self):
        booking_payload = {
            "flight_id": "FL_JAI_BOM_0_123",
            "passengers": [
                {
                    "title": "Mr",
                    "first_name": "Rahul",
                    "last_name": "Sharma",
                    "gender": "Male",
                    "passenger_type": "adult"
                }
            ],
            "email": "rahul.sharma@example.com",
            "phone": "+919876543210",
            "fare_type": "Regular"
        }
        response = self.client.post("/api/v1/bookings/create", json=booking_payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "confirmed")
        self.assertTrue(data["pnr"].startswith("NTT"))
        self.assertEqual(len(data["passengers"]), 1)


    def test_gds_status_endpoint(self):
        response = self.client.get("/api/v1/gds/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("providers", data)
        self.assertIn("amadeus", data["providers"])
        self.assertIn("travelport", data["providers"])

    def test_flight_search_v1_gds_fields(self):
        response = self.client.get(
            "/api/v1/flights/search?origin_code=DEL&destination_code=BLR&departure_date=2026-08-28&provider=simulation"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("data_source", data)
        self.assertIn("gds_provider", data)


class TestAmadeusClient(unittest.TestCase):
    def test_parse_iso_duration(self):
        formatted, mins = parse_iso_duration("PT2H15M")
        self.assertEqual(formatted, "2h 15m")
        self.assertEqual(mins, 135)

        formatted_h, mins_h = parse_iso_duration("PT1H")
        self.assertEqual(formatted_h, "1h")
        self.assertEqual(mins_h, 60)

        formatted_m, mins_m = parse_iso_duration("PT45M")
        self.assertEqual(formatted_m, "45m")
        self.assertEqual(mins_m, 45)

    def test_amadeus_unconfigured_behavior(self):
        client = AmadeusClient(client_id="", client_secret="")
        self.assertFalse(client.is_configured)
        self.assertIsNone(client.get_access_token())
        self.assertIsNone(client.search_flight_offers("DEL", "BOM", "2026-08-25"))
        self.assertIsNone(client.confirm_flight_price({}))
        self.assertIsNone(client.create_flight_order({}, []))
        self.assertIsNone(client.search_locations("DEL"))

    def test_parse_amadeus_mock_json(self):
        sample_amadeus_response = {
            "data": [
                {
                    "id": "1",
                    "numberOfBookableSeats": 5,
                    "itineraries": [
                        {
                            "duration": "PT2H10M",
                            "segments": [
                                {
                                    "departure": {"iataCode": "DEL", "at": "2026-08-25T06:00:00"},
                                    "arrival": {"iataCode": "BOM", "at": "2026-08-25T08:10:00"},
                                    "carrierCode": "6E",
                                    "number": "205",
                                    "duration": "PT2H10M",
                                    "aircraft": {"code": "32N"}
                                }
                            ]
                        }
                    ],
                    "price": {
                        "currency": "INR",
                        "total": "4500.00",
                        "base": "4000.00",
                        "grandTotal": "4500.00"
                    },
                    "travelerPricings": [
                        {
                            "fareDetailsBySegment": [
                                {
                                    "includedCheckedBags": {"weight": 15, "weightUnit": "KG"}
                                }
                            ]
                        }
                    ]
                }
            ],
            "dictionaries": {
                "carriers": {
                    "6E": "INDIGO"
                }
            }
        }

        client = AmadeusClient(client_id="test_key", client_secret="test_secret")
        parsed = client.parse_amadeus_response(sample_amadeus_response)
        self.assertEqual(len(parsed), 1)
        flight = parsed[0]
        self.assertEqual(flight.airline, "Indigo")
        self.assertEqual(flight.flight_number, "6E-205")
        self.assertEqual(flight.origin, "DEL")
        self.assertEqual(flight.destination, "BOM")
        self.assertEqual(flight.departure_time, "06:00")
        self.assertEqual(flight.arrival_time, "08:10")
        self.assertEqual(flight.duration, "2h 10m")
        self.assertEqual(flight.stops, 0)
        self.assertEqual(flight.final_price, 4500.0)
        self.assertEqual(flight.baggage_checkin, "15 KG")


class TestTravelportClient(unittest.TestCase):
    def test_parse_duration_minutes(self):
        formatted, mins = parse_duration_minutes("135")
        self.assertEqual(formatted, "2h 15m")
        self.assertEqual(mins, 135)

        formatted_iso, mins_iso = parse_duration_minutes("PT1H45M")
        self.assertEqual(formatted_iso, "1h 45m")
        self.assertEqual(mins_iso, 105)

    def test_travelport_unconfigured_behavior(self):
        client = TravelportClient(username="", password="", target_branch="")
        self.assertFalse(client.is_configured)
        self.assertIsNone(client.search_flights("DEL", "BOM", "2026-08-25"))
        self.assertIsNone(client.retrieve_trip("123456"))

    def test_parse_travelport_mock_json(self):
        sample_travelport_response = {
            "airPricingSolution": [
                {
                    "key": "TP_SOL_1",
                    "totalPrice": "INR5200.00",
                    "basePrice": "INR4600.00",
                    "approximateTaxes": "INR600.00",
                    "totalTravelTime": "125",
                    "seatsAvailable": 9,
                    "refundable": True,
                    "baggageAllowance": "15 Kg",
                    "airSegment": [
                        {
                            "carrier": "AI",
                            "carrierName": "Air India",
                            "flightNumber": "631",
                            "origin": "JAI",
                            "destination": "BOM",
                            "departureTime": "2026-08-25T07:15:00",
                            "arrivalTime": "2026-08-25T09:20:00",
                            "flightTime": "125",
                            "equipment": "Airbus A320"
                        }
                    ]
                }
            ]
        }

        client = TravelportClient(
            username="test_user", password="test_password", target_branch="P7123456"
        )
        self.assertTrue(client.is_configured)
        parsed = client.parse_travelport_response(sample_travelport_response, "ECONOMY")
        self.assertEqual(len(parsed), 1)
        flight = parsed[0]
        self.assertEqual(flight.airline, "Air India")
        self.assertEqual(flight.flight_number, "AI-631")
        self.assertEqual(flight.origin, "JAI")
        self.assertEqual(flight.destination, "BOM")
        self.assertEqual(flight.departure_time, "07:15")
        self.assertEqual(flight.arrival_time, "09:20")
        self.assertEqual(flight.duration, "2h 5m")
        self.assertEqual(flight.stops, 0)
        self.assertEqual(flight.final_price, 5200.0)
        self.assertEqual(flight.baggage_checkin, "15 Kg")


class TestTraveloproClient(unittest.TestCase):
    def test_parse_duration_string(self):
        formatted, mins = parse_duration_string("145")
        self.assertEqual(formatted, "2h 25m")
        self.assertEqual(mins, 145)

        formatted_hhmm, mins_hhmm = parse_duration_string("02:30")
        self.assertEqual(formatted_hhmm, "2h 30m")
        self.assertEqual(mins_hhmm, 150)

        formatted_iso, mins_iso = parse_duration_string("PT1H50M")
        self.assertEqual(formatted_iso, "1h 50m")
        self.assertEqual(mins_iso, 110)

    def test_travelopro_unconfigured_behavior(self):
        client = TraveloproClient(api_key="")
        self.assertFalse(client.is_configured)
        self.assertIsNone(client.search_flights("DEL", "BOM", "2026-08-25"))
        self.assertIsNone(client.get_fare_rules("test_token"))
        self.assertIsNone(client.create_booking("test_token", [], {}))

    def test_parse_travelopro_mock_json(self):
        sample_travelopro_response = {
            "status": "success",
            "data": [
                {
                    "result_token": "TPRO_TOK_1",
                    "airline_code": "6E",
                    "airline_name": "IndiGo",
                    "flight_number": "6E-512",
                    "origin": "DEL",
                    "destination": "BOM",
                    "departure_time": "2026-08-25T10:00:00",
                    "arrival_time": "2026-08-25T12:15:00",
                    "duration": "135",
                    "price": {
                        "base": 4200.0,
                        "taxes": 600.0,
                        "total": 4800.0
                    },
                    "seats_available": 6,
                    "refundable": True,
                    "cabin_baggage": "7 Kg",
                    "checkin_baggage": "15 Kg",
                    "segments": [
                        {
                            "carrier_code": "6E",
                            "carrier_name": "IndiGo",
                            "flight_number": "512",
                            "origin": "DEL",
                            "destination": "BOM",
                            "departure_time": "2026-08-25T10:00:00",
                            "arrival_time": "2026-08-25T12:15:00",
                            "duration": "135",
                            "aircraft": "Airbus A320neo"
                        }
                    ]
                }
            ]
        }

        client = TraveloproClient(api_key="test_key", api_secret="test_secret")
        self.assertTrue(client.is_configured)
        parsed = client.parse_travelopro_response(sample_travelopro_response, "ECONOMY")
        self.assertEqual(len(parsed), 1)
        flight = parsed[0]
        self.assertEqual(flight.airline, "Indigo")
        self.assertEqual(flight.flight_number, "6E-512")
        self.assertEqual(flight.origin, "DEL")
        self.assertEqual(flight.destination, "BOM")
        self.assertEqual(flight.departure_time, "10:00")
        self.assertEqual(flight.arrival_time, "12:15")
        self.assertEqual(flight.duration, "2h 15m")
        self.assertEqual(flight.stops, 0)
        self.assertEqual(flight.final_price, 4800.0)
        self.assertEqual(flight.baggage_checkin, "15 Kg")
        self.assertTrue(flight.id.startswith("TPRO_"))


if __name__ == "__main__":
    unittest.main()
