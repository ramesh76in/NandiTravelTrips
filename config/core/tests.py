"""
Comprehensive Unit and Integration Tests for Nandi Travel Trips Django App
"""
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from core.flight_service import search_flights_service, get_all_airports, get_flight_by_id
from backend.schemas import FlightItem, FlightSegment


class CoreViewsTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_home_page_renders_successfully(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')
        self.assertIn('default_origin', response.context)
        self.assertEqual(response.context['default_origin'], 'JAI')
        self.assertContains(response, 'Nandi Travel Trips')
        self.assertContains(response, 'Jaipur')
        self.assertContains(response, 'Mumbai')

    def test_flight_results_default(self):
        response = self.client.get(reverse('flight_results'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'flights/results.html')
        self.assertIn('search', response.context)
        search_data = response.context['search']
        self.assertEqual(search_data['origin_code'], 'JAI')
        self.assertEqual(search_data['destination_code'], 'BOM')
        self.assertGreater(len(search_data['flights']), 0)

    def test_flight_results_filtered(self):
        url = reverse('flight_results') + '?origin_code=DEL&destination_code=BLR&departure_date=2026-08-28&adults=2&non_stop=true&sort_by=cheapest'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        search_data = response.context['search']
        self.assertEqual(search_data['origin_code'], 'DEL')
        self.assertEqual(search_data['destination_code'], 'BLR')
        self.assertEqual(search_data['adults'], 2)
        for flight in search_data['flights']:
            self.assertEqual(flight['stops'], 0)

    def test_traveller_details_get(self):
        url = reverse('traveller_details') + '?flight_id=FL_TEST_1&origin=DEL&destination=BOM&adults=2&children=1&infants=1'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'flights/traveller-details.html')
        self.assertEqual(response.context['adults'], 2)
        self.assertEqual(response.context['children'], 1)
        self.assertEqual(response.context['infants'], 1)
        self.assertEqual(response.context['total_passengers'], 4)

    def test_review_booking_post(self):
        payload = {
            'flight_id': 'FL_TEST_1',
            'origin': 'JAI',
            'destination': 'BOM',
            'departure_date': '2026-08-25',
            'travel_class': 'ECONOMY',
            'adults': 1,
            'children': 0,
            'infants': 0,
            'email': 'customer@example.com',
            'phone': '+91 98765 43210',
            'adult_1_title': 'Mr',
            'adult_1_first': 'Ramesh',
            'adult_1_last': 'Kumar',
            'adult_1_gender': 'Male',
        }
        response = self.client.post(reverse('review_booking'), data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'flights/review-booking.html')
        self.assertIn('passengers', response.context)
        self.assertEqual(len(response.context['passengers']), 1)
        self.assertEqual(response.context['passengers'][0]['first_name'], 'Ramesh')
        self.assertGreater(response.context['grand_total'], 0)

    def test_review_booking_get_redirects_to_home(self):
        response = self.client.get(reverse('review_booking'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))

    def test_booking_success_post(self):
        payload = {
            'flight_id': 'FL_TEST_1',
            'origin': 'JAI',
            'destination': 'BOM',
            'departure_date': '2026-08-25',
            'email': 'customer@example.com',
            'phone': '+91 98765 43210',
            'grand_total': '4850.00',
            'primary_passenger': 'Mr. Ramesh Kumar',
        }
        response = self.client.post(reverse('booking_success'), data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'flights/booking-success.html')
        self.assertIn('pnr', response.context)
        self.assertTrue(response.context['pnr'].startswith('NTT'))
        self.assertContains(response, 'Booking Confirmed!')

    def test_api_airports_endpoint(self):
        response = self.client.get(reverse('api_airports'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertGreaterEqual(len(data['data']), 10)

    def test_api_airports_search_filter(self):
        response = self.client.get(reverse('api_airports') + '?q=delhi')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['code'], 'DEL')


class FlightServiceTest(TestCase):
    def test_search_flights_service(self):
        res = search_flights_service(
            origin_code='JAI',
            destination_code='BOM',
            departure_date='2026-08-25',
            adults=1
        )
        self.assertEqual(res['origin_code'], 'JAI')
        self.assertEqual(res['destination_code'], 'BOM')
        self.assertGreater(len(res['flights']), 0)
        for f in res['flights']:
            self.assertIn('airline', f)
            self.assertIn('final_price', f)

    def test_flight_service_sort_fastest(self):
        res = search_flights_service(
            origin_code='JAI',
            destination_code='BOM',
            departure_date='2026-08-25',
            sort_by='fastest'
        )
        durations = [f['duration_minutes'] for f in res['flights']]
        self.assertEqual(durations, sorted(durations))

    def test_get_flight_by_id(self):
        flight = get_flight_by_id('FL_JAI_BOM_0_123', 'JAI', 'BOM', '2026-08-25')
        self.assertIsNotNone(flight)
        self.assertIn('airline', flight)

    @patch('backend.travelport_client.TravelportClient.is_configured', True)
    @patch('backend.travelport_client.TravelportClient.search_flights')
    def test_flight_service_travelport_provider(self, mock_search):
        mock_flight = FlightItem(
            id='TP_TEST_1',
            airline='Air India',
            airline_code='AI',
            flight_number='AI-631',
            origin='JAI',
            origin_city='Jaipur',
            destination='BOM',
            destination_city='Mumbai',
            departure_time='07:00',
            arrival_time='09:00',
            duration='2h 00m',
            duration_minutes=120,
            stops=0,
            travel_class='ECONOMY',
            seats_available=8,
            refundable=True,
            baggage_cabin='7 Kg',
            baggage_checkin='15 Kg',
            base_price=4500.0,
            taxes=500.0,
            final_price=5000.0,
            segments=[]
        )
        mock_search.return_value = [mock_flight]

        res = search_flights_service('JAI', 'BOM', '2026-08-25', adults=1)
        self.assertEqual(res['data_source'], 'travelport_live')
        self.assertEqual(len(res['flights']), 1)
        self.assertEqual(res['flights'][0]['airline'], 'Air India')

    @patch('backend.travelopro_client.TraveloproClient.is_configured', True)
    @patch('backend.travelopro_client.TraveloproClient.search_flights')
    def test_flight_service_travelopro_provider(self, mock_search):
        mock_flight = FlightItem(
            id='TPRO_TEST_1',
            airline='IndiGo',
            airline_code='6E',
            flight_number='6E-512',
            origin='JAI',
            origin_city='Jaipur',
            destination='BOM',
            destination_city='Mumbai',
            departure_time='10:00',
            arrival_time='12:15',
            duration='2h 15m',
            duration_minutes=135,
            stops=0,
            travel_class='ECONOMY',
            seats_available=6,
            refundable=True,
            baggage_cabin='7 Kg',
            baggage_checkin='15 Kg',
            base_price=4200.0,
            taxes=600.0,
            final_price=4800.0,
            segments=[]
        )
        mock_search.return_value = [mock_flight]

        res = search_flights_service('JAI', 'BOM', '2026-08-25', adults=1)
        self.assertEqual(res['data_source'], 'travelopro_live')
        self.assertEqual(len(res['flights']), 1)
        self.assertEqual(res['flights'][0]['airline'], 'IndiGo')



class FlightDisplayFilterTests(TestCase):
    def test_flight_time_12_hour_format(self):
        from config.core.templatetags.flight_display import flight_time
        self.assertEqual(flight_time("2026-09-04T05:30:00"), "5:30 AM")
        self.assertEqual(flight_time("2026-09-04T17:45:00"), "5:45 PM")
        self.assertEqual(flight_time("23:05:00"), "11:05 PM")

    def test_flight_date_format(self):
        from config.core.templatetags.flight_display import flight_date
        self.assertEqual(flight_date("2026-09-04"), "4 Sep 2026")


    def test_flight_date_is_windows_compatible(self):
        from config.core.templatetags.flight_display import flight_date
        self.assertEqual(flight_date("2026-09-05"), "5 Sep 2026")
        self.assertEqual(flight_date("2026-09-15"), "15 Sep 2026")
