from schemas.trip_state import TripState
from api_clients.duffel_client import search_flights


def flight_agent(state: TripState) -> dict:
    results = search_flights(
        origin=state["origin"],
        destination=state["destination"],
        departure_date=state["departure_date"],
    )
    return {"flight_results": results}