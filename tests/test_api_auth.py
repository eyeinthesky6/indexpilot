from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from indexpilot.cli import api_main
from src.api_auth import check_bearer_token, get_api_auth_mode
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


def test_api_middleware_keeps_only_liveness_access_and_static_ui_public(monkeypatch):
    monkeypatch.setenv("INDEXPILOT_API_AUTH_MODE", "required")
    monkeypatch.setenv("INDEXPILOT_API_TOKEN", "test-secret")
    client = TestClient(app)

    assert client.get("/").status_code == 200
    access = client.get("/api/access")
    assert access.status_code == 200
    assert access.json()["authMode"] == "required"
    assert client.get("/dashboard/").status_code == 200
    assert client.get("/openapi.json").status_code == 401
    assert client.get("/openapi.json", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert (
        client.get("/openapi.json", headers={"Authorization": "Bearer test-secret"}).status_code
        == 200
    )


def test_api_middleware_allows_passwordless_loopback_mode(monkeypatch):
    monkeypatch.setenv("INDEXPILOT_API_AUTH_MODE", "disabled")
    monkeypatch.delenv("INDEXPILOT_API_TOKEN", raising=False)
    client = TestClient(app)

    assert client.get("/openapi.json").status_code == 200


def test_loopback_api_defaults_to_passwordless_local_mode(monkeypatch):
    monkeypatch.delenv("INDEXPILOT_API_AUTH_MODE", raising=False)
    monkeypatch.delenv("INDEXPILOT_API_TOKEN", raising=False)
    run_args = {}

    def fake_run(*args, **kwargs):
        run_args["args"] = args
        run_args["kwargs"] = kwargs

    monkeypatch.setattr("uvicorn.run", fake_run)

    assert api_main(["--host", "127.0.0.1", "--port", "8765"]) == 0
    assert get_api_auth_mode() == "disabled"
    assert run_args["kwargs"]["host"] == "127.0.0.1"
    assert run_args["kwargs"]["port"] == 8765


def test_loopback_api_preserves_explicit_required_auth(monkeypatch):
    monkeypatch.setenv("INDEXPILOT_API_AUTH_MODE", "required")
    monkeypatch.setenv("INDEXPILOT_API_TOKEN", "test-secret")
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: None)

    assert api_main(["--host", "localhost"]) == 0
    assert get_api_auth_mode() == "required"


def test_non_loopback_api_refuses_to_start_without_auth(monkeypatch):
    monkeypatch.setenv("INDEXPILOT_API_AUTH_MODE", "disabled")
    monkeypatch.delenv("INDEXPILOT_API_TOKEN", raising=False)

    try:
        api_main(["--host", "0.0.0.0"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("non-loopback API should refuse disabled authentication")


@pytest.mark.parametrize(
    ("path", "operation"),
    [
        ("/api/lifecycle/weekly", "run_manual_weekly_lifecycle"),
        ("/api/lifecycle/monthly", "run_manual_monthly_lifecycle"),
        ("/api/lifecycle/tenant/7", "run_manual_tenant_lifecycle"),
    ],
)
def test_lifecycle_api_rejects_non_dry_operations(monkeypatch, path, operation):
    monkeypatch.setenv("INDEXPILOT_API_AUTH_MODE", "disabled")
    client = TestClient(app)

    with patch(f"src.index_lifecycle_manager.{operation}") as lifecycle_operation:
        response = client.post(f"{path}?dry_run=false")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "IndexPilot lifecycle API operations are advisory dry runs only."
    )
    lifecycle_operation.assert_not_called()


def test_lifecycle_api_preserves_advisory_dry_run(monkeypatch):
    monkeypatch.setenv("INDEXPILOT_API_AUTH_MODE", "disabled")
    client = TestClient(app)

    with patch(
        "src.index_lifecycle_manager.run_manual_weekly_lifecycle",
        return_value={"dry_run": True},
    ) as lifecycle_operation:
        response = client.post("/api/lifecycle/weekly")

    assert response.status_code == 200
    assert response.json() == {"dry_run": True}
    lifecycle_operation.assert_called_once_with(dry_run=True)
