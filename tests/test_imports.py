import importlib

import pytest

MODULES = [
    "main",
    "graph",
    "web.routes",
    "schemas.trip_state",
    "agents.activities_agent",
    "agents.budget_allocator",
    "agents.flight_agent",
    "agents.hotel_agent",
    "agents.itinerary_compiler",
    "api_clients.airports",
    "api_clients.duffel_client",
    "api_clients.flight_estimate",
    "api_clients.fx_client",
    "api_clients.hotels_client",
    "api_clients.places_client",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports_without_network(name):
    importlib.import_module(name)
