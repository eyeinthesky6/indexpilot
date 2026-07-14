from fastapi.testclient import TestClient

from indexpilot.cli import api_main
from src.api_auth import check_bearer_token
from src.api_server import app


def test_bearer_auth_fails_closed_when_token_is_not_configured(monkeypatch):
    monkeypatch.delenv("INDEXPILOT_API_AUTH_MODE", raising=False)
    monkeypatch.delenv("INDEXPILOT_API_TOKEN", raising=False)

    assert check_bearer_token(None) == (503, "api_auth_not_configured")


def test_bearer_auth_uses_constant_time_token_comparison(monkeypatch):
    monkeypatch.setenv("INDEXPILOT_API_AUTH_MODE", "required")
    monkeypatch.setenv("INDEXPILOT_API_TOKEN", "test-secret")

    assert check_bearer_token(None) == (401, "bearer_token_required")
    assert check_bearer_token("Basic test-secret") == (401, "bearer_token_required")
    assert check_bearer_token("Bearer wrong") == (401, "invalid_bearer_token")
    assert check_bearer_token("Bearer test-secret") is None


def test_api_middleware_keeps_only_liveness_public(monkeypatch):
    monkeypatch.setenv("INDEXPILOT_API_AUTH_MODE", "required")
    monkeypatch.setenv("INDEXPILOT_API_TOKEN", "test-secret")
    client = TestClient(app)

    assert client.get("/").status_code == 200
    assert client.get("/openapi.json").status_code == 401
    assert client.get("/openapi.json", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert (
        client.get("/openapi.json", headers={"Authorization": "Bearer test-secret"}).status_code
        == 200
    )


def test_non_loopback_api_refuses_to_start_without_auth(monkeypatch):
    monkeypatch.setenv("INDEXPILOT_API_AUTH_MODE", "disabled")
    monkeypatch.delenv("INDEXPILOT_API_TOKEN", raising=False)

    try:
        api_main(["--host", "0.0.0.0"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("non-loopback API should refuse disabled authentication")
