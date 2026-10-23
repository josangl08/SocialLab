"""Sugerencias de configuración a partir de referentes (AD-11)."""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from auth.dependencies import get_current_user
from main import app
from models.schemas import User
from services import reference_accounts as ra
from tests.conftest import USER_ID
from tests.fake_supabase import FakeSupabase

ACCOUNT = {"id": 7, "content_pillars": ["masamadre"], "content_type_mix": {"post": 2, "reel": 1, "carousel": 0, "story": 1}}


def _ref(username, themes, mix=None, ppw=1.0):
    return {"username": username, "status": "ok", "themes": themes, "posts_per_week": ppw,
            "format_mix": mix or {"REELS": 33, "CAROUSEL_ALBUM": 0, "IMAGE": 67}}


def _run(analysis, pending=None):
    fake = FakeSupabase({"agent_decisions": pending or []})
    with patch.object(ra, "get_supabase_admin_client", return_value=fake), \
            patch.object(ra, "record_agent_decision") as record:
        created = ra.suggest_from_references(ACCOUNT, {"references": analysis})
    return created, record


def test_new_pillar_from_recurring_theme():
    created, record = _run([_ref("a", {"fermentación": 1, "masamadre": 2}), _ref("b", {"fermentación": 1})])
    assert created == ["suggest_pillars_change"]
    kwargs = record.call_args.kwargs
    assert kwargs["status"] == "suggested"
    assert kwargs["session_id"] is None
    assert kwargs["tool_args"]["source"] == "reference_accounts"
    assert kwargs["tool_args"]["suggested_content_pillars"] == ["masamadre", "fermentación"]


def test_no_pillar_for_single_mention_or_existing_pillar():
    created, record = _run([_ref("a", {"fermentación": 1, "masamadre": 3})])
    assert created == []
    record.assert_not_called()


def test_mix_gap_over_20pp_redistributes_same_total():
    reels_heavy = {"REELS": 80, "CAROUSEL_ALBUM": 20, "IMAGE": 0}
    created, record = _run([_ref("a", {}, reels_heavy), _ref("b", {}, reels_heavy)])
    assert created == ["suggest_mix_change"]
    mix = record.call_args.kwargs["tool_args"]["suggested_content_type_mix"]
    assert mix == {"post": 0, "reel": 2, "carousel": 1, "story": 1}  # mismo total de feed (3), stories intactas


def test_frequency_raises_total_by_one_only():
    created, record = _run([_ref("a", {}, ppw=7.0), _ref("b", {}, ppw=6.0)])
    assert created == ["suggest_mix_change"]
    kwargs = record.call_args.kwargs
    mix = kwargs["tool_args"]["suggested_content_type_mix"]
    assert mix["post"] + mix["reel"] + mix["carousel"] == 4
    assert "subir solo una publicación" in kwargs["rationale"]


def test_no_duplicate_while_identical_suggestion_pending():
    analysis = [_ref("a", {"fermentación": 2})]
    pending = [{"account_id": 7, "status": "suggested", "decision_type": "suggest_pillars_change",
                "tool_args": {"suggested_content_pillars": ["masamadre", "fermentación"]}}]
    created, record = _run(analysis, pending)
    assert created == []
    record.assert_not_called()


def test_ignores_references_with_errors():
    created, _ = _run([{"username": "x", "status": "not_found"}])
    assert created == []


async def _mock_user():
    return User(id=USER_ID, email="test@example.com")


def test_accepting_pillars_suggestion_writes_config():
    app.dependency_overrides[get_current_user] = _mock_user
    client = TestClient(app)
    decision = {"id": 5, "account_id": 7, "status": "suggested", "decision_type": "suggest_pillars_change",
                "tool_args": {"suggested_content_pillars": ["masamadre", "fermentación"]}}
    with patch("routes.agent_routes.admin_supabase") as admin:
        tables = {}

        def table(name):
            t = tables.setdefault(name, MagicMock())
            t.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[decision] if name == "agent_decisions" else [{"user_id": USER_ID}]
            )
            return t
        admin.table.side_effect = table
        res = client.post("/api/agent/decisions/5/accept-suggestion")

    assert res.status_code == 200
    assert res.json()["config_column"] == "content_pillars"
    tables["instagram_accounts"].update.assert_called_once_with({"content_pillars": ["masamadre", "fermentación"]})
