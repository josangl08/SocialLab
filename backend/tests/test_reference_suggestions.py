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


def _ref(username, captions=None, mix=None, ppw=1.0, comparable=True):
    return {"username": username, "status": "ok", "top_captions": captions or [], "posts_per_week": ppw,
            "format_mix": mix or {"REELS": 33, "CAROUSEL_ALBUM": 0, "IMAGE": 67}, "comparable": comparable}


def _run(analysis, pending=None, gemini='{"pillars": []}'):
    fake = FakeSupabase({"agent_decisions": pending or []})
    gemini_mock = MagicMock(side_effect=gemini) if isinstance(gemini, Exception) else MagicMock(return_value=gemini)
    with patch.object(ra, "get_supabase_admin_client", return_value=fake), \
            patch.object(ra, "generate_gemini_content_sync", gemini_mock), \
            patch.object(ra, "record_agent_decision") as record:
        created = ra.suggest_from_references(ACCOUNT, {"references": analysis})
    return created, record, gemini_mock


def test_new_pillar_from_gemini_themes():
    created, record, gemini = _run(
        [_ref("a", ["Fermentación lenta en casa"]), _ref("b", ["Mi masa madre fermentando 48 h"])],
        gemini='{"pillars": ["Fermentación", "masamadre"]}',
    )
    assert created == ["suggest_pillars_change"]
    prompt = gemini.call_args.args[0]
    assert "@a: Fermentación lenta en casa" in prompt and "masamadre" in prompt and "español" in prompt
    kwargs = record.call_args.kwargs
    assert kwargs["status"] == "suggested"
    assert kwargs["session_id"] is None
    assert kwargs["tool_args"]["source"] == "reference_accounts"
    # El pilar ya existente que repite Gemini no se vuelve a añadir
    assert kwargs["tool_args"]["suggested_content_pillars"] == ["masamadre", "Fermentación"]


def test_no_pillar_when_gemini_finds_none_or_fails():
    created, record, _ = _run([_ref("a", ["x"])], gemini='{"pillars": []}')
    assert created == []
    created, record, _ = _run([_ref("a", ["x"])], gemini=RuntimeError("429"))
    assert created == []
    record.assert_not_called()


def test_no_gemini_call_without_captions():
    _, _, gemini = _run([_ref("a")])
    gemini.assert_not_called()


def test_mix_gap_over_20pp_redistributes_same_total():
    reels_heavy = {"REELS": 80, "CAROUSEL_ALBUM": 20, "IMAGE": 0}
    created, record, _ = _run([_ref("a", mix=reels_heavy), _ref("b", mix=reels_heavy)])
    assert created == ["suggest_mix_change"]
    mix = record.call_args.kwargs["tool_args"]["suggested_content_type_mix"]
    assert mix == {"post": 0, "reel": 2, "carousel": 1, "story": 1}  # mismo total de feed (3), stories intactas


def test_frequency_raises_total_by_one_only():
    created, record, _ = _run([_ref("a", ppw=7.0), _ref("b", ppw=6.0)])
    assert created == ["suggest_mix_change"]
    kwargs = record.call_args.kwargs
    mix = kwargs["tool_args"]["suggested_content_type_mix"]
    assert mix["post"] + mix["reel"] + mix["carousel"] == 4
    assert "subir solo una publicación" in kwargs["rationale"]


def test_non_comparable_references_do_not_drive_mix_or_frequency():
    reels_heavy = {"REELS": 80, "CAROUSEL_ALBUM": 20, "IMAGE": 0}
    created, record, _ = _run([_ref("natgeo", mix=reels_heavy, ppw=7.0, comparable=False)])
    assert created == []
    record.assert_not_called()


def test_no_duplicate_while_identical_suggestion_pending():
    analysis = [_ref("a", ["x"])]
    pending = [{"account_id": 7, "status": "suggested", "decision_type": "suggest_pillars_change",
                "tool_args": {"suggested_content_pillars": ["masamadre", "fermentación"]}}]
    created, record, _ = _run(analysis, pending, gemini='{"pillars": ["fermentación"]}')
    assert created == []
    record.assert_not_called()


def test_ignores_references_with_errors():
    created, _, _ = _run([{"username": "x", "status": "not_found"}])
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
