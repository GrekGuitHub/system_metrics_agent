import pytest
from fastapi.testclient import TestClient

from app import api

client = TestClient(api.app)

PAYLOAD = {
    "agent": "system-metrics-agent",
    "event_type": "system_metrics",
    "data": {"cpu": {"percent": 12.5}},
}


@pytest.fixture(autouse=True)
def reset_metrics():
    api.received_metrics.clear()
    yield
    api.received_metrics.clear()


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_latest_without_metrics_returns_404():
    response = client.get("/metrics/latest")

    assert response.status_code == 404


def test_post_then_latest():
    response = client.post("/metrics", json=PAYLOAD)

    assert response.status_code == 201
    assert response.json()["total_received"] == 1

    latest = client.get("/metrics/latest").json()
    assert latest["agent"] == "system-metrics-agent"
    assert latest["data"]["cpu"]["percent"] == 12.5
    assert "received_at" in latest


def test_list_metrics():
    client.post("/metrics", json=PAYLOAD)
    client.post("/metrics", json=PAYLOAD)

    body = client.get("/metrics").json()

    assert body["total"] == 2
    assert len(body["metrics"]) == 2


def test_invalid_payload_returns_422():
    response = client.post("/metrics", json={"agent": "", "event_type": "x"})

    assert response.status_code == 422
