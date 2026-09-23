"""
Estimated fares for routes Duffel's test environment doesn't cover.

Airport coordinates come from Google Places (cached per run), and the fare is a
simple distance band model. Anything produced here is flagged price_is_estimate
so the planner and the page can say so.
"""

import logging
import math
import os

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_coords_cache = {}

# One-way economy fare per person: fixed part plus a rate per km, by distance band.
FARE_BANDS = ((1500, 30, 0.11), (4000, 40, 0.085), (float("inf"), 60, 0.065))
RETURN_DISCOUNT = 0.92  # a round trip costs a little less than two one-ways


def _airport_coords(code_or_city: str):
    key = code_or_city.strip().lower()
    if key in _coords_cache:
        return _coords_cache[key]
    response = requests.post(
        SEARCH_URL,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": os.getenv("GOOGLE_PLACES_API_KEY", ""),
            "X-Goog-FieldMask": "places.location,places.displayName",
        },
        json={"textQuery": f"{code_or_city} airport", "maxResultCount": 1},
        timeout=15,
    )
    response.raise_for_status()
    places = response.json().get("places", [])
    if not places:
        raise ValueError(f"No airport found for {code_or_city}")
    loc = places[0]["location"]
    _coords_cache[key] = (loc["latitude"], loc["longitude"])
    return _coords_cache[key]


def _km_between(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


def estimate_flight(origin, destination, departure_date, return_date=None, adults=1,
                    origin_city=None, destination_city=None):
    """One estimated 'offer' in the same shape as a real one, or None if the
    airports can't be located."""
    try:
        distance = _km_between(_airport_coords(origin_city or origin),
                               _airport_coords(destination_city or destination))
    except Exception as exc:
        logger.warning("Could not estimate a fare for %s-%s: %r", origin, destination, exc)
        return None

    base, per_km = next((b, r) for limit, b, r in FARE_BANDS if distance <= limit)
    one_way = base + per_km * distance
    total = one_way * (2 * RETURN_DISCOUNT if return_date else 1) * max(1, int(adults))

    return {
        "id": f"estimate_{origin}_{destination}",
        "airline": "Estimated fare (no live offer for this route)",
        "price": round(total, 2),
        "currency": "USD",
        "stops": 0 if distance < 4000 else 1,
        "distance_km": round(distance),
        "price_is_estimate": True,
    }
