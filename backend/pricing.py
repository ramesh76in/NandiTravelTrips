"""Nandi Travel Trips flight pricing engine.

Provider fare/taxes are kept intact. Nandi markup is applied to provider base fare,
and GST is calculated on (provider base fare + Nandi markup). Provider taxes are
passed through separately. This keeps the provider's tax components distinct from
Nandi's own taxable service amount.
"""
import os
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional


def _money(value: Any) -> float:
    try:
        return float(Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except Exception:
        return 0.0


def _rate(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        return default


def calculate_flight_price(
    provider_base_fare: float,
    provider_taxes: float,
    *,
    markup_percent: Optional[float] = None,
    gst_percent: Optional[float] = None,
) -> Dict[str, float]:
    """Return a transparent customer price breakdown.

    Formula:
      provider total = base + provider taxes
      Nandi markup = base * markup%
      GST = (base + markup) * GST%
      customer total = provider taxes + base + markup + GST
    """
    base = _money(provider_base_fare)
    provider_tax = _money(provider_taxes)
    markup_rate = _rate("FLIGHT_MARKUP_PERCENT", 5.0) if markup_percent is None else max(0.0, float(markup_percent))
    gst_rate = _rate("FLIGHT_GST_RATE", 18.0) if gst_percent is None else max(0.0, float(gst_percent))

    markup = _money(base * markup_rate / 100.0)
    taxable_service_value = _money(base + markup)
    gst = _money(taxable_service_value * gst_rate / 100.0)
    provider_total = _money(base + provider_tax)
    customer_total = _money(provider_total + markup + gst)

    return {
        "provider_base_fare": base,
        "provider_taxes": provider_tax,
        "provider_total_fare": provider_total,
        "markup_percent": markup_rate,
        "markup_amount": markup,
        "taxable_service_value": taxable_service_value,
        "gst_percent": gst_rate,
        "gst_amount": gst,
        "customer_total_fare": customer_total,
        "customer_savings_vs_provider_plus_tax": 0.0,
    }


def apply_flight_pricing(flight: Dict[str, Any]) -> Dict[str, Any]:
    """Add Nandi pricing fields while preserving provider fields."""
    breakdown = calculate_flight_price(
        flight.get("base_price", 0),
        flight.get("taxes", 0),
    )
    flight = dict(flight)
    flight.update(breakdown)
    # final_price is the customer-facing amount throughout the app.
    flight["final_price"] = breakdown["customer_total_fare"]
    return flight
