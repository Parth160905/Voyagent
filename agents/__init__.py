from typing import TypedDict, Optional, List


class TripState(TypedDict):
    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str]
    budget_total: float
    budget_currency: str
    flight_results: Optional[List[dict]]
    hotel_results: Optional[List[dict]]
    activity_results: Optional[List[dict]]
    final_itinerary: Optional[str]