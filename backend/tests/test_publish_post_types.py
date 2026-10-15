"""Los Reels guardados desde el Studio se publican como REELS (job programado y "Publicar ahora")."""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app
from auth.dependencies import get_current_user, get_user_supabase_client
from models.schemas import User
from services.scheduler.post_scheduler import publish_post_job
from tests.conftest import USER_ID

STUDIO_REEL = {
    "id": 5, "user_id": USER_ID, "content": "Gancho\nCuerpo", "media_url": "https://x/v.mp4",
    "post_type": "reel", "content_format": "reel", "trial_graduation": "MANUAL",
    "status": "draft", "instagram_account_id": 3,
}


def test_scheduled_job_publishes_studio_reel_as_reels():
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = \
        MagicMock(data={**STUDIO_REEL, "status": "scheduled"})
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = \
        MagicMock(data={"id": 3, "telegram_chat_id": None, "drive_folder_id": None})
    publisher = MagicMock()
    publisher.publish_post.return_value = {"id": "ig-1"}
    publisher.get_publishing_quota.return_value = None

    with patch("services.scheduler.post_scheduler.get_supabase_admin_client", return_value=db), \
         patch("services.scheduler.post_scheduler.InstagramPublisher", return_value=publisher):
        publish_post_job(5)

    kwargs = publisher.publish_post.call_args.kwargs
    assert kwargs["post_type"] == "REELS"
    assert kwargs["video_url"] == "https://x/v.mp4"
    assert kwargs["trial_graduation"] == "MANUAL"


def _publish_now(post, body=None, quota=None, expected_status=200):
    async def user():
        return User(id=USER_ID, email="t@example.com")

    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = \
        MagicMock(data=post)
    publisher = MagicMock()
    publisher.publish_post.return_value = {"id": "ig-1", "permalink": "https://instagram.com/p/1"}
    publisher.get_publishing_quota.return_value = quota
    prev_user = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = user
    app.dependency_overrides[get_user_supabase_client] = lambda: db
    try:
        with patch("routes.posts_routes.InstagramPublisher", return_value=publisher):
            resp = TestClient(app).post("/api/posts/5/publish", json=body or {})
    finally:
        app.dependency_overrides.pop(get_user_supabase_client, None)
        if prev_user is not None:
            app.dependency_overrides[get_current_user] = prev_user
    assert resp.status_code == expected_status, resp.text
    if expected_status != 200:
        return resp.json(), publisher
    return publisher.publish_post.call_args.kwargs


def test_publish_now_uses_saved_type_and_content():
    kwargs = _publish_now(STUDIO_REEL)
    assert kwargs["post_type"] == "REELS"
    assert kwargs["video_url"] == "https://x/v.mp4"
    assert kwargs["caption"] == "Gancho\nCuerpo"  # antes leía post['caption'], que no existe
    assert kwargs["trial_graduation"] == "MANUAL"


def test_publish_now_explicit_post_type_overrides():
    kwargs = _publish_now(STUDIO_REEL, {"post_type": "FEED"})
    assert kwargs["post_type"] == "FEED"
    assert kwargs["video_url"] is None


def test_publish_now_without_quota_returns_429_and_does_not_publish():
    body, publisher = _publish_now(STUDIO_REEL, quota={"quota_usage": 100, "quota_total": 100}, expected_status=429)
    assert body["code"] == "PUBLISH_QUOTA_EXCEEDED"
    publisher.publish_post.assert_not_called()
