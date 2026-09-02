# Nandi Travel Trips ✈️🌍

Comprehensive Flight Search, Booking, and Multi-GDS Travel Management Platform built with **Django** (Web UI) and **FastAPI** (High-Performance REST Backend & GDS Orchestration).

---

## 🌟 Key Features

* **Multi-GDS & Aggregator Routing Engine:**
  * **Travelopro (aeroVE5 / TravelNext REST API):** High-speed flight availability search, fare rules, and reservation management.
  * **Amadeus Self-Service API (v2):** Real-time OAuth2 token caching, flight offers search, pricing confirmation, and orders.
  * **Travelport Universal API / TripServices:** GDS air shopping, segment parsing, and PNR retrieval.
  * **Deterministic Fallback Simulation Engine:** Guarantees zero downtime by seamlessly generating realistic flight results if external APIs are unconfigured or rate-limited.
* **Full-Featured User Booking Flow (Django):**
  * Interactive homepage flight search with airport autocomplete.
  * Search results with filtering (direct/connecting, class, airlines, price slider) and sorting (cheapest, fastest, earliest).
  * Passenger details form supporting adults, children, and infants.
  * Review booking breakdown with base fare, taxes, and total pricing.
  * Booking confirmation receipt with PNR generation and e-ticket receipt.
* **Modern Developer API (FastAPI):**
  * Interactive Swagger documentation at `/docs` and ReDoc at `/redoc`.
  * Integration health check & status endpoint (`/api/v1/gds/status`).
  * Strict validation with Pydantic v2 schemas.

---

## 📁 Project Structure

```
NandiTravelTrips/
├── backend/                  # FastAPI Application & GDS Integration Clients
│   ├── main.py               # FastAPI entry point & flight orchestrator
│   ├── schemas.py            # Pydantic data schemas
│   ├── amadeus_client.py     # Amadeus Self-Service API Client
│   ├── travelport_client.py  # Travelport Universal API Client
│   ├── travelopro_client.py  # Travelopro / aeroVE5 API Client
│   ├── flights_data.py       # Airport DB & fallback generator
│   └── test_api.py           # API unit & integration tests
│
├── config/                   # Django Web Portal
│   ├── config/               # Django project settings & URLs
│   ├── core/                 # Core travel views, templates, static assets
│   │   ├── templates/        # Responsive HTML5 templates
│   │   ├── static/           # CSS, JavaScript & Images
│   │   ├── flight_service.py # Service layer with multi-GDS routing
│   │   └── tests.py          # Django core test suite
│   └── manage.py             # Django CLI
│
├── .env.example              # Environment variables template
├── requirements.txt          # Python dependencies
└── .gitignore                # Git ignore rules
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
* Python 3.10+ installed
* Git installed

### 2. Setup Virtual Environment & Dependencies
```powershell
# Clone repository
git clone https://github.com/ramesh76in/NandiTravelTrips.git
cd NandiTravelTrips

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1   # On Linux/macOS: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and set your credentials (or leave defaults to run in simulation mode):
```powershell
cp .env.example .env
```

### 4. Run the Application

#### Option A: Run Django Web Portal (Frontend Booking Site)
```powershell
python config/manage.py runserver
```
Visit: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

#### Option B: Run FastAPI Backend (REST API & Swagger Docs)
```powershell
uvicorn backend.main:app --reload --port 8001
```
* **Swagger UI:** [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)
* **GDS Status Check:** [http://127.0.0.1:8001/api/v1/gds/status](http://127.0.0.1:8001/api/v1/gds/status)

---

## 🧪 Running Tests

* **Run Backend Unit Tests:**
  ```powershell
  python -m unittest backend.test_api
  ```
* **Run Django Core Tests:**
  ```powershell
  python config/manage.py test core
  ```

---

## 🔒 Security Note
Never commit the `.env` file to version control. Always keep API keys, passwords, and tokens in `.env` (which is included in `.gitignore`). Use `.env.example` for sharing configuration schemas.
