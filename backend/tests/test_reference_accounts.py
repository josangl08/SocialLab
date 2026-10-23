"""Análisis de referentes con Business Discovery (AD-10), Graph API simulada."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from services import reference_accounts as ra
from tests.fake_supabase import FakeSupabase

NOW = datetime.now(timezone.utc)


def _media(days_ago: int, likes: int, comments: int = 0, kind: str = "IMAGE", caption: str = "Hola"):
    return {
        "caption": caption, "media_type": "VIDEO" if kind == "REELS" else kind,
        "media_product_type": "REELS" if kind == "REELS" else "FEED",
        "like_count": likes, "comments_count": comments,
        "timestamp": (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S+0000"),
        "permalink": f"https://instagram.com/p/{days_ago}{likes}",
    }


DISCOVERY = {
    "username": "chef_pro", "followers_count": 1000, "media_count": 120,
    "media": {"data": [
        _media(1, 100, 10, "REELS", "Nadie te cuenta esto sobre el pan\n#masamadre receta"),
        _media(3, 50, 0, "CAROUSEL_ALBUM", "3 errores al hornear\n#masamadre"),
        _media(5, 20, 0, "IMAGE", "Domingo de horno"),
        _media(10, 10, 0, "REELS", "Otra"),
        _media(40, 500, 0, "IMAGE", "Antiguo"),
    ]},
}


def _ok_response(payload):
    resp = MagicMock(ok=True, status_code=200, content=b"{}")
    resp.json.return_value = {"business_discovery": payload, "id": "1"}
    return resp


def _error_response(code: int, subcode=None, message="error"):
    resp = MagicMock(ok=False, status_code=400, content=b"{}")
    resp.json.return_value = {"error": {"code": code, "error_subcode": subcode, "message": message}}
    return resp


def _fake(refs, snapshots=None, login_type="facebook"):
    return FakeSupabase({
        "instagram_accounts": [{
            "id": 7, "reference_accounts": refs, "content_pillars": ["masamadre"],
            "content_type_mix": {"post": 1, "reel": 1, "carousel": 1, "story": 0},
            "instagram_business_account_id": "178", "long_lived_access_token": "enc", "login_type": login_type,
        }],
        "reference_account_snapshots": snapshots or [],
        "agent_decisions": [],
    })


@pytest.fixture
def env():
    def _setup(refs, responses, snapshots=None, login_type="facebook"):
        fake = _fake(refs, snapshots, login_type)
        get = MagicMock(side_effect=responses)
        patches = [
            patch.object(ra, "get_supabase_admin_client", return_value=fake),
            patch.object(ra, "decrypt_token", return_value="token"),
            patch.object(ra.requests, "get", get),
            patch.object(ra, "suggest_from_references", return_value=[]),
        ]
        for p in patches:
            p.start()
        return fake, get, patches
    started = []

    def factory(*a, **kw):
        fake, get, patches = _setup(*a, **kw)
        started.extend(patches)
        return fake, get
    yield factory
    for p in started:
        p.stop()


def test_metrics_from_business_discovery():
    metrics = ra.compute_reference_metrics(DISCOVERY, NOW)
    assert metrics["followers"] == 1000
    assert metrics["posts_per_week"] == 1.0  # 4 posts en 28 días
    assert metrics["format_mix"] == {"REELS": 40, "CAROUSEL_ALBUM": 20, "IMAGE": 40}
    top = metrics["top_posts"]
    assert [p["engagement_rate"] for p in top] == [50.0, 11.0, 5.0]
    assert top[0]["caption_first_line"] == "Antiguo"
    assert top[1]["permalink"].startswith("https://instagram.com/p/")
    assert metrics["median_engagement_rate"] == 5.0
    assert "masamadre" in metrics["themes"]


def test_analysis_calls_api_and_caches(env):
    fake, get = env(["chef_pro"], [_ok_response(DISCOVERY)])
    first = ra.analyze_reference_accounts(7)
    assert first["refreshed"] is True
    assert first["references"][0]["status"] == "ok"
    assert first["references"][0]["followers"] == 1000
    assert "@chef_pro: 1000 seguidores" in first["summary"]
    assert get.call_count == 1
    assert "business_discovery.username(chef_pro)" in get.call_args.kwargs["params"]["fields"]

    second = ra.analyze_reference_accounts(7)
    assert second["refreshed"] is False
    assert get.call_count == 1
    assert len(fake.store["reference_account_snapshots"]) == 1


def test_stale_snapshot_is_refreshed(env):
    old = {"account_id": 7, "username": "chef_pro", "status": "ok", "payload": {},
           "fetched_at": (NOW - timedelta(days=8)).isoformat()}
    _, get = env(["chef_pro"], [_ok_response(DISCOVERY)], snapshots=[old])
    assert ra.analyze_reference_accounts(7)["refreshed"] is True
    assert get.call_count == 1


def test_force_refresh_ignores_cache(env):
    fresh = {"account_id": 7, "username": "chef_pro", "status": "ok", "payload": {}, "fetched_at": NOW.isoformat()}
    _, get = env(["chef_pro"], [_ok_response(DISCOVERY)], snapshots=[fresh])
    ra.analyze_reference_accounts(7, force_refresh=True)
    assert get.call_count == 1


def test_invalid_reference_does_not_break_the_rest(env):
    _, get = env(
        ["personal_user", "chef_pro", "ghost"],
        [_error_response(110, message="Invalid user id"), _ok_response(DISCOVERY),
         _error_response(110, 2207013, "The user with username: ghost cannot be found")],
    )
    refs = {r["username"]: r for r in ra.analyze_reference_accounts(7)["references"]}
    assert refs["personal_user"]["status"] == "not_professional"
    assert "no es una cuenta profesional" in refs["personal_user"]["error_message"]
    assert refs["chef_pro"]["status"] == "ok"
    assert refs["ghost"]["status"] == "not_found"


def test_rate_limit_is_an_error(env):
    env(["chef_pro"], [_error_response(4, message="Application request limit reached")])
    ref = ra.analyze_reference_accounts(7)["references"][0]
    assert ref["status"] == "error"
    assert "Límite" in ref["error_message"]


def test_at_most_five_calls(env):
    _, get = env([f"ref{i}" for i in range(7)], [_ok_response(DISCOVERY)] * 7)
    result = ra.analyze_reference_accounts(7)
    assert get.call_count == 5
    assert len(result["references"]) == 5


def test_errors_cached_24h(env):
    recent_error = {"account_id": 7, "username": "ghost", "status": "not_found", "payload": None,
                    "error_message": "x", "fetched_at": (NOW - timedelta(hours=2)).isoformat()}
    old_error = {**recent_error, "username": "old", "fetched_at": (NOW - timedelta(hours=30)).isoformat()}
    _, get = env(["ghost", "old"], [_error_response(110, 2207013)], snapshots=[recent_error, old_error])
    ra.analyze_reference_accounts(7)
    assert get.call_count == 1
    assert "username(old)" in get.call_args.kwargs["params"]["fields"]


def test_instagram_login_accounts_cannot_use_business_discovery(env):
    _, get = env(["chef_pro"], [], login_type="instagram")
    ref = ra.analyze_reference_accounts(7)["references"][0]
    assert ref["status"] == "error"
    assert "Facebook Login" in ref["error_message"]
    get.assert_not_called()


def test_no_references_no_summary(env):
    _, get = env([], [])
    assert ra.analyze_reference_accounts(7) == {"references": [], "summary": "", "refreshed": False}
    get.assert_not_called()


def test_summary_empty_when_nothing_analysable():
    assert ra.summarize_references({"references": [{"username": "x", "status": "not_found"}]}) == ""


def test_delete_stale_snapshots():
    fake = FakeSupabase({"reference_account_snapshots": [
        {"id": 1, "account_id": 7, "username": "keep"},
        {"id": 2, "account_id": 7, "username": "gone"},
        {"id": 3, "account_id": 8, "username": "gone"},
    ]})
    with patch.object(ra, "get_supabase_admin_client", return_value=fake):
        ra.delete_stale_snapshots(7, ["@keep"])
    assert [s["id"] for s in fake.store["reference_account_snapshots"]] == [1, 3]


def test_long_first_line_is_cut_at_125_chars():
    long_caption = "x" * 300
    data = {"followers_count": 10, "media": {"data": [_media(1, 5, 0, "IMAGE", long_caption)]}}
    line = ra.compute_reference_metrics(data, NOW)["top_posts"][0]["caption_first_line"]
    assert len(line) == 126 and line.endswith("…")
