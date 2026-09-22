from types import SimpleNamespace

from fastapi.testclient import TestClient

from dossier_agent import server
from dossier_agent import database


class FakeResult:
    response_id = "persisted-response"
    text = "SUMMARY\nSource: https://example.com/primary"

    def as_json(self):
        return {"verdict": "confirmed", "sources": ["https://example.com/primary"]}


class FakeAgent:
    def __init__(self, model=None, live_web=True, provider=None):
        self.model = model or "test-model"
        self.provider_config = SimpleNamespace(name=provider or "local")

    def research(self, question, *, output_format="human"):
        return FakeResult()


def test_account_history_and_sources_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'dossier.db'}")
    monkeypatch.setenv("DOSSIER_AUTH_SECRET", "test-secret")
    monkeypatch.setattr(server, "DossierAgent", FakeAgent)
    database._engine = None
    database._session_factory = None
    server._database_initialized = False

    client = TestClient(server.app)
    signup = client.post(
        "/api/auth/signup",
        json={"email": "persisted@example.com", "password": "correct horse battery staple"},
    )
    assert signup.status_code == 200
    headers = {"Authorization": f"Bearer {signup.json()['token']}"}

    research = client.post(
        "/api/research",
        headers=headers,
        json={"question": "Persist this", "provider": "local", "live_web": False},
    )
    assert research.status_code == 200
    research_id = research.json()["research_id"]

    history = client.get("/api/history", headers=headers)
    assert history.status_code == 200
    assert history.json()["items"][0]["source_count"] == 1

    detail = client.get(f"/api/research/{research_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["sources"][0]["url"] == "https://example.com/primary"
