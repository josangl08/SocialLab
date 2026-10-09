"""
Route tests scaffolding for Content Quality Endpoints.
Verifications:
- Authentication required (401/403 unauthenticated)
- 422 Unprocessable Entity on invalid inputs
- Zero Gemini calls (mock that raises if called)
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from main import app
from auth.dependencies import get_current_user
from models.schemas import User
from tests.conftest import USER_ID


@pytest.fixture
def auth_client():
    """Client with authenticated user dependency override."""
    async def mock_get_current_user():
        return User(id=USER_ID, email="test@example.com")

    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = mock_get_current_user
    client = TestClient(app)
    yield client
    _restore_auth_override(previous)


@pytest.fixture
def unauth_client():
    """Client with no auth dependency override (enforces auth)."""
    # Otros módulos de test fijan este override al importarse: se restaura al terminar.
    previous = app.dependency_overrides.pop(get_current_user, None)
    yield TestClient(app)
    _restore_auth_override(previous)


def _restore_auth_override(previous):
    if previous is None:
        app.dependency_overrides.pop(get_current_user, None)
    else:
        app.dependency_overrides[get_current_user] = previous


class TestContentRoutesAuthentication:
    def test_lint_requires_auth(self, unauth_client):
        resp = unauth_client.post("/content/lint", json={"caption": "Test caption"})
        assert resp.status_code in (401, 403)

    def test_humanize_requires_auth(self, unauth_client):
        resp = unauth_client.post("/content/humanize", json={"text": "Test text"})
        assert resp.status_code in (401, 403)

    def test_score_hook_requires_auth(self, unauth_client):
        resp = unauth_client.post("/content/score-hook", json={"hook": "Test hook"})
        assert resp.status_code in (401, 403)

    def test_beats_requires_auth(self, unauth_client):
        resp = unauth_client.post("/content/beats", json={"beats": [{"label": "L1", "text": "T1"}]})
        assert resp.status_code in (401, 403)

    def test_hook_formulas_requires_auth(self, unauth_client):
        resp = unauth_client.get("/content/hook-formulas")
        assert resp.status_code in (401, 403)


class TestContentRoutesValidation:
    def test_lint_invalid_input_yields_422(self, auth_client):
        # Missing required 'caption' field
        resp = auth_client.post("/content/lint", json={"format": "invalid_format_xyz"})
        assert resp.status_code == 422

    def test_humanize_invalid_input_yields_422(self, auth_client):
        # Missing required 'text' field
        resp = auth_client.post("/content/humanize", json={"language": 12345})
        assert resp.status_code == 422

    def test_score_hook_invalid_input_yields_422(self, auth_client):
        # Missing required 'hook' field
        resp = auth_client.post("/content/score-hook", json={})
        assert resp.status_code == 422

    def test_beats_invalid_input_yields_422(self, auth_client):
        # Invalid beats format (not a list of dicts)
        resp = auth_client.post("/content/beats", json={"beats": "not_a_list"})
        assert resp.status_code == 422


class TestContentRoutesNoGeminiCall:
    def test_deterministic_endpoints_never_invoke_gemini(self, auth_client):
        with patch("services.gemini_service.generate_gemini_content") as mock_gemini:
            mock_gemini.side_effect = AssertionError("Gemini MUST NOT be called in deterministic quality endpoints")

            # Route execution checks (once endpoints are implemented by Codex [implementation])
            # If endpoint is not yet mounted (404), this test safely flags it without invoking Gemini.
            endpoints = [
                ("POST", "/content/lint", {"caption": "Un caption simple para validar"}),
                ("POST", "/content/humanize", {"text": "Texto sin slop"}),
                ("POST", "/content/score-hook", {"hook": "Perdí 18.000€ en un contrato"}),
                ("POST", "/content/beats", {"beats": [{"label": "H1", "text": "Gancho inicial"}]}),
                ("GET", "/content/hook-formulas", None),
            ]

            for method, path, payload in endpoints:
                if method == "POST":
                    resp = auth_client.post(path, json=payload)
                else:
                    resp = auth_client.get(path)

                # Ensure Gemini was never called regardless of 200 or 404
                mock_gemini.assert_not_called()


class TestContentRoutesResponses:
    def test_lint_returns_quality_report(self, auth_client):
        resp = auth_client.post("/content/lint", json={"caption": "A" * 130 + " #a #b #c #d #e #f"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["truncated"] is True
        assert body["hashtag_count"] == 6
        assert body["hashtags_over_limit"] == ["#f"]

    def test_humanize_serializes_change_with_from_key(self, auth_client):
        resp = auth_client.post("/content/humanize", json={"text": "Vamos a delve into esto."})
        assert resp.status_code == 200
        body = resp.json()
        assert "delve into" not in body["text"]
        assert body["changes"][0]["from"] == "delve into"

    def test_score_hook_returns_formula(self, auth_client):
        resp = auth_client.post("/content/score-hook", json={"hook": "Perdí 18.000€ por una cláusula"})
        assert resp.status_code == 200
        assert resp.json()["formula_id"] == 3

    def test_beats_rejects_non_positive_wpm(self, auth_client):
        resp = auth_client.post("/content/beats", json={"beats": [{"label": "H", "text": "Hola"}], "wpm": 0})
        assert resp.status_code == 422

    def test_hook_formulas_returns_26(self, auth_client):
        resp = auth_client.get("/content/hook-formulas", params={"strategy_mode": "personal_storyline"})
        assert resp.status_code == 200
        formulas = resp.json()
        assert len(formulas) == 26
        assert "personal_storyline" in formulas[0]["best_for"]
