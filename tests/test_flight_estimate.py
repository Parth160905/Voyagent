from api_clients.flight_estimate import _one_way_usd


def test_fare_is_positive():
    assert _one_way_usd(500) > 0


def test_longer_flights_cost_more():
    assert _one_way_usd(8000) > _one_way_usd(500)
