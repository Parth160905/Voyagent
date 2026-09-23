import logging

from schemas.trip_state import TripState
from api_clients.duffel_client import search_flights
from api_clients.fare_estimate import estimate_flight

logger = logging.getLogger(__name__)


def flight_agent(state: TripState) -> dict:
    search = dict(
        origin=state["origin"],
        destination=state["destination"],
        departure_date=state["departure_date"],
        return_date=state.get("return_date"),        # round trip when a return date is set
        adults=state.get("travelers") or 1,
    )
    try:
        results = search_flights(**search)
    except Exception as exc:
        logger.warning("Duffel search failed, falling back to an estimate: %r", exc)
        results = []
    if results:
        return {"flight_results": results}

    # Duffel's test environment only covers some routes, so estimate the rest.
    logger.info("No live offers for %s-%s, estimating the fare.",
                search["origin"], search["destination"])
    estimate = estimate_flight(**search,
                               origin_city=state.get("origin_city"),
                               destination_city=state.get("destination_city"))
    return {"flight_results": [estimate] if estimate else []}
