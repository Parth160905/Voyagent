"""
Fares for routes Duffel's test environment doesn't cover.

Coordinates come from Duffel's place database, and the fare is a simple
distance model. Everything here is flagged price_is_estimate so the planner,
the page and the itinerary can say so.
"""

import logging
import math
from datetime import datetime, timedelta

from api_clients.duffel_client import resolve_place

logger = logging.getLogger(__name__)

# One-way economy fare per person: a fixed part plus a rate per km, by distance band.
FARE_BANDS = ((800, 22, 0.045), (2000, 25, 0.035), (6000, 45, 0.032),
              (float("inf"), 80, 0.028))
RETURN_DISCOUNT = 0.92   # a round trip costs a little less than two one-ways
CRUISE_KMH = 750


def _km_between(a, b):
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2)
    return 2 * 6371 * math.asin(min(1, math.sqrt(h)))


def _one_way_usd(km):
    for limit, base, per_km in FARE_BANDS:
        if km <= limit:
            return max(35, base + per_km * km)
    return max(35, 80 + 0.028 * km)


def _at(day, hour):
    return f"{str(day)[:10]}T{hour:02d}:00:00"


def _plus_hours(timestamp, hours):
    return (datetime.fromisoformat(timestamp) + timedelta(hours=hours)).isoformat(timespec="seconds")


def estimate_flights(origin, destination, departure_date, return_date=None, adults=1):
    """Two estimated 'offers' shaped like real ones, or [] if the airports
    can't be located."""
    start, end = resolve_place(origin), resolve_place(destination)
    if not (start and end and start.get("latitude") and end.get("latitude")):
        logger.warning("No coordinates for %s or %s, cannot estimate a fare.", origin, destination)
        return []

    km = _km_between((start["latitude"], start["longitude"]), (end["latitude"], end["longitude"]))
    per_person = _one_way_usd(km)
    legs = 2 if return_date else 1
    if return_date:
        per_person *= RETURN_DISCOUNT
    hours = km / CRUISE_KMH + 1

    flights = []
    for label, multiplier, stops, out_hour in (("Estimated direct fare", 1.0, 0, 9),
                                               ("Estimated fare with one stop", 0.85, 1, 14)):
        travel = hours + 2 * stops
        out = _at(departure_date, out_hour)
        flight = {
            "id": f"estimate_{stops}",
            "airline": label,
            "price": round(per_person * legs * multiplier * max(1, int(adults)), 2),
            "currency": "USD",
            "departure": out,
            "arrival": _plus_hours(out, travel),
            "stops": stops,
            "price_is_estimate": True,
            "distance_km": round(km),
        }
        if return_date:
            back = _at(return_date, out_hour + 2)
            flight["return_departure"] = back
            flight["return_arrival"] = _plus_hours(back, travel)
        flights.append(flight)
    return flights
