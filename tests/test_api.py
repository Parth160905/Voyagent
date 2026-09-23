from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_home_page_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200


def test_plan_rejects_empty_request():
    response = client.post("/api/plan", json={})
    assert response.status_code == 422


def test_plan_rejects_non_json_body():
    response = client.post("/api/plan", content="not json",
                           headers={"content-type": "application/json"})
    assert response.status_code == 422
