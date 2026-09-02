"""
URL Configuration for Core App
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('flights/results/', views.flight_results, name='flight_results'),
    path('flights/search-status/', views.flight_search_status, name='flight_search_status'),
    path('flights/traveller-details/', views.traveller_details, name='traveller_details'),
    path('flights/review-booking/', views.review_booking, name='review_booking'),
    path('flights/booking-success/', views.booking_success, name='booking_success'),
    path('api/airports/', views.api_airports, name='api_airports'),
]