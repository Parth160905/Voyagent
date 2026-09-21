from schemas.trip_state import TripState
from api_clients.places_client import search_activities


def activities_agent(state: TripState) -> dict:
    results = search_activities(city_name=state["destination_city_code"])
    return {"activity_results": results}