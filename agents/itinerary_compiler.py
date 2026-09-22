"""
Itinerary compiler agent.

Last node in the graph. Takes what the budget allocator selected and asks an
LLM to turn it into a day-by-day plan in Markdown. The model only sees the
selected options, and the prompt forbids inventing bookings, prices or extra
places, so the plan stays grounded in the real search results.

Provider is pluggable: set LLM_PROVIDER in .env to "gemini" (default, free
tier) or "claude".
"""

import json
import logging
import os
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

from schemas.trip_state import TripState

load_dotenv()
logger = logging.getLogger(__name__)

PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
# Tried in order. Each Gemini model has its own free-tier daily quota, so when
# one runs out (HTTP 429) the next one takes over.
GEMINI_MODELS = [m.strip() for m in os.getenv(
    "GEMINI_MODELS", "gemini-3.8-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite"
).split(",") if m.strip()]
GEMINI_TIMEOUT_MS = 45_000
CLAUDE_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
KEY_NAMES = {"gemini": "GEMINI_API_KEY", "claude": "ANTHROPIC_API_KEY"}

SYSTEM_PROMPT = """You are the itinerary compiler in a multi-agent travel planner.
Other agents have already chosen the flight, hotel and activities, and worked out the budget.
Your job is to turn their choices into a clear day-by-day plan.

Rules:
- Use only the flight, hotel and activities in the trip data. Do not invent bookings, prices,
  restaurants, tours or attractions that are not listed.
- You may add generic suggestions such as "lunch near the hotel" or "free evening",
  but never name a specific venue that is not in the data.
- Schedule every listed activity exactly once. Group activities that are close together,
  using their addresses.
- Use the dates exactly as given in "days". Do not work out weekdays yourself.
- Arrival day: plan lightly after the flight lands. Final day: hotel check-out, then the return
  flight if one is in the data (use its departure time). If there is no return flight, say the
  return journey is not booked yet.
- The trip is for the number of travellers given. All prices already cover every traveller.
- Hotel prices marked as estimates are estimates; say so once in the budget summary.
- Copy every price and total exactly as given, in the trip currency. Never recalculate them.
- If budget_status is "over_budget", open with a short warning based on budget_note.

Format the answer in Markdown:
# <Trip title>
One-line summary.
## Day N: <date from "days">
Bullet points grouped as Morning / Afternoon / Evening.
## Budget summary
A table with one row per budget_breakdown item.
"""


def _trip_context(state: TripState) -> dict:
    """Only what the model needs. Dropping URLs and raw offers saves tokens."""
    start = date.fromisoformat(str(state["departure_date"])[:10])
    end = date.fromisoformat(str(state["return_date"])[:10])
    days = [(start + timedelta(days=i)).strftime("%A %d %B %Y")
            for i in range((end - start).days + 1)]

    flight = state.get("selected_flight") or {}
    hotel = state.get("selected_hotel") or {}
    return {
        "origin": state.get("origin"),
        "destination": state.get("destination"),
        "city": state.get("destination_city_code"),
        "travellers": state.get("travelers") or 1,
        "days": days,
        "flight": {k: flight.get(k) for k in
                   ("airline", "departure", "arrival", "return_departure", "return_arrival",
                    "stops", "cost_in_budget_currency") if flight.get(k) is not None},
        "hotel": {k: hotel.get(k) for k in
                  ("name", "address", "rating", "nights", "total_cost_in_budget_currency",
                   "price_is_estimate") if hotel.get(k) is not None},
        "activities": [
            {k: a.get(k) for k in ("name", "address", "rating", "estimated_cost")}
            for a in state.get("selected_activities") or []
        ],
        "budget_breakdown": state.get("budget_breakdown"),
        "budget_status": state.get("budget_status"),
        "budget_note": state.get("budget_note"),
    }


# ---------- LLM providers (imports are lazy so only the one in use is needed) ----------

