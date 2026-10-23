"""PATCH /api/agent/config, diagnóstico, generate-strategy y dismiss-suggestion (Fase B)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from auth.dependencies import get_current_user
from main import app
from models.schemas import User
from tests.conftest import USER_ID


async def _mock_user():
    return User(id=USER_ID, email="test@example.com")


app.dependency_overrides[get_current_user] = _mock_user
client = TestClient(app)


@pytest.fixture
def admin():
    with patch("routes.agent_routes.admin_supabase") as mock_admin:
        yield mock_admin


def _account_rows(admin, row):
    admin.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[row])


def test_patch_writes_only_sent_fields(admin):
    _account_rows(admin, {"user_id": USER_ID, "content_type_mix": {"reel": 3}, "default_tone": "casual"})

    res = client.patch("/api/agent/config/7", json={"content_type_mix": {"reel": 3}, "best_times": []})

    assert res.status_code == 200
    admin.table.return_value.update.assert_called_once_with({"content_type_mix": {"reel": 3}, "best_times": []})
    body = res.json()
    assert body["content_type_mix"] == {"reel": 3}
    assert body["default_tone"] == "casual"


def test_patch_null_caption_voice_is_written(admin):
    _account_rows(admin, {"user_id": USER_ID})
    client.patch("/api/agent/config/7", json={"caption_voice": None})
    admin.table.return_value.update.assert_called_once_with({"caption_voice": None})


def test_patch_other_user_account_is_forbidden(admin):
    _account_rows(admin, {"user_id": "someone-else"})
    res = client.patch("/api/agent/config/7", json={"sector": "x"})
    assert res.status_code == 403
    admin.table.return_value.update.assert_not_called()


def test_patch_rejects_six_references(admin):
    _account_rows(admin, {"user_id": USER_ID})
    res = client.patch("/api/agent/config/7", json={"reference_accounts": list("abcdef")})
    assert res.status_code == 422


def test_put_rejects_six_references(admin):
    _account_rows(admin, {"user_id": USER_ID})
    res = client.put("/api/agent/config/7", json={"reference_accounts": list("abcdef")})
    assert res.status_code == 422


def test_put_without_posting_frequency_does_not_write_it(admin):
    _account_rows(admin, {"user_id": USER_ID})
    res = client.put("/api/agent/config/7", json={"sector": "cocina"})
    assert res.status_code == 200
    written = admin.table.return_value.update.call_args[0][0]
    assert "posting_frequency" not in written


def test_get_config_keeps_empty_best_times_and_wizard_answers(admin):
    answers = {"dedica": ["Gastronomía"], "answered_at": "2026-10-20T10:00:00+00:00"}
    _account_rows(admin, {"user_id": USER_ID, "best_times": [], "strategy_wizard_answers": answers})
    body = client.get("/api/agent/config/7").json()
    assert body["best_times"] == []
    assert body["strategy_wizard_answers"] == answers


def test_diagnostics_returns_issues_preview_and_audit(admin):
    _account_rows(admin, {
        "user_id": USER_ID, "account_type": "professional", "scheduling_mode": "fixed",
        "preferred_days": [], "content_type_mix": {"reel": 2}, "default_language": "en",
    })
    with patch("routes.agent_routes.AnalyticsService") as mock_service:
        mock_service.return_value.get_empirical_scheduling_data.return_value = {"has_data": False}
        res = client.get("/api/agent/strategy/7/diagnostics")

    assert res.status_code == 200
    body = res.json()
    codes = {i["code"] for i in body["issues"]}
    assert "FIXED_NO_DAYS" in codes
    assert "Tipo de cuenta: profesional." in body["context_preview"]
    assert "Idioma de los captions: inglés." in body["context_preview"]
    assert "Estrategia de Hashtags por Capas" not in body["context_preview"]
    assert isinstance(body["profile_audit"]["score"], int)
    assert body["profile_audit"]["items"]


def test_diagnostics_forbidden_for_other_user(admin):
    _account_rows(admin, {"user_id": "someone-else"})
    assert client.get("/api/agent/strategy/7/diagnostics").status_code == 403


def test_generate_strategy_saves_answers_without_touching_config(admin):
    _account_rows(admin, {"user_id": USER_ID})
    generated = {"account_type": "personal", "posting_frequency": "daily", "content_pillars": ["a"]}
    with patch("routes.agent_routes.generate_gemini_content", new=AsyncMock(return_value="{}")), \
            patch("routes.agent_routes.clean_and_parse_json", new=AsyncMock(return_value=dict(generated))):
        res = client.post("/api/agent/generate-strategy", json={
            "account_id": 7, "dedica": ["Gastronomía"], "contenido": [], "objetivo": ["Vender"], "referentes": ["chef"],
        })

    assert res.status_code == 200
    assert "posting_frequency" not in res.json()
    written = admin.table.return_value.update.call_args[0][0]
    assert list(written) == ["strategy_wizard_answers"]
    assert written["strategy_wizard_answers"]["dedica"] == ["Gastronomía"]
    assert written["strategy_wizard_answers"]["referentes"] == ["chef"]
    assert "answered_at" in written["strategy_wizard_answers"]


def test_generate_strategy_without_account_writes_nothing(admin):
    with patch("routes.agent_routes.generate_gemini_content", new=AsyncMock(return_value="{}")), \
            patch("routes.agent_routes.clean_and_parse_json", new=AsyncMock(return_value={})):
        res = client.post("/api/agent/generate-strategy", json={"dedica": []})
    assert res.status_code == 200
    admin.table.return_value.update.assert_not_called()


def _decision(admin, status):
    def table(name):
        t = MagicMock()
        if name == "agent_decisions":
            t.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": 5, "account_id": 7, "status": status, "decision_type": "suggest_mix_change"}]
            )
        else:
            t.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"user_id": USER_ID}])
        admin.tables[name] = t
        return t
    admin.tables = {}
    admin.table.side_effect = table


def test_dismiss_suggestion(admin):
    _decision(admin, "suggested")
    res = client.post("/api/agent/decisions/5/dismiss-suggestion")
    assert res.status_code == 200
    assert res.json() == {"dismissed": True}
    written = admin.tables["agent_decisions"].update.call_args[0][0]
    assert written["status"] == "dismissed"
    assert "dismissed_at" in written
    admin.tables["instagram_accounts"].update.assert_not_called()


def test_dismiss_non_pending_suggestion_conflicts(admin):
    _decision(admin, "accepted")
    assert client.post("/api/agent/decisions/5/dismiss-suggestion").status_code == 409


def test_list_decisions_filters_by_status(admin):
    _account_rows(admin, {"user_id": USER_ID})
    with patch("routes.agent_routes._orphan_decision_ids", return_value=[]):
        client.get("/api/agent/decisions?account_id=7&status=suggested")
    eq_calls = [c.args for c in admin.table.return_value.select.return_value.eq.return_value.eq.call_args_list]
    assert ("status", "suggested") in eq_calls


def test_reference_accounts_endpoint_respects_refresh_flag(admin):
    _account_rows(admin, {"user_id": USER_ID})
    analysis = {"references": [{"username": "chef", "status": "not_professional", "error_message": "x"}],
                "summary": "", "refreshed": True}
    with patch("routes.agent_routes.analyze_reference_accounts", return_value=analysis) as analyze:
        res = client.get("/api/agent/reference-accounts/7?refresh=true")
    assert res.status_code == 200
    assert res.json()["references"][0]["status"] == "not_professional"
    analyze.assert_called_once_with(7, True)


def test_patch_references_cleans_removed_snapshots(admin, no_reference_snapshot_cleanup):
    _account_rows(admin, {"user_id": USER_ID})
    client.patch("/api/agent/config/7", json={"reference_accounts": ["@chef", "pan"]})
    no_reference_snapshot_cleanup.assert_called_once_with(7, ["chef", "pan"])
