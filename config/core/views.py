"""
Views for Nandi Travel Trips Core Application
"""
import uuid
import hashlib
import json
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from django.core.cache import cache
from django.conf import settings
from datetime import datetime, timedelta
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_http_methods
from .flight_service import search_flights_service, get_all_airports, get_flight_by_id

logger = logging.getLogger("nandi.flight")

_SEARCH_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="flight-search")
_SEARCH_LOCK = threading.Lock()
_SEARCH_JOBS = {}

def _canonical_provider_params(params):
    """Return only inputs that can change the live provider Availability result."""
    fare_type_map = {
        "regular": "Regular", "student": "Student",
        "armed forces": "Armed Force", "armed force": "Armed Force",
        "senior citizen": "Senior Citizen",
    }
    fare_type = str(params.get("fare_type") or "Regular").strip()
    fare_type = fare_type_map.get(fare_type.lower(), fare_type)
    return {
        "origin_code": str(params.get("origin_code") or "").strip().upper(),
        "destination_code": str(params.get("destination_code") or "").strip().upper(),
        "departure_date": str(params.get("departure_date") or "").strip(),
        "return_date": str(params.get("return_date") or "").strip() or None,
        "trip_type": str(params.get("trip_type") or "ONEWAY").strip().upper(),
        "travel_class": str(params.get("travel_class") or "ECONOMY").strip().upper(),
        "adults": int(params.get("adults") or 1),
        "children": int(params.get("children") or 0),
        "infants": int(params.get("infants") or 0),
        "fare_type": fare_type,
    }


