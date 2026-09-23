"""
Budget allocator agent.

Fan-in node: runs after the flight, hotel and activities agents have all
finished. Converts every price into the trip currency, picks the best
flight + hotel pair that fits the budget, then spends what's left on
activities.

No LLM call here on purpose. This is a constraint problem, so the answer
should be deterministic, cheap, and unit-testable.
"""

import math
from datetime import date
from itertools import product

from api_clients.fx_client import convert, get_usd_rates
from schemas.trip_state import TripState

# Held back for food, local transport and surprises.
CONTINGENCY_RATIO = 0.15
# Guaranteed floor for activities, so a great hotel can't eat the whole budget.
MIN_ACTIVITY_RATIO = 0.10

# Google Places gives a price level (or nothing), not a price. Rough
# per-person cost in USD, converted to the trip currency later.
PRICE_LEVEL_COST_USD = {
    0: 0, 1: 10, 2: 25, 3: 60, 4: 120,
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 10,
    "PRICE_LEVEL_MODERATE": 25,
    "PRICE_LEVEL_EXPENSIVE": 60,
    "PRICE_LEVEL_VERY_EXPENSIVE": 120,
}
UNKNOWN_ACTIVITY_COST_USD = 10  # typical ticketed attraction

FLIGHT_PRICE_KEYS = ("total_amount", "price", "total_price", "amount", "cost")
HOTEL_TOTAL_KEYS = ("total_price", "total_cost")
HOTEL_NIGHTLY_KEYS = ("price_per_night", "nightly_rate", "price")  # mock hotels: nightly "price"

TOP_N = 10                 # options per category -> at most 100 pairs to check
MAX_ACTIVITIES_PER_DAY = 3
DEFAULT_HOTEL_RATING = 3.0
STOP_PENALTY = 0.15        # score lost per layover


# ---------- helpers ----------

def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_number(d, *keys):
    """Return the first key that holds a usable number."""
    for key in keys:
        value = _to_float(d.get(key))
        if value is not None:
            return value
    return None


def _to_date(value):
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _money(option, keys, to_ccy):
    """Read a price from an option and convert it to the trip currency."""
    amount = _first_number(option, *keys)
    if amount is None:
        return None
    from_ccy = option.get("currency") or option.get("total_currency") or to_ccy
    try:
        return convert(amount, from_ccy, to_ccy)
    except KeyError:
        return None  # no exchange rate for this currency, skip the option


def _flight_stops(flight):
    if "stops" in flight:
        return int(flight["stops"])
    # Raw Duffel offer: stops = segments - 1, worst slice wins.
    stops = [len(s.get("segments") or []) - 1 for s in flight.get("slices") or []]
    return max(stops + [0])


def _hotel_cost(hotel, nights, rooms, ccy):
    total = _money(hotel, HOTEL_TOTAL_KEYS, ccy)
    if total is not None:
        return total
    nightly = _money(hotel, HOTEL_NIGHTLY_KEYS, ccy)
    return None if nightly is None else nightly * nights * rooms


def _hotel_rating(hotel):
    return _first_number(hotel, "rating", "stars") or DEFAULT_HOTEL_RATING


def _activity_cost(activity, travelers, ccy):
    level = activity.get("price_level", activity.get("priceLevel"))
    usd = PRICE_LEVEL_COST_USD.get(level, UNKNOWN_ACTIVITY_COST_USD)
    return convert(usd, "USD", ccy) * travelers


def _priced(options, cost_fn):
    """Pair each option with its cost, dropping any we can't price."""
    priced = []
    for option in options:
        cost = cost_fn(option)
        if cost is not None:
            priced.append((option, cost))
    return priced[:TOP_N]


def _pair_score(flight, hotel):
    return _hotel_rating(hotel) / 5 - STOP_PENALTY * _flight_stops(flight)


