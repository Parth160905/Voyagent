import logging

from schemas.trip_state import TripState
from api_clients.hotels_client import search_hotels_places
from api_clients.duffel_client import search_hotels as sample_hotels

logger = logging.getLogger(__name__)


def hotel_agent(state: TripState) -> dict:
    """Real hotels from Google Places; sample hotels only if that search fails."""
    city = state["destination_city_code"]
    try:
        hotels = search_hotels_places(city)
        if hotels:
            return {"hotel_results": hotels}
        logger.warning("No hotels found in Places for %s, using sample hotels.", city)
    except Exception as exc:
        logger.warning("Places hotel search failed, using sample hotels: %r", exc)

    return {"hotel_results": sample_hotels(
        city_code=city,
        check_in_date=state["departure_date"],
        check_out_date=state.get("return_date") or state["departure_date"],
        adults=state.get("travelers") or 1,
    )}
