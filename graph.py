from langgraph.graph import StateGraph, START, END

from schemas.trip_state import TripState
from agents.flight_agent import flight_agent
from agents.hotel_agent import hotel_agent
from agents.activities_agent import activities_agent
from agents.budget_allocator import budget_allocator_agent
from agents.itinerary_compiler import itinerary_compiler_agent


def build_graph():
    builder = StateGraph(TripState)

    builder.add_node("flight_agent", flight_agent)
    builder.add_node("hotel_agent", hotel_agent)
    builder.add_node("activities_agent", activities_agent)
    builder.add_node("budget_allocator", budget_allocator_agent)
    builder.add_node("itinerary_compiler", itinerary_compiler_agent)

    # The three search agents run in parallel
    builder.add_edge(START, "flight_agent")
    builder.add_edge(START, "hotel_agent")
    builder.add_edge(START, "activities_agent")

    # Wait for all three, allocate the budget, then write the itinerary
    builder.add_edge(["flight_agent", "hotel_agent", "activities_agent"], "budget_allocator")
    builder.add_edge("budget_allocator", "itinerary_compiler")
    builder.add_edge("itinerary_compiler", END)

    return builder.compile()


voyagent_graph = build_graph()