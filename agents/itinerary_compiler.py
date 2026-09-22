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
from datetime import date, timedelta

from dotenv import load_dotenv

from schemas.trip_state import TripState

load_dotenv()
logger = logging.getLogger(__name__)

PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
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
- Arrival day: plan lightly after the flight lands. Final day: hotel check-out. If no return
  flight is in the data, say the return journey is not booked yet.
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
        "days": days,
        "flight": {k: flight.get(k) for k in
                   ("airline", "departure", "arrival", "cost_in_budget_currency")},
        "hotel": {k: hotel.get(k) for k in
                  ("name", "rating", "nights", "total_cost_in_budget_currency")},
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

    client = genai.Client()  # reads GEMINI_API_KEY from the environment
    interaction = client.interactions.create(
        model=GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
        input=prompt,
        generation_config={"thinking_level": "low"},
    )
    return interaction.output_text or ""


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


# ---------- node ----------

def itinerary_compiler_agent(state: TripState) -> dict:
    # Nothing to plan if the allocator couldn't pick a flight and hotel.
    if state.get("budget_status") in (None, "insufficient_data"):
        reason = state.get("budget_note") or "budget allocation did not run."
        return {"final_itinerary": f"Could not build an itinerary: {reason}"}

    if PROVIDER not in PROVIDERS:
        return {"final_itinerary": f"Unknown LLM_PROVIDER '{PROVIDER}'. Use 'gemini' or 'claude'."}

    key_name = KEY_NAMES[PROVIDER]
    if not os.getenv(key_name):
        logger.warning("%s is not set, skipping itinerary generation.", key_name)
        return {"final_itinerary": f"Itinerary generation skipped: {key_name} is missing from .env."}

    prompt = "Build the itinerary from this trip data:\n\n" + json.dumps(_trip_context(state), indent=2)
    try:
        text = PROVIDERS[PROVIDER](prompt).strip()
    except Exception as exc:  # any provider/network error: degrade gracefully, keep the rest of the plan
        logger.warning("Itinerary generation failed (%s): %r", PROVIDER, exc)
        return {"final_itinerary": "Itinerary generation failed. Check the server logs."}

    return {"final_itinerary": text or "The model returned an empty itinerary."}