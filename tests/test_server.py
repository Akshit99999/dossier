from fastapi.testclient import TestClient
from types import SimpleNamespace

from dossier_agent import db, server


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


def test_health_endpoint(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
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
    assert readiness.json()["storage"] == "sqlite"


def test_auth_workflow_and_protected_history(tmp_path, monkeypatch):
    test_db = tmp_path / "test_auth.db"
    monkeypatch.setattr(server, "get_db_connection", lambda db_path=None: db.get_db_connection(test_db))
    monkeypatch.setattr(server, "get_user_by_token", lambda token: db.get_user_by_token(token, db_path=test_db))
    monkeypatch.setattr(server, "register_user", lambda email, password: db.register_user(email, password, db_path=test_db))
    monkeypatch.setattr(server, "authenticate_user", lambda email, password: db.authenticate_user(email, password, db_path=test_db))
    db.init_db(test_db)

    client = TestClient(server.app)

    # 1. Register user
    reg_res = client.post("/api/auth/register", json={"email": "researcher@example.com", "password": "password123"})
    assert reg_res.status_code == 200
    token = reg_res.json()["token"]
    assert token

    # 2. Check /api/auth/me
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["user"]["email"] == "researcher@example.com"

    # 3. Login with credentials
    login_res = client.post("/api/auth/login", json={"email": "researcher@example.com", "password": "password123"})
    assert login_res.status_code == 200
    assert "token" in login_res.json()
