import logging

from schemas.trip_state import TripState
from api_clients.duffel_client import search_flights
from api_clients.flight_estimate import estimate_flights

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
        logger.warning("Duffel search failed: %r", exc)
        results = []
    if results:
        return {"flight_results": results}

    # Duffel's test environment only covers some routes; estimate the rest.
    logger.info("No live offers for %s-%s, estimating the fare.", search["origin"], search["destination"])
    return {"flight_results": estimate_flights(**search)}
