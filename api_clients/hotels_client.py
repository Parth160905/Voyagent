"""
Real hotels from Google Places (New).

Places has names, ratings and addresses but no room rates, so the nightly
price is an estimate from the hotel's price level (or its rating when the
price level is missing). Each hotel is flagged with price_is_estimate.
"""

import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
FIELDS = ",".join(f"places.{name}" for name in (
    "id", "displayName", "formattedAddress", "rating",
    "userRatingCount", "priceLevel", "googleMapsUri",
))

# Rough nightly rate in USD for each Places price level.
NIGHTLY_USD_BY_LEVEL = {
    "PRICE_LEVEL_INEXPENSIVE": 45,
    "PRICE_LEVEL_MODERATE": 90,
    "PRICE_LEVEL_EXPENSIVE": 170,
    "PRICE_LEVEL_VERY_EXPENSIVE": 320,
}


def _estimate_nightly_usd(price_level, rating):
    if price_level in NIGHTLY_USD_BY_LEVEL:
        return NIGHTLY_USD_BY_LEVEL[price_level]
    rating = rating or 0
    if rating >= 4.5:
        return 120
    if rating >= 4.0:
        return 80
    return 55


CACHE_SECONDS = 3600
_cache = {}


def search_hotels_places(city_name, max_results=8):
    key = (city_name or "").strip().lower()
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    hotels = _search_hotels_places(key or city_name, max_results)
    seen = {h["name"] for h in hotels}
    for cheap in _search_hotels_places(key or city_name, max_results, prefix="budget hotels in"):
        if cheap["name"] not in seen:
            hotels.append(cheap)
    _cache[key] = (time.time(), hotels)
    return hotels


def _search_hotels_places(city_name, max_results=8, prefix="hotels in"):
    response = requests.post(
        SEARCH_URL,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": os.getenv("GOOGLE_PLACES_API_KEY", ""),
            "X-Goog-FieldMask": FIELDS,
        },
        json={
            "textQuery": f"{prefix} {city_name}",
            "includedType": "lodging",
            "maxResultCount": max_results,
        },
        timeout=20,
    )
    response.raise_for_status()

    hotels = []
    for place in response.json().get("places", []):
        name = place.get("displayName", {}).get("text")
        if not name:
            continue
        hotels.append({
            "id": place.get("id"),
            "name": name,
            "address": place.get("formattedAddress"),
            "rating": place.get("rating"),
            "rating_count": place.get("userRatingCount"),
            "maps_url": place.get("googleMapsUri"),
            "price_per_night": _estimate_nightly_usd(place.get("priceLevel"), place.get("rating")),
            "currency": "USD",
            "price_is_estimate": True,
        })
    return hotels
