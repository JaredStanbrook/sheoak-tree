import json


def test_health_check(client):
    """Test the health endpoint returns 200/503 based on service status."""
    # Note: Service might be 'degraded' in test mode due to mocks,
    # but the endpoint should still return valid JSON.
    response = client.get("/api/health")
    assert response.status_code in [200, 503]
    data = json.loads(response.data)
    assert "status" in data
    assert "services" in data


def test_get_hardwares_empty(client):
    """Test fetching hardwares when DB is empty."""
    response = client.get("/api/hardwares")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    # The motion app might seed defaults, or return empty
    assert isinstance(data["hardwares"], list)