def _flight_provider_cache_key(params):
    payload = json.dumps(_canonical_provider_params(params), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"flight-provider-search:v1:{digest}"


def _apply_presentation_filters(search_data, *, non_stop=False, sort_by="cheapest", max_price=None, airline_filter=None):
    """Apply UI-only filtering/sorting without another live Availability call."""
    result = dict(search_data or {})
    flights = [dict(f) for f in (result.get("flights") or [])]

    if non_stop:
        flights = [f for f in flights if int(f.get("stops", 0) or 0) == 0]
    if airline_filter:
        wanted = {str(a).strip().lower() for a in airline_filter if str(a).strip()}
        flights = [f for f in flights if str(f.get("airline", "")).lower() in wanted or str(f.get("airline_code", "")).lower() in wanted]
    if max_price is not None:
        flights = [f for f in flights if float(f.get("final_price", 0) or 0) <= float(max_price)]

    if sort_by == "fastest":
        flights.sort(key=lambda x: float(x.get("duration_minutes", 0) or 0))
    elif sort_by == "earliest":
        flights.sort(key=lambda x: str(x.get("departure_time", "")))
    else:
        flights.sort(key=lambda x: float(x.get("final_price", 0) or 0))

    result["flights"] = flights
    result["total_results"] = len(flights)
    result["available_airlines"] = sorted({str(f.get("airline", "")) for f in flights if f.get("airline")})
    prices = [float(f.get("final_price", 0) or 0) for f in flights]
    result["min_price"] = min(prices) if prices else 0
    result["max_price"] = max(prices) if prices else 0
    result["non_stop"] = bool(non_stop)
    return result


def _search_job(job_id, provider_cache_key, search_kwargs, ttl, lock_key):
    started = time.perf_counter()
    state_key = f"flight-search-job:{job_id}"
    try:
        logger.info("FLIGHT ASYNC JOB | job=%s | status=running | provider_cache_key=%s", job_id, provider_cache_key)
        result = search_flights_service(**search_kwargs)
        cache.set(provider_cache_key, result, ttl)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        state = {"status": "ready", "cache_key": provider_cache_key, "elapsed_ms": elapsed_ms, "total_results": result.get("total_results", 0)}
        cache.set(state_key, state, max(int(ttl), 60))
        with _SEARCH_LOCK:
            if job_id in _SEARCH_JOBS:
                _SEARCH_JOBS[job_id].update(state)
        cache.delete(lock_key)
        logger.info("FLIGHT ASYNC JOB | job=%s | status=ready | elapsed_ms=%s | results=%s", job_id, elapsed_ms, result.get("total_results", 0))
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        state = {"status": "error", "error": str(exc), "elapsed_ms": elapsed_ms, "cache_key": provider_cache_key}
        cache.set(state_key, state, max(int(ttl), 60))
        with _SEARCH_LOCK:
            if job_id in _SEARCH_JOBS:
                _SEARCH_JOBS[job_id].update(state)
        cache.delete(lock_key)
        logger.exception("FLIGHT ASYNC JOB | job=%s | status=error | elapsed_ms=%s", job_id, elapsed_ms)


def _start_async_search(provider_cache_key, search_kwargs, ttl, results_url):
    """Start/dedupe one provider search across Django worker processes."""
    lock_key = f"flight-search-lock:{provider_cache_key}"
    existing = cache.get(lock_key)
    if existing:
        return existing.get("job_id") if isinstance(existing, dict) else str(existing)

    job_id = uuid.uuid4().hex
    job_state = {"job_id": job_id, "status": "queued", "cache_key": provider_cache_key, "results_url": results_url}
    lock_ttl = int(getattr(settings, "FLIGHT_SEARCH_LOCK_TTL", max(int(ttl) * 3, 180)))
    if not cache.add(lock_key, {"job_id": job_id}, lock_ttl):
        existing = cache.get(lock_key)
        return existing.get("job_id") if isinstance(existing, dict) else str(existing)

    with _SEARCH_LOCK:
        _SEARCH_JOBS[job_id] = job_state.copy()
    cache.set(f"flight-search-job:{job_id}", job_state, max(int(ttl), 60))
    _SEARCH_EXECUTOR.submit(_search_job, job_id, provider_cache_key, search_kwargs, ttl, lock_key)
    with _SEARCH_LOCK:
        if job_id in _SEARCH_JOBS:
            _SEARCH_JOBS[job_id]["status"] = "running"
    cache.set(f"flight-search-job:{job_id}", {**job_state, "status": "running"}, max(int(ttl), 60))
    return job_id


def flight_search_status(request):
    job_id = request.GET.get("job_id", "").strip()
    if not job_id:
        return JsonResponse({"status": "error", "error": "Missing job_id"}, status=400)
    job = cache.get(f"flight-search-job:{job_id}")
    if not job:
        with _SEARCH_LOCK:
            job = dict(_SEARCH_JOBS.get(job_id, {}))
    if not job:
        return JsonResponse({"status": "error", "error": "Search job expired or not found"}, status=404)
    if job.get("status") == "ready":
        return JsonResponse({"status": "ready", "results_url": job.get("results_url", ""), "elapsed_ms": job.get("elapsed_ms"), "cache_key": job.get("cache_key", "")})
    if job.get("status") == "error":
        return JsonResponse({"status": "error", "error": job.get("error", "Search failed")})
    return JsonResponse({"status": job.get("status", "running")})

def home(request):
    """
    Renders the homepage flight search engine
    """
    today = datetime.now()
    default_dep = (today + timedelta(days=2)).strftime("%Y-%m-%d")
    default_ret = (today + timedelta(days=9)).strftime("%Y-%m-%d")

    context = {
        "default_origin": "JAI",
        "default_origin_city": "Jaipur",
        "default_destination": "BOM",
        "default_destination_city": "Mumbai",
        "default_departure_date": default_dep,
        "default_return_date": default_ret,
        "airports": get_all_airports(),
    }
    return render(request, "home.html", context)


def flight_results(request):
    """
    Flight search results page with interactive filters and sorting
    """
    origin_code = request.GET.get("origin_code", "JAI").strip().upper()
    destination_code = request.GET.get("destination_code", "BOM").strip().upper()

    today = datetime.now()
    default_dep = (today + timedelta(days=2)).strftime("%Y-%m-%d")
    departure_date = request.GET.get("departure_date", default_dep).strip()
    return_date = request.GET.get("return_date", "").strip()

    trip_type = request.GET.get("trip_type", "ONEWAY")
    travel_class = request.GET.get("travel_class", "ECONOMY")

    try:
        adults = int(request.GET.get("adults", 1))
    except (ValueError, TypeError):
        adults = 1

    try:
        children = int(request.GET.get("children", 0))
    except (ValueError, TypeError):
        children = 0

    try:
        infants = int(request.GET.get("infants", 0))
    except (ValueError, TypeError):
        infants = 0

    fare_type = request.GET.get("fare_type", "Regular")
    promo_code = request.GET.get("promo_code", "").strip()
    non_stop = request.GET.get("non_stop") in ("on", "true", "True", "1")

    sort_by = request.GET.get("sort_by", "cheapest")
    max_price_str = request.GET.get("max_price")
    max_price = float(max_price_str) if max_price_str else None
    
    selected_airlines = request.GET.getlist("airline")

    provider_params = {
        "origin_code": origin_code, "destination_code": destination_code,
        "departure_date": departure_date, "return_date": return_date or None,
        "trip_type": trip_type, "travel_class": travel_class,
        "adults": adults, "children": children, "infants": infants,
        "fare_type": fare_type,
    }
    provider_cache_key = _flight_provider_cache_key(provider_params)
    started = time.perf_counter()
    search_data = cache.get(provider_cache_key)
    cache_hit = search_data is not None

    # A cache miss always enters the same async/deduplicated path. There is
    # deliberately no synchronous provider call for async=1, so a refresh or
    # polling race cannot trigger a second Travelopro Availability request.
    if not cache_hit:
        search_id = uuid.uuid4().hex
        logger.info("FLIGHT SEARCH START | search_id=%s | provider_cache_key=%s | route=%s-%s | date=%s", search_id, provider_cache_key, origin_code, destination_code, departure_date)
        search_kwargs = {
            **provider_params,
            "correlation_id": search_id,
            "promo_code": None,
            "non_stop": False,
            "sort_by": "cheapest",
            "max_price": None,
            "airline_filter": None,
        }
        full_path = request.get_full_path().split("&async=1")[0].split("?async=1")[0]
        results_url = full_path + ("&" if "?" in full_path else "?") + "async=1"
        job_id = _start_async_search(provider_cache_key, search_kwargs, getattr(settings, "FLIGHT_SEARCH_CACHE_TTL", 120), results_url)
        return render(request, "flights/search-loading.html", {
            "job_id": job_id, "origin_code": origin_code, "destination_code": destination_code,
            "departure_date": departure_date, "status_url": reverse("flight_search_status"),
        })

    logger.info("FLIGHT SEARCH | cache_hit=%s | provider_cache_key=%s | route=%s-%s | date=%s", cache_hit, provider_cache_key, origin_code, destination_code, departure_date)
    search_data = _apply_presentation_filters(
        search_data,
        non_stop=non_stop,
        sort_by=sort_by,
        max_price=max_price,
        airline_filter=selected_airlines,
    )

    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    logger.info(
        "FLIGHT SEARCH | cache_hit=%s | elapsed_ms=%s | route=%s-%s | date=%s | results=%s | source=%s",
        cache_hit, elapsed_ms, origin_code, destination_code, departure_date,
        search_data.get("total_results", 0), search_data.get("data_source", "unknown")
    )

    # Store only a tiny cache key in the session. The previous implementation
    # serialized the full provider offer list into the Django session/database,
    # which is expensive for large Travelopro responses.
    request.session["flight_search_cache_key"] = provider_cache_key
    request.session["flight_search_key"] = {
        "origin": origin_code, "destination": destination_code,
        "departure_date": departure_date, "trip_type": trip_type,
    }
    request.session.modified = True

    context = {
        "search": search_data,
        "selected_sort": sort_by,
        "selected_airlines": selected_airlines,
        "all_airports": get_all_airports(),
    }
    return render(request, "flights/results.html", context)


def traveller_details(request):
    """
    Step 2: Collect passenger names and contact details
    """
    flight_id = request.GET.get("flight_id") or request.POST.get("flight_id")
    origin = request.GET.get("origin", "JAI")
    destination = request.GET.get("destination", "BOM")
    departure_date = request.GET.get("departure_date", datetime.now().strftime("%Y-%m-%d"))

    try:
        adults = int(request.GET.get("adults", 1))
    except (ValueError, TypeError):
        adults = 1

    try:
        children = int(request.GET.get("children", 0))
    except (ValueError, TypeError):
        children = 0

    try:
        infants = int(request.GET.get("infants", 0))
    except (ValueError, TypeError):
        infants = 0

    travel_class = request.GET.get("travel_class", "ECONOMY")
    fare_type = request.GET.get("fare_type", "Regular")

    cached_search = cache.get(request.session.get("flight_search_cache_key", ""), {})
    stored_flights = cached_search.get("flights", []) if isinstance(cached_search, dict) else []
    flight = get_flight_by_id(
        flight_id or "FL_DEFAULT", origin, destination, departure_date,
        stored_flights=stored_flights,
    )

    # For a live Travelopro offer, revalidate immediately after selection. This
    # confirms the current price/fare before passenger/payment work begins.
    revalidation = None
    revalidation_error = None
    if flight and flight.get("provider") == "travelopro":
        try:
            from backend.travelopro_client import TraveloproClient
            if flight.get("session_id") and flight.get("fare_source_code"):
                revalidation = TraveloproClient().revalidate(
                    session_id=flight["session_id"],
                    fare_source_code=flight["fare_source_code"],
                    fare_source_code_inbound=flight.get("fare_source_code_inbound"),
                )
        except Exception as exc:
            revalidation_error = str(exc)

    total_passengers = adults + children + infants
    adult_list = list(range(1, adults + 1))
    child_list = list(range(1, children + 1))
    infant_list = list(range(1, infants + 1))

    context = {
        "flight": flight,
        "adults": adults,
        "children": children,
        "infants": infants,
        "total_passengers": total_passengers,
        "adult_list": adult_list,
        "child_list": child_list,
        "infant_list": infant_list,
        "travel_class": travel_class,
        "fare_type": fare_type,
        "origin": origin,
        "destination": destination,
        "revalidation": revalidation,
        "revalidation_error": revalidation_error,
        "departure_date": departure_date,
    }
    return render(request, "flights/traveller-details.html", context)


@require_http_methods(["GET", "POST"])
def review_booking(request):
    """
    Step 3: Review flight itinerary, passenger details, and fare breakdown
    """
    if request.method == "POST":
        flight_id = request.POST.get("flight_id", "")
        origin = request.POST.get("origin", "JAI")
        destination = request.POST.get("destination", "BOM")
        departure_date = request.POST.get("departure_date", datetime.now().strftime("%Y-%m-%d"))
        travel_class = request.POST.get("travel_class", "ECONOMY")
        fare_type = request.POST.get("fare_type", "Regular")

        try:
            adults = int(request.POST.get("adults", 1))
        except (ValueError, TypeError):
            adults = 1
        try:
            children = int(request.POST.get("children", 0))
        except (ValueError, TypeError):
            children = 0
        try:
            infants = int(request.POST.get("infants", 0))
        except (ValueError, TypeError):
            infants = 0

        email = request.POST.get("email", "")
        phone = request.POST.get("phone", "")

        # Extract passenger data
        passengers = []
        for i in range(1, adults + 1):
            title = request.POST.get(f"adult_{i}_title", "Mr")
            first = request.POST.get(f"adult_{i}_first", f"Adult {i}")
            last = request.POST.get(f"adult_{i}_last", "Passenger")
            gender = request.POST.get(f"adult_{i}_gender", "Male")
            passengers.append({
                "type": "Adult",
                "title": title,
                "first_name": first,
                "last_name": last,
                "full_name": f"{title} {first} {last}",
                "gender": gender,
            })

        for i in range(1, children + 1):
            first = request.POST.get(f"child_{i}_first", f"Child {i}")
            last = request.POST.get(f"child_{i}_last", "Passenger")
            passengers.append({
                "type": "Child",
                "title": "Master" if request.POST.get(f"child_{i}_gender") == "Male" else "Miss",
                "first_name": first,
                "last_name": last,
                "full_name": f"{first} {last}",
                "gender": request.POST.get(f"child_{i}_gender", "Male"),
            })

        for i in range(1, infants + 1):
            first = request.POST.get(f"infant_{i}_first", f"Infant {i}")
            last = request.POST.get(f"infant_{i}_last", "Passenger")
            passengers.append({
                "type": "Infant",
                "title": "Infant",
                "first_name": first,
                "last_name": last,
                "full_name": f"{first} {last}",
                "gender": request.POST.get(f"infant_{i}_gender", "Male"),
            })

        flight = get_flight_by_id(flight_id, origin, destination, departure_date)
        total_pax = max(1, adults + children)
        base_fare = round(flight["base_price"] * total_pax, 2) if flight else 0
        taxes = round(flight["taxes"] * total_pax, 2) if flight else 0
        grand_total = round(base_fare + taxes, 2)

        context = {
            "flight": flight,
            "passengers": passengers,
            "adults": adults,
            "children": children,
            "infants": infants,
            "email": email,
            "phone": phone,
            "travel_class": travel_class,
            "fare_type": fare_type,
            "base_fare": base_fare,
            "taxes": taxes,
            "grand_total": grand_total,
        }
        return render(request, "flights/review-booking.html", context)

    # Fallback to home if accessed directly via GET
    return redirect("home")


@require_http_methods(["POST"])
def booking_success(request):
    """
    Step 4: Confirm booking, generate PNR, and display e-ticket receipt
    """
    flight_id = request.POST.get("flight_id", "FL_DEFAULT")
    origin = request.POST.get("origin", "JAI")
    destination = request.POST.get("destination", "BOM")
    departure_date = request.POST.get("departure_date", datetime.now().strftime("%Y-%m-%d"))
    email = request.POST.get("email", "support@nanditraveltrips.com")
    phone = request.POST.get("phone", "+91 98765 43210")
    grand_total = request.POST.get("grand_total", "5499.00")
    primary_passenger = request.POST.get("primary_passenger", "Mr. Rahul Sharma")

    flight = get_flight_by_id(flight_id, origin, destination, departure_date)
    pnr = f"NTT{uuid.uuid4().hex[:6].upper()}"
    booking_ref = f"BK-{uuid.uuid4().hex[:8].upper()}"
    booking_time = datetime.now().strftime("%d %b %Y, %I:%M %p")

    context = {
        "flight": flight,
        "pnr": pnr,
        "booking_ref": booking_ref,
        "booking_time": booking_time,
        "email": email,
        "phone": phone,
        "grand_total": grand_total,
        "primary_passenger": primary_passenger,
    }
    return render(request, "flights/booking-success.html", context)


def api_airports(request):
    """
    JSON API for airport autocomplete / search
    """
    q = request.GET.get("q", "").strip().lower()
    airports = get_all_airports()
    if q:
        airports = [
            a for a in airports
            if q in a["city"].lower() or q in a["code"].lower() or q in a["airport"].lower() or q in a["country"].lower()
        ]
    return JsonResponse({"status": "success", "data": airports})