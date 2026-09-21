from schemas.trip_state import TripState
from api_clients.duffel_client import search_flights


def flight_agent(state: TripState) -> TripState:
    results = search_flights(
        origin=state["origin"],
        destination=state["destination"],
        departure_date=state["departure_date"],
    )
    state["flight_results"] = results
    return state