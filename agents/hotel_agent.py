from schemas.trip_state import TripState
from api_clients.duffel_client import search_hotels


def hotel_agent(state: TripState) -> dict:
    results = search_hotels(
        city_code=state["destination_city_code"],
        check_in_date=state["departure_date"],
        check_out_date=state["return_date"] or state["departure_date"],
        adults=1,
    )
    return {"hotel_results": results}