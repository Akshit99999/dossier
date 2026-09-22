from fastapi.testclient import TestClient

from dossier_agent import server
from dossier_agent.auth import AuthIdentity, hash_password, issue_token, read_token, verify_password
from dossier_agent.database import Base


def test_password_hashing_and_signed_token_round_trip():
    encoded = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("incorrect", encoded)

    identity = AuthIdentity(user_id=4, email="person@example.com")
    assert read_token(issue_token(identity)) == identity


def test_mysql_schema_contains_account_research_and_source_tables():
    assert {"users", "research_runs", "source_records"} <= set(Base.metadata.tables)


def test_account_endpoint_explains_missing_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    response = TestClient(server.app).post(
        "/api/auth/signup",
        json={"email": "person@example.com", "password": "correct horse battery staple"},
    )
    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["detail"]
