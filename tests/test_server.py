from fastapi.testclient import TestClient
from types import SimpleNamespace

from dossier_agent import server


class FakeResult:
    response_id = "resp_web"
    text = "A cited report."

    def as_json(self):
        return {"verdict": "confirmed", "summary": "A test result."}


class FakeAgent:
    def __init__(self, model=None, live_web=True, provider=None):
        self.model = model
        self.live_web = live_web
        self.provider = provider
        self.provider_config = SimpleNamespace(name="openai")

    def research(self, question, *, output_format="human"):
        assert question == "Test the claim"
        return FakeResult()


def test_health_endpoint():
    response = TestClient(server.app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "dossier",
        "openai_configured": False,
        "provider": "openrouter",
        "model": "openrouter/free",
        "provider_configured": False,
    }


def test_research_endpoint_returns_json(monkeypatch):
    monkeypatch.setattr(server, "DossierAgent", FakeAgent)
    response = TestClient(server.app).post(
        "/api/research",
        json={"question": "Test the claim", "output_format": "json", "live_web": True},
    )
    assert response.status_code == 200
    assert response.json()["result"]["verdict"] == "confirmed"


def test_history_endpoint_is_available():
    response = TestClient(server.app).get("/api/history")
    assert response.status_code == 200
    assert "items" in response.json()


def test_deployment_health_probes():
    client = TestClient(server.app)
    assert client.get("/api/health/live").json() == {"status": "ok", "service": "dossier"}
    readiness = client.get("/api/health/ready")
    assert readiness.status_code == 200
    assert readiness.json()["storage"] == "memory"
