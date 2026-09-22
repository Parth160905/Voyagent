from schemas.trip_state import TripState
from api_clients.duffel_client import search_hotels

# Duffel Stays needs a sales-approved account, so search_hotels returns mock
# hotels with no ratings. Give each mock hotel a fixed guest rating (out of 5)
# so the budget allocator can weigh quality against price. Real hotel data
# brings its own rating, and setdefault never overwrites it.
MOCK_HOTEL_RATINGS = {
    "The Manhattan Grand": 4.6,
    "Central Park Suites": 4.4,
    "SoHo Boutique Hotel": 4.3,
    "Brooklyn Bridge Hotel": 4.1,
    "Times Square Inn": 3.8,
}
DEFAULT_MOCK_RATING = 3.5


def hotel_agent(state: TripState) -> dict:
    results = search_hotels(
        city_code=state["destination_city_code"],
        check_in_date=state["departure_date"],
        check_out_date=state["return_date"] or state["departure_date"],
        adults=1,
    )
    for hotel in results or []:
        hotel.setdefault("rating", MOCK_HOTEL_RATINGS.get(hotel.get("name"), DEFAULT_MOCK_RATING))
    return {"hotel_results": results}