import os
import random
import requests

DUFFEL_API_KEY = os.getenv("DUFFEL_API_KEY")
BASE_URL = "https://api.duffel.com"

HEADERS = {
    "Content-Type": "application/json",
    "Accept-Encoding": "gzip",
    "Duffel-Version": "v2",
    "Authorization": f"Bearer {DUFFEL_API_KEY}",
}


def search_flights(origin: str, destination: str, departure_date: str) -> list[dict]:
    payload = {
        "data": {
            "slices": [
                {
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date,
                }
            ],
            "passengers": [{"type": "adult"}],
            "cabin_class": "economy",
        }
    }

    response = requests.post(
        f"{BASE_URL}/air/offer_requests",
        headers=HEADERS,
        json=payload,
        params={"return_offers": "true"},
    )
    response.raise_for_status()
    offers = response.json()["data"]["offers"]

    return [
        {
            "id": offer["id"],
            "airline": offer["owner"]["name"],
            "price": offer["total_amount"],
            "currency": offer["total_currency"],
            "departure": offer["slices"][0]["segments"][0]["departing_at"],
            "arrival": offer["slices"][0]["segments"][-1]["arriving_at"],
        }
        for offer in offers[:5]
    ]


def search_hotels(
    city_code: str, check_in_date: str, check_out_date: str, adults: int = 1
) -> list[dict]:
    sample_hotels = {
        "NYC": ["The Manhattan Grand", "Central Park Suites", "Brooklyn Bridge Hotel", "Times Square Inn", "SoHo Boutique Hotel"],
        "LON": ["The Kensington", "Covent Garden Suites", "Thames View Hotel", "Camden Lock Inn", "Mayfair Grand"],
        "PAR": ["Hotel Le Marais", "Champs-Elysees Suites", "Montmartre Boutique", "Seine View Hotel", "Latin Quarter Inn"],
        "TOK": ["Shibuya Grand", "Shinjuku Suites", "Asakusa Traditional Inn", "Ginza Boutique Hotel", "Tokyo Bay Hotel"],
    }

    names = sample_hotels.get(city_code, ["Sample Hotel A", "Sample Hotel B", "Sample Hotel C"])

    return [
        {
            "id": f"mock_hotel_{i}",
            "name": name,
            "price": str(round(random.uniform(90, 350), 2)),
            "currency": "USD",
            "location": {"city_code": city_code},
        }
        for i, name in enumerate(names)
    ]