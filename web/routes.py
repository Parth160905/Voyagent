"""
Public routes: the planner web page and the JSON API behind it.

The planner calls APIs with quotas and costs (Places, Gemini), so every
request is validated and rate limited before the graph runs.
"""

import logging
import os
import threading
import time
from collections import defaultdict, deque
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from api_clients.airports import CITY_AIRPORTS, resolve_airport
from api_clients.duffel_client import suggest_places
from graph import voyagent_graph

logger = logging.getLogger(__name__)
router = APIRouter()

INDEX_HTML = Path(__file__).parent / "index.html"

PER_IP_PER_HOUR = int(os.getenv("PER_IP_PLANS_PER_HOUR", "5"))
PLANS_PER_DAY = int(os.getenv("DAILY_PLAN_LIMIT", "100"))
MAX_NIGHTS = 14
CURRENCIES = {"USD", "GBP", "EUR", "INR", "AED", "SGD", "JPY", "AUD", "CAD"}

_lock = threading.Lock()
_hits_by_ip = defaultdict(deque)
_today = {"date": None, "count": 0}


class PlanRequest(BaseModel):
    origin: str = Field(min_length=2, max_length=60, description="City or airport, e.g. Lucknow or LKO")
    destination: str = Field(min_length=2, max_length=60, description="City or airport, e.g. Delhi or DEL")
    city: str = Field(default="", max_length=60, description="City to explore; defaults to the destination")
    departure_date: date
    return_date: date
    travelers: int = Field(default=1, ge=1, le=9, description="Number of people on the trip")
    budget_total: float = Field(gt=0, le=1_000_000)
    budget_currency: str = "USD"

    @field_validator("budget_currency")
    @classmethod
    def _clean_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value.isalpha():
            raise ValueError("Use letters only, like LHR or USD.")
        return value

    @model_validator(mode="after")
    def _check_trip(self):
        if self.budget_currency not in CURRENCIES:
            raise ValueError(f"Currency must be one of: {', '.join(sorted(CURRENCIES))}.")
        if self.origin == self.destination:
            raise ValueError("Origin and destination airports must be different.")
        today = date.today()
        if self.departure_date <= today:
            raise ValueError("Departure date must be in the future.")
        if self.departure_date > today + timedelta(days=330):
            raise ValueError("Departure date must be within the next 11 months.")
        nights = (self.return_date - self.departure_date).days
        if nights < 1:
            raise ValueError("Return date must be after the departure date.")
        if nights > MAX_NIGHTS:
            raise ValueError(f"Trips are limited to {MAX_NIGHTS} nights.")
        return self


def _client_ip(request: Request) -> str:
    # Behind Render's proxy the real client IP is the first X-Forwarded-For entry.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _enforce_limits(ip: str) -> None:
    now = time.time()
    with _lock:
        if _today["date"] != date.today():
            _today.update(date=date.today(), count=0)
        if _today["count"] >= PLANS_PER_DAY:
            raise HTTPException(429, "The planner has hit today's limit. Try again tomorrow.")

        hits = _hits_by_ip[ip]
        while hits and now - hits[0] > 3600:
            hits.popleft()
        if len(hits) >= PER_IP_PER_HOUR:
            raise HTTPException(429, f"You can plan {PER_IP_PER_HOUR} trips per hour. Try again later.")

        hits.append(now)
        _today["count"] += 1


def _pick(d, *keys):
    return {k: (d or {}).get(k) for k in keys} if d else None


@router.get("/", include_in_schema=False)
def planner_page():
    return FileResponse(INDEX_HTML)


@router.get("/api/places")
def place_suggestions(q: str = ""):
    """Autocomplete for the From and To boxes: any airport or city worldwide."""
    query = (q or "").strip()
    if len(query) < 2:
        return {"places": []}

    seen, out = set(), []
    for name, code in CITY_AIRPORTS.items():      # popular cities first, no API call
        if name.startswith(query.lower()) and code not in seen:
            seen.add(code)
            out.append({"label": f"{name.title()} ({code})"})
        if len(out) >= 5:
            break
    try:
        for place in suggest_places(query, limit=8):
            if place["iata_code"] in seen:
                continue
            seen.add(place["iata_code"])
            city = place.get("city_name") or place.get("name")
            out.append({"label": f"{city} ({place['iata_code']})"})
    except Exception as exc:
        logger.warning("Place lookup failed: %r", exc)
    return {"places": out[:10]}


@router.post("/api/plan")
def plan_trip(req: PlanRequest, request: Request):
    _enforce_limits(_client_ip(request))

    state = {
        "origin": req.origin,
        "destination": req.destination,
        # Hotel and activity search look in this place, so a city name works best.
        "destination_city_code": req.city.strip(),
        "departure_date": req.departure_date.isoformat(),
        "return_date": req.return_date.isoformat(),
        "travelers": req.travelers,
        "budget_total": req.budget_total,
        "budget_currency": req.budget_currency,
        "flight_results": None,
        "hotel_results": None,
        "activity_results": None,
        "final_itinerary": None,
    }
    try:
        result = voyagent_graph.invoke(state)
    except Exception:
        logger.exception("Planner crashed")
        raise HTTPException(500, "Planning failed on our side. Try again in a minute.")

    if not (result.get("flight_results") or []):
        raise HTTPException(422, (
            f"No flights found from {req.origin} to {req.destination} on those dates. "
            "This demo runs on Duffel's test data, which mainly covers major international "
            "routes. Try one of the examples under the form."))
    if not (result.get("hotel_results") or []):
        raise HTTPException(422, f"No hotels found in {req.city}. Try a nearby larger city.")

    return {
        "itinerary": result.get("final_itinerary"),
        "budget_status": result.get("budget_status"),
        "budget_note": result.get("budget_note"),
        "budget_breakdown": result.get("budget_breakdown"),
        "travelers": req.travelers,
        "flight": _pick(result.get("selected_flight"), "airline", "departure", "arrival",
                        "return_departure", "return_arrival", "stops",
                        "cost_in_budget_currency"),
        "hotel": _pick(result.get("selected_hotel"), "name", "address", "rating", "nights",
                       "total_cost_in_budget_currency", "price_is_estimate"),
        "activities": [{"name": a.get("name"), "estimated_cost": a.get("estimated_cost")}
                       for a in result.get("selected_activities") or []],
    }
