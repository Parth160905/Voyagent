from schemas.trip_state import TripState
from api_clients.duffel_client import search_flights


def flight_agent(state: TripState) -> dict:
    results = search_flights(
        origin=state["origin"],
        destination=state["destination"],
        departure_date=state["departure_date"],
        return_date=state.get("return_date"),        # round trip when a return date is set
        adults=state.get("travelers") or 1,
    )
    return {"flight_results": results}