def _pick_activities(options, money, travelers, nights, ccy):
    """Greedy: highest-rated first, skip anything that doesn't fit."""
    slots = nights * MAX_ACTIVITIES_PER_DAY
    ranked = sorted(options, key=lambda a: _to_float(a.get("rating")) or 0, reverse=True)
    chosen, spent = [], 0.0
    for activity in ranked:
        if len(chosen) == slots:
            break
        cost = _activity_cost(activity, travelers, ccy)
        if spent + cost <= money:
            chosen.append({**activity, "estimated_cost": round(cost, 2)})
            spent += cost
    return chosen, spent


def _fail(reason):
    return {"budget_status": "insufficient_data", "budget_note": reason}


# ---------- node ----------

def budget_allocator_agent(state: TripState) -> dict:
    budget = _to_float(state.get("budget_total"))
    if budget is None or budget <= 0:
        return _fail("No valid budget in trip state.")

    ccy = (state.get("budget_currency") or "USD").upper()
    try:
        convert(1, "USD", ccy)
    except KeyError:
        return _fail(f"No exchange rate available for {ccy}.")

    if not state.get("return_date"):
        return _fail("No return_date, so hotel nights can't be worked out.")
    try:
        nights = max((_to_date(state["return_date"]) - _to_date(state["departure_date"])).days, 1)
    except (KeyError, TypeError, ValueError):
        return _fail("Invalid or missing travel dates.")

    # TripState has no travelers field yet, so this is 1 for now.
    travelers = int(state.get("travelers") or 1)
    rooms = math.ceil(travelers / 2)

    flights = _priced(state.get("flight_results") or [],
                      lambda f: _money(f, FLIGHT_PRICE_KEYS, ccy))
    hotels = _priced(state.get("hotel_results") or [],
                     lambda h: _hotel_cost(h, nights, rooms, ccy))
    if not flights or not hotels:
        return _fail("Missing priced flight or hotel options.")

    contingency = budget * CONTINGENCY_RATIO
    core_cap = budget - contingency - budget * MIN_ACTIVITY_RATIO

    pairs = [(f, fc, h, hc) for (f, fc), (h, hc) in product(flights, hotels)]
    affordable = [p for p in pairs if p[1] + p[3] <= core_cap]

    if affordable:
        # Best score wins; on a tie, the cheaper pair.
        flight, f_cost, hotel, h_cost = max(
            affordable, key=lambda p: (_pair_score(p[0], p[2]), -(p[1] + p[3]))
        )
        status = "ok"
        note = "Flight and hotel fit the budget."
    else:
        flight, f_cost, hotel, h_cost = min(pairs, key=lambda p: p[1] + p[3])
        status = "over_budget"
        shortfall = f_cost + h_cost - core_cap
        note = (f"Cheapest flight + hotel is {f_cost + h_cost:.0f} {ccy}, about "
                f"{shortfall:.0f} {ccy} over what the budget allows for them.")

    activity_money = max(budget - contingency - f_cost - h_cost, 0)
    if status == "over_budget":
        # The trip already breaks the budget; still plan a little sightseeing so the
        # itinerary isn't empty. The warning and the breakdown show the overspend.
        activity_money = max(activity_money, budget * MIN_ACTIVITY_RATIO)
    activities, a_cost = _pick_activities(
        state.get("activity_results") or [], activity_money, travelers, nights, ccy
    )

    _, fx_source = get_usd_rates()
    spent = f_cost + h_cost + a_cost
    return {
        "selected_flight": {**flight, "cost_in_budget_currency": round(f_cost, 2)},
        "selected_hotel": {**hotel, "nights": nights,
                           "total_cost_in_budget_currency": round(h_cost, 2)},
        "selected_activities": activities,
        "budget_breakdown": {
            "currency": ccy,
            "fx_rates": fx_source,  # "live" or "fallback"
            "total_budget": round(budget, 2),
            "flight": round(f_cost, 2),
            "hotel": round(h_cost, 2),
            "activities": round(a_cost, 2),
            "contingency": round(contingency, 2),
            "unallocated": round(budget - spent - contingency, 2),
        },
        "budget_status": status,
        "budget_note": note,
    }