from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from agents.flight_agent import flight_agent
from agents.hotel_agent import hotel_agent
from agents.activities_agent import activities_agent
from graph import voyagent_graph

app = FastAPI()


@app.get("/")
def health_check():
    return {"status": "ok"}


def build_test_state():
    return {
        "origin": "LHR",
        "destination": "JFK",
        "destination_city_code": "NYC",
        "departure_date": "2026-12-15",
        "return_date": "2026-12-20",
        "budget_total": 2000,
        "budget_currency": "GBP",
        "flight_results": None,
        "hotel_results": None,
        "activity_results": None,
        "final_itinerary": None,
    }


@app.get("/test-flight-agent")
def test_flight_agent():
    return flight_agent(build_test_state())


@app.get("/test-hotel-agent")
def test_hotel_agent():
    return hotel_agent(build_test_state())


@app.get("/test-activities-agent")
def test_activities_agent():
    return activities_agent(build_test_state())


@app.get("/test-orchestrator")
def test_orchestrator():
    return voyagent_graph.invoke(build_test_state())
@app.get("/test-itinerary", response_class=PlainTextResponse)
def test_itinerary():
    result = voyagent_graph.invoke(build_test_state())
    return result.get("final_itinerary") or "No itinerary generated. Check the terminal."
from web.routes import router as web_router
app.include_router(web_router)