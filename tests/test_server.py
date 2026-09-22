from fastapi.testclient import TestClient

from dossier_agent import server


class FakeResult:
    response_id = "resp_web"
    text = "A cited report."

    def as_json(self):
        return {"verdict": "confirmed", "summary": "A test result."}


class FakeAgent:
    def __init__(self, model=None, live_web=True):
        self.model = model
        self.live_web = live_web

    def research(self, question, *, output_format="human"):
        assert question == "Test the claim"
        return FakeResult()


def test_health_endpoint():
    response = TestClient(server.app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "dossier"}


def test_research_endpoint_returns_json(monkeypatch):
    monkeypatch.setattr(server, "DossierAgent", FakeAgent)
    response = TestClient(server.app).post(
        "/api/research",
        json={"question": "Test the claim", "output_format": "json", "live_web": True},
    )
    assert response.status_code == 200
    assert response.json()["result"]["verdict"] == "confirmed"
