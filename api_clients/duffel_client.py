"""
Duffel client.

search_flights: real flight search against Duffel (test mode with a test token).
Supports return trips and several passengers; prices cover everyone, both ways.

search_hotels: sample hotels, used only as a fallback when the real hotel
search (Google Places) is unavailable. Duffel Stays needs an approved account.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

DUFFEL_API_KEY = os.getenv("DUFFEL_API_KEY")
OFFER_REQUESTS_URL = "https://api.duffel.com/air/offer_requests"
MAX_OFFERS = 10


def _headers():
    return {
        "Authorization": f"Bearer {DUFFEL_API_KEY}",
        "Duffel-Version": "v2",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def search_flights(origin, destination, departure_date, return_date=None, adults=1):
    slices = [{"origin": origin, "destination": destination, "departure_date": departure_date}]
    if return_date:
        slices.append({"origin": destination, "destination": origin, "departure_date": return_date})

    body = {"data": {
        "slices": slices,
        "passengers": [{"type": "adult"} for _ in range(max(1, int(adults)))],
        "cabin_class": "economy",
        "max_connections": 1,
    }}
    response = requests.post(
        OFFER_REQUESTS_URL,
        params={"return_offers": "true", "supplier_timeout": 8000},
        headers=_headers(),
        json=body,
        timeout=25,
    )
    response.raise_for_status()

    offers = response.json()["data"].get("offers", [])
    offers.sort(key=lambda o: float(o["total_amount"]))
    return [_simplify(offer) for offer in offers[:MAX_OFFERS]]


def _simplify(offer):
    outbound = offer["slices"][0]["segments"]
    flight = {
        "id": offer["id"],
        "airline": offer["owner"]["name"],
        "price": offer["total_amount"],          # total for all passengers and both legs
        "currency": offer["total_currency"],
        "departure": outbound[0]["departing_at"],
        "arrival": outbound[-1]["arriving_at"],
        "stops": max(len(s["segments"]) - 1 for s in offer["slices"]),
    }
    if len(offer["slices"]) > 1:
        inbound = offer["slices"][1]["segments"]
        flight["return_departure"] = inbound[0]["departing_at"]
        flight["return_arrival"] = inbound[-1]["arriving_at"]
    return flight


def search_hotels(city_code, check_in_date, check_out_date, adults=1):
    """Sample hotels (fallback only). Prices are fixed per hotel so results are stable."""
    city = str(city_code).strip() or "City"
    names = [f"{city} Central Hotel", f"Grand {city}", f"{city} Boutique Suites",
             f"{city} Budget Inn", f"Riverside {city} Hotel"]
    nightly_usd = [180, 260, 210, 90, 140]
    ratings = [4.2, 4.6, 4.4, 3.7, 4.0]
    return [
        {
            "id": f"sample_hotel_{i}",
            "name": name,
            "price": str(nightly_usd[i]),
            "currency": "USD",
            "rating": ratings[i],
            "is_sample": True,
        }
        for i, name in enumerate(names)
    ]


SUGGESTIONS_URL = "https://api.duffel.com/places/suggestions"
_places_cache = {}


def suggest_places(query, limit=6):
    """Airports and cities matching a name or code, most popular first.
    Duffel knows thousands of places, so this covers anywhere the built-in
    city table misses."""
    query = (query or "").strip()
    if len(query) < 2:
        return []
    if query.lower() in _places_cache:
        return _places_cache[query.lower()][:limit]

    response = requests.get(SUGGESTIONS_URL, params={"query": query},
                            headers=_headers(), timeout=15)
    response.raise_for_status()

    places = []
    for place in response.json().get("data", []):
        if not place.get("iata_code"):
            continue
        airports = place.get("airports") or []
        places.append({
            "iata_code": place["iata_code"],
            "name": place.get("name"),
            "type": place.get("type"),                      # "airport" or "city"
            "city_name": place.get("city_name") or place.get("name"),
            "latitude": place.get("latitude") or (airports[0].get("latitude") if airports else None),
            "longitude": place.get("longitude") or (airports[0].get("longitude") if airports else None),
        })
    _places_cache[query.lower()] = places
    return places[:limit]


def resolve_place(query):
    """Turn 'Lucknow' or 'LKO' into a single place with an IATA code."""
    matches = suggest_places(query, limit=10)
    if not matches:
        return None
    wanted = (query or "").strip().upper()
    for place in matches:
        if place["iata_code"] == wanted:
            return place
    return matches[0]
