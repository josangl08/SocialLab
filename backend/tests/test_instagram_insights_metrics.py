"""Fase E: métricas nuevas pedidas a la Graph API (shares, reels_skip_rate, AD-9)."""
from unittest.mock import patch

from services.instagram_insights import InstagramInsightsService


def _service():
    return InstagramInsightsService("token", "ig-1", "facebook")


def _values(**metrics):
    return {"data": [{"name": k, "values": [{"value": v}]} for k, v in metrics.items()]}


def test_media_insights_requests_shares():
    svc = _service()
    with patch.object(svc, "_make_request", return_value=_values(reach=100, shares=7, views=300)) as req:
        insights = svc.get_media_insights("m1", "IMAGE")
    assert "shares" in req.call_args_list[0].args[1]["metric"].split(",")
    assert insights["shares"] == 7
    assert req.call_count == 1  # sin llamadas extra para posts que no son vídeo


def test_reel_insights_include_skip_rate():
    svc = _service()
    responses = [_values(reach=100), _values(ig_reels_avg_watch_time=1200, reels_skip_rate=35.5)]
    with patch.object(svc, "_make_request", side_effect=responses) as req:
        insights = svc.get_media_insights("m1", "VIDEO")
    assert "reels_skip_rate" in req.call_args_list[1].args[1]["metric"]
    assert insights["reels_skip_rate"] == 35.5
    assert req.call_count == 2


def test_reel_insights_fallback_without_skip_rate():
    """Si la API rechaza reels_skip_rate se reintenta sin ella y se conserva el watch time."""
    svc = _service()
    responses = [_values(reach=100), RuntimeError("metric not supported"), _values(ig_reels_avg_watch_time=900)]
    with patch.object(svc, "_make_request", side_effect=responses) as req:
        insights = svc.get_media_insights("m1", "VIDEO")
    assert "reels_skip_rate" not in req.call_args_list[2].args[1]["metric"]
    assert insights["ig_reels_avg_watch_time"] == 900
    assert "reels_skip_rate" not in insights


def _breakdown(*rows):
    return {"data": [{"total_value": {"breakdowns": [{"results": [
        {"dimension_values": [dim], "value": v} for dim, v in rows
    ]}]}}]}


def test_account_insights_follows_and_contact_taps():
    svc = _service()

    def fake_request(endpoint, params):
        metric = params.get("metric")
        if metric == "follows_and_unfollows":
            assert params["breakdown"] == "follow_type"
            return _breakdown(("FOLLOWER", 120), ("NON_FOLLOWER", 30))
        if metric == "profile_links_taps":
            assert params["breakdown"] == "contact_button_type"
            return _breakdown(("CALL", 2), ("EMAIL", 3))
        return {"data": []}

    with patch.object(svc, "_make_request", side_effect=fake_request):
        insights = svc.get_account_insights()
    assert insights["follows"] == 120
    assert insights["unfollows"] == 30
    assert insights["profile_links_taps"] == 5


def test_account_insights_growth_defaults_when_unavailable():
    """Cuentas sin acceso a estas métricas (p. ej. < 100 seguidores) -> 0, sin romper el sync."""
    svc = _service()

    def fake_request(endpoint, params):
        if params.get("metric") in ("follows_and_unfollows", "profile_links_taps"):
            raise RuntimeError("not available")
        return {"data": []}

    with patch.object(svc, "_make_request", side_effect=fake_request):
        insights = svc.get_account_insights()
    assert (insights["follows"], insights["unfollows"], insights["profile_links_taps"]) == (0, 0, 0)


def test_insights_service_base_url_by_login_type():
    """AD-2: InstagramInsightsService(login_type) configura self.base_url según login_type."""
    svc_fb = InstagramInsightsService("token", "ig-1", login_type="facebook")
    svc_ig = InstagramInsightsService("token", "ig-1", login_type="instagram")

    assert svc_fb.base_url.startswith("https://graph.facebook.com/")
    assert svc_ig.base_url.startswith("https://graph.instagram.com/")