def _generate_with_gemini(prompt: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(http_options=types.HttpOptions(  # reads GEMINI_API_KEY
        timeout=GEMINI_TIMEOUT_MS,
        # Retry only server errors. A 429 means that model's quota is used up, and
        # the SDK's default is to wait about a minute per retry for the same answer.
        retry_options=types.HttpRetryOptions(attempts=1, http_status_codes=[500, 502, 503, 504]),
    ))
    last_error = None
    for model in GEMINI_MODELS:
        for config in ({"thinking_level": "low"}, None):  # retry without config if a model rejects it
            try:
                kwargs = {"generation_config": config} if config else {}
                interaction = client.interactions.create(
                    model=model, system_instruction=SYSTEM_PROMPT, input=prompt, **kwargs)
                text = (interaction.output_text or "").strip()
                if text:
                    return text
                break
            except Exception as exc:
                last_error = exc
                if config and "thinking" in repr(exc).lower():
                    continue
                logger.warning("Gemini model %s failed, trying the next one: %r", model, exc)
                break
    raise RuntimeError(f"All Gemini models failed. Last error: {last_error!r}")


def _generate_with_claude(prompt: str) -> str:
    from anthropic import Anthropic

    response = Anthropic().messages.create(  # reads ANTHROPIC_API_KEY
        model=CLAUDE_MODEL,
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in response.content if b.type == "text")


PROVIDERS = {"gemini": _generate_with_gemini, "claude": _generate_with_claude}


def _when(timestamp) -> str:
    """'2026-12-15T13:48:00' -> '15 Dec at 13:48'."""
    try:
        return datetime.fromisoformat(str(timestamp)).strftime("%d %b at %H:%M").lstrip("0")
    except ValueError:
        return str(timestamp or "")


def _basic_itinerary(ctx: dict) -> str:
    """Plain plan built without an LLM, used when every model is unavailable,
    so visitors still get a usable result."""
    days, flight, hotel = ctx["days"], ctx["flight"], ctx["hotel"]
    activities = [a["name"] for a in ctx["activities"] if a.get("name")]
    middle = max(len(days) - 2, 1)
    per_day = [activities[i::middle] for i in range(middle)]

    lines = [f"# Trip to {ctx.get('city') or ctx['destination']}",
             f"{len(days)} days for {ctx['travellers']} traveller(s). This is a basic plan "
             "because the AI writer is unavailable right now.", ""]
    for i, day in enumerate(days):
        lines.append(f"## Day {i + 1}: {day}")
        if i == 0:
            lines.append(f"- Fly with {flight.get('airline', 'your airline')}, landing {_when(flight.get('arrival'))}.")
            lines.append(f"- Check in to {hotel.get('name', 'your hotel')}.")
        elif i == len(days) - 1:
            lines.append(f"- Check out of {hotel.get('name', 'your hotel')}.")
            if flight.get("return_departure"):
                lines.append(f"- Return flight departs {_when(flight['return_departure'])}.")
            else:
                lines.append("- Return journey not booked yet.")
        else:
            todo = per_day[(i - 1) % middle]
            lines += [f"- Visit {name}." for name in todo] or ["- Free day to explore."]
        lines.append("")

    b = ctx.get("budget_breakdown") or {}
    ccy = b.get("currency", "")
    lines += ["## Budget summary", "| Item | Amount |", "|---|---|"]
    lines += [f"| {k.replace('_', ' ').title()} | {v} {ccy} |" for k, v in b.items()
              if isinstance(v, (int, float))]
    return "\n".join(lines)


# ---------- node ----------

def itinerary_compiler_agent(state: TripState) -> dict:
    # Nothing to plan if the allocator couldn't pick a flight and hotel.
    if state.get("budget_status") in (None, "insufficient_data"):
        reason = state.get("budget_note") or "budget allocation did not run."
        return {"final_itinerary": f"Could not build an itinerary: {reason}"}

    if PROVIDER not in PROVIDERS:
        return {"final_itinerary": f"Unknown LLM_PROVIDER '{PROVIDER}'. Use 'gemini' or 'claude'."}

    context = _trip_context(state)
    key_name = KEY_NAMES[PROVIDER]
    if not os.getenv(key_name):
        logger.warning("%s is not set, using the basic itinerary.", key_name)
        return {"final_itinerary": _basic_itinerary(context)}

    prompt = "Build the itinerary from this trip data:\n\n" + json.dumps(context, indent=2)
    try:
        text = PROVIDERS[PROVIDER](prompt).strip()
    except Exception as exc:  # quota, outage or timeout: fall back to the basic plan
        logger.warning("Itinerary generation failed (%s), using the basic itinerary: %r", PROVIDER, exc)
        return {"final_itinerary": _basic_itinerary(context)}

    return {"final_itinerary": text or _basic_itinerary(context)}
