import os
import requests

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
BASE_URL = "https://places.googleapis.com/v1/places:searchText"


def search_activities(city_name: str, activity_type: str = "tourist attraction") -> list[dict]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.googleMapsUri",
    }

    payload = {
        "textQuery": f"{activity_type} in {city_name}",
        "maxResultCount": 5,
    }

    response = requests.post(BASE_URL, headers=headers, json=payload)
    response.raise_for_status()
    places = response.json().get("places", [])

    return [
        {
            "name": place.get("displayName", {}).get("text"),
            "address": place.get("formattedAddress"),
            "rating": place.get("rating"),
            "rating_count": place.get("userRatingCount"),
            "maps_url": place.get("googleMapsUri"),
        }
        for place in places
    ]