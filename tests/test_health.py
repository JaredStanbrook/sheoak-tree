def test_homepage_returns_ok(client):
    response = client.get("/")
    assert response.status_code == 200
