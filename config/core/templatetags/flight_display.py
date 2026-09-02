from datetime import datetime
from django import template

register = template.Library()

_DATETIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
)

def _parse(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Handle ISO values ending in Z or with a timezone offset.
    candidate = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        pass
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None

@register.filter
def flight_time(value):
    """Render provider datetime/time in a customer-friendly 12-hour format."""
    dt = _parse(value)
    if dt:
        return dt.strftime("%I:%M %p").lstrip("0")
    text = str(value or "").strip()
    # Provider may return a time-only HH:MM[:SS].
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime("%I:%M %p").lstrip("0")
        except ValueError:
            continue
    return text

@register.filter
def flight_date(value):
    """Render a flight date as e.g. 4 Sep 2026."""
    dt = _parse(value)
    if dt:
        return f"{dt.strftime('%d').lstrip('0')} {dt.strftime('%b %Y')}"
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(text, fmt)
            return f"{dt.strftime('%d').lstrip('0')} {dt.strftime('%b %Y')}"
        except ValueError:
            continue
    return text

@register.filter
def flight_datetime(value):
    """Render a full provider datetime as e.g. 4 Sep 2026, 5:30 AM."""
    dt = _parse(value)
    if dt:
        return f"{dt.strftime('%d').lstrip('0')} {dt.strftime('%b %Y')}, {dt.strftime('%I:%M %p').lstrip('0')}"
    return str(value or "").strip()

@register.filter
def flight_date_with_offset(value, departure_value=None):
    """Display arrival date with +1 when it is on a later calendar day."""
    arr = _parse(value)
    dep = _parse(departure_value)
    if arr:
        label = f"{arr.strftime('%d').lstrip('0')} {arr.strftime('%b %Y')}"
        if dep and arr.date() > dep.date():
            label += " +1"
        return label
    return str(value or "").strip()
