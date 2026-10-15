"""Sync de posts de Instagram: portada de vídeos y colaboraciones (persistent-thumbnails, AD-9, AD-10)."""
from unittest.mock import MagicMock, patch

from services.instagram_insights import InstagramInsightsService

VIDEO = {"id": "ig-v", "media_type": "VIDEO", "media_url": "https://cdn.test/v.mp4?oe=1",
         "thumbnail_url": "https://cdn.test/v.jpg?oe=1", "timestamp": "2026-10-01T10:00:00+0000"}
COPYRIGHT_VIDEO = {"id": "ig-c", "media_type": "VIDEO", "thumbnail_url": "https://cdn.test/c.jpg",
                   "timestamp": "2026-10-02T10:00:00+0000"}


COLLAB = {"id": "ig-x", "media_type": "IMAGE", "media_url": "https://cdn.test/x.jpg",
          "caption": "Colaboración", "timestamp": "2026-08-04T01:48:43+0000"}


def _sync(media: list[dict], collaborations=None) -> tuple[list[dict], MagicMock]:
    """Ejecuta el sync y devuelve las filas enviadas al upsert de `posts` y el cliente simulado.
    `collaborations`: respuesta de `collaborative_media` (o una excepción)."""
    svc = InstagramInsightsService("token", "ig-1")
    db = MagicMock()
    collab_response = {"data": collaborations or []}
    request = MagicMock(side_effect=collaborations) if isinstance(collaborations, Exception) \
        else MagicMock(return_value=collab_response)
    with patch.object(svc, "_get_all_media_paginated", return_value=media), \
            patch.object(svc, "_make_request", request), \
            patch("services.instagram_insights.time.sleep"):
        svc.sync_posts_to_database(db, user_id="u1", instagram_account_id_db=7)
    rows: list[dict] = []
    for call in db.table.return_value.upsert.call_args_list:
        if call.kwargs.get("on_conflict") == "instagram_post_id":
            rows.extend(call.args[0])
    return rows, request


def test_sync_stores_video_cover():
    rows = {r["instagram_post_id"]: r for r in _sync([VIDEO, COPYRIGHT_VIDEO])[0]}

    assert rows["ig-v"]["media_thumbnail_url"] == "https://cdn.test/v.jpg?oe=1"
    assert rows["ig-c"]["media_url"] is None
    assert rows["ig-c"]["media_thumbnail_url"] == "https://cdn.test/c.jpg"


def test_sync_requests_thumbnail_url_field():
    svc = InstagramInsightsService("token", "ig-1")
    with patch.object(svc, "_make_request", return_value={"data": []}) as req:
        svc._get_all_media_paginated()
    assert "thumbnail_url" in req.call_args.args[1]["fields"].split(",")


def test_sync_adds_accepted_collaborations_flagged():
    rows, request = _sync([VIDEO], [COLLAB])
    by_id = {r["instagram_post_id"]: r for r in rows}

    assert request.call_args.args[0] == "ig-1/collaborative_media"
    assert by_id["ig-x"]["is_collaboration"] is True
    assert by_id["ig-x"]["user_id"] == "u1"
    assert by_id["ig-x"]["status"] == "published"
    assert by_id["ig-x"]["publication_date"] == COLLAB["timestamp"]
    assert by_id["ig-v"]["is_collaboration"] is False
    assert {frozenset(r) for r in rows} == {frozenset(rows[0])}  # mismas columnas en el upsert


def test_collaborations_failure_keeps_own_posts():
    rows, _ = _sync([VIDEO], Exception("Instagram caído"))

    assert [r["instagram_post_id"] for r in rows] == ["ig-v"]


def test_collaborations_follow_pagination():
    svc = InstagramInsightsService("token", "ig-1")
    pages = [{"data": [COLLAB], "paging": {"next": "https://graph.test/next"}},
             {"data": [{**COLLAB, "id": "ig-y"}]}]
    with patch.object(svc, "_make_request", side_effect=pages) as request:
        rows = svc.get_collaboration_post_rows("u1", 7)

    assert [r["instagram_post_id"] for r in rows] == ["ig-x", "ig-y"]
    assert request.call_args_list[1].args[0] == "https://graph.test/next"
