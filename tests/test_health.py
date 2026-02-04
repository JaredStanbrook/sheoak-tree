def test_homepage_returns_ok(client):
    response = client.get("/")
    assert response.status_code == 200


def test_ai_page_returns_roadmap_placeholder(client):
    response = client.get("/ai")
    assert response.status_code == 200
    assert b"AI Workbench (Coming Soon)" in response.data
