from typing import TypedDict, Optional, List


class TripState(TypedDict):
    origin: str
    destination: str
    destination_city_code: str
    departure_date: str
    return_date: Optional[str]
    budget_total: float
    budget_currency: str
    flight_results: Optional[List[dict]]
    hotel_results: Optional[List[dict]]
    activity_results: Optional[List[dict]]
    final_itinerary: Optional[str]
        # Set by budget_allocator_agent
    selected_flight: dict
    selected_hotel: dict
    selected_activities: list[dict]
    budget_breakdown: dict
    budget_status: str   # "ok" | "over_budget" | "insufficient_data"
    budget_note: str