"""Sync de posts de Instagram: portada de vídeos (persistent-thumbnails, AD-9)."""
from unittest.mock import MagicMock, patch

from services.instagram_insights import InstagramInsightsService

VIDEO = {"id": "ig-v", "media_type": "VIDEO", "media_url": "https://cdn.test/v.mp4?oe=1",
         "thumbnail_url": "https://cdn.test/v.jpg?oe=1", "timestamp": "2026-10-01T10:00:00+0000"}
COPYRIGHT_VIDEO = {"id": "ig-c", "media_type": "VIDEO", "thumbnail_url": "https://cdn.test/c.jpg",
                   "timestamp": "2026-10-02T10:00:00+0000"}


def _sync(media: list[dict]) -> list[dict]:
    """Ejecuta el sync y devuelve las filas enviadas al upsert de `posts`."""
    svc = InstagramInsightsService("token", "ig-1")
    db = MagicMock()
    with patch.object(svc, "_get_all_media_paginated", return_value=media), \
            patch("services.instagram_insights.time.sleep"):
        svc.sync_posts_to_database(db, user_id="u1", instagram_account_id_db=7)
    rows: list[dict] = []
    for call in db.table.return_value.upsert.call_args_list:
        if call.kwargs.get("on_conflict") == "instagram_post_id":
            rows.extend(call.args[0])
    return rows


def test_sync_stores_video_cover():
    rows = {r["instagram_post_id"]: r for r in _sync([VIDEO, COPYRIGHT_VIDEO])}

    assert rows["ig-v"]["media_thumbnail_url"] == "https://cdn.test/v.jpg?oe=1"
    assert rows["ig-c"]["media_url"] is None
    assert rows["ig-c"]["media_thumbnail_url"] == "https://cdn.test/c.jpg"


def test_sync_requests_thumbnail_url_field():
    svc = InstagramInsightsService("token", "ig-1")
    with patch.object(svc, "_make_request", return_value={"data": []}) as req:
        svc._get_all_media_paginated()
    assert "thumbnail_url" in req.call_args.args[1]["fields"].split(",")
