from fastapi.testclient import TestClient

from app.main import app

# TestClient does not start a server, it calls the routing of the FastAPI
# application directly. That is why it is fast and a good fit for CI.

client = TestClient(app)


def test_root_returns_ok():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_greet_returns_personal_message():
    response = client.post("/greet", json={"name": "Anna"})
    assert response.status_code == 200
    assert response.json() == {"message": "Szia, Anna!"}


def test_greet_rejects_empty_name():
    # Pydantic validation rejects an empty name.
    response = client.post("/greet", json={"name": ""})
    assert response.status_code == 422


def test_config_reports_configured_key(monkeypatch):
    # The endpoint reports true, and the value is not part of the response.
    monkeypatch.setenv("OPENAI_API_KEY", "test-value")
    response = client.get("/config")
    assert response.status_code == 200
    assert response.json() == {"api_key_configured": True}
    assert "test-value" not in response.text
