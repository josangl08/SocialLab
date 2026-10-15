import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from auth.dependencies import get_current_user_from_query_token, get_user_supabase_client_from_query_token
from main import app
from models.schemas import User
from services import media_thumbnails
from tests.conftest import USER_ID

client = TestClient(app)
_OVERRIDDEN = (get_current_user_from_query_token, get_user_supabase_client_from_query_token)


async def _query_user():
    return User(id=USER_ID, email="test@example.com")


@pytest.fixture
def user_db():
    """Usuario autenticado por ?token= y cliente de Supabase (RLS) simulado."""
    previous = {dep: app.dependency_overrides.get(dep) for dep in _OVERRIDDEN}
    db = MagicMock()
    app.dependency_overrides[get_current_user_from_query_token] = _query_user
    app.dependency_overrides[get_user_supabase_client_from_query_token] = lambda: db
    media_thumbnails.clear_cache()
    yield db
    media_thumbnails.clear_cache()
    for dep, value in previous.items():
        if value is None:
            app.dependency_overrides.pop(dep, None)
        else:
            app.dependency_overrides[dep] = value


def _post_rows(db: MagicMock, rows: list) -> None:
    db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
        MagicMock(data=rows)
    )


# --- GET /api/drive/files/{id}/image -----------------------------------------

def test_drive_image_with_size_returns_thumbnail_and_cache_header(user_db):
    with patch("routes.drive_routes.get_thumbnail", return_value=b"jpeg") as get_thumbnail:
        response = client.get("/api/drive/files/f1/image?token=t&size=160")

    assert response.status_code == 200
    assert response.content == b"jpeg"
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["cache-control"] == "private, max-age=86400"
    get_thumbnail.assert_called_once_with("drive", "f1", 160, user_id=USER_ID)


def test_drive_image_with_invalid_size_is_422(user_db):
    assert client.get("/api/drive/files/f1/image?token=t&size=999").status_code == 422


def test_drive_image_without_size_returns_original(user_db):
    drive = MagicMock()
    drive.get_image_bytes.return_value = (b"original", "image/png")
    with patch("routes.drive_routes.get_drive_connector", return_value=drive):
        response = client.get("/api/drive/files/f1/image?token=t")

    assert response.status_code == 200
    assert response.content == b"original"
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, max-age=86400"


def test_drive_image_without_drive_connected_is_401(user_db):
    with patch("routes.drive_routes.get_drive_connector", side_effect=RuntimeError("no creds")):
        assert client.get("/api/drive/files/f1/image?token=t").status_code == 401


def test_drive_download_does_not_block_event_loop(user_db):
    """Dos descargas concurrentes de 0,4 s tardan ~0,4 s y no 0,8 s."""
    def slow_download(file_id):
        time.sleep(0.4)
        return b"original", "image/jpeg"

    drive = MagicMock()
    drive.get_image_bytes.side_effect = slow_download

    async def two_requests():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            start = time.perf_counter()
            responses = await asyncio.gather(
                ac.get("/api/drive/files/a/image?token=t"),
                ac.get("/api/drive/files/b/image?token=t"),
            )
            return responses, time.perf_counter() - start

    with patch("routes.drive_routes.get_drive_connector", return_value=drive):
        responses, elapsed = asyncio.run(two_requests())

    assert all(r.status_code == 200 for r in responses)
    assert elapsed < 0.7


# --- GET /api/posts/{id}/thumbnail -------------------------------------------

def test_post_thumbnail_of_other_user_is_404(user_db):
    _post_rows(user_db, [])  # RLS no devuelve posts ajenos
    assert client.get("/api/posts/42/thumbnail?token=t").status_code == 404


def test_post_thumbnail_without_media_is_404(user_db):
    _post_rows(user_db, [{"user_id": USER_ID, "media_url": None, "drive_file_id": None}])
    assert client.get("/api/posts/42/thumbnail?token=t").status_code == 404


SIZES = {640: b"p640", 480: b"p480", 320: b"p320", 160: b"p160"}
BASE = "https://p.supabase.co/storage/v1/object/public/thumbnails/u/42/abc"


def _render_and_save(sizes=SIZES, save_error=None):
    """Simula la generación (render_all_sizes) y el guardado en Storage (save_thumbnails)."""
    render = patch("routes.posts_routes.render_all_sizes", AsyncMock(return_value=sizes))
    save = patch("services.thumbnail_store.save_thumbnails", AsyncMock(return_value=BASE, side_effect=save_error))
    return render, save


def test_post_thumbnail_already_stored_redirects_to_storage(user_db):
    _post_rows(user_db, [{"user_id": USER_ID, "media_url": None, "drive_file_id": "f1", "thumbnail_url_base": BASE}])
    render, save = _render_and_save()
    with render as render_mock, save:
        response = client.get("/api/posts/42/thumbnail?token=t&size=160", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == f"{BASE}_160.webp"
    assert response.headers["cache-control"] == "private, max-age=86400"
    render_mock.assert_not_called()


def test_post_thumbnail_first_request_saves_and_returns_requested_size(user_db):
    _post_rows(user_db, [{"user_id": USER_ID, "media_url": None, "drive_file_id": "f1", "thumbnail_url_base": None}])
    render, save = _render_and_save()
    with render as render_mock, save as save_mock:
        response = client.get("/api/posts/42/thumbnail?token=t&size=480")

    assert response.status_code == 200
    assert response.content == b"p480"
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["cache-control"] == "private, max-age=86400"
    render_mock.assert_awaited_once_with("drive", "f1", user_id=USER_ID)
    save_mock.assert_awaited_once_with(USER_ID, 42, SIZES, {"media_url": None, "drive_file_id": "f1"})


def test_post_thumbnail_prefers_storage_over_drive(user_db):
    _post_rows(user_db, [{"user_id": USER_ID, "media_url": "https://x.test/a.jpg", "drive_file_id": "f1"}])
    render, save = _render_and_save()
    with render as render_mock, save:
        assert client.get("/api/posts/42/thumbnail?token=t").content == b"p320"

    render_mock.assert_awaited_once_with("storage", "https://x.test/a.jpg", user_id=USER_ID)


def test_post_thumbnail_upload_failure_still_returns_image(user_db):
    _post_rows(user_db, [{"user_id": USER_ID, "media_url": None, "drive_file_id": "f1"}])
    render, save = _render_and_save(save_error=Exception("Storage caído"))
    with render, save:
        response = client.get("/api/posts/42/thumbnail?token=t&size=160")

    assert response.status_code == 200
    assert response.content == b"p160"


def test_post_thumbnail_storage_video_is_404(user_db):
    _post_rows(user_db, [{"user_id": USER_ID, "media_url": "https://x.test/reel.mp4", "drive_file_id": None}])
    with patch("services.media_thumbnails.requests.get") as get, \
            patch("routes.posts_routes.save_in_background", AsyncMock()) as save:
        assert client.get("/api/posts/42/thumbnail?token=t").status_code == 404
    get.assert_not_called()
    save.assert_not_called()


def test_post_thumbnail_source_failure_is_502(user_db):
    _post_rows(user_db, [{"user_id": USER_ID, "media_url": None, "drive_file_id": "f1"}])
    with patch("routes.posts_routes.render_all_sizes", AsyncMock(side_effect=Exception("Drive caído"))):
        assert client.get("/api/posts/42/thumbnail?token=t").status_code == 502


def test_post_thumbnail_invalid_size_is_422(user_db):
    assert client.get("/api/posts/42/thumbnail?token=t&size=50").status_code == 422
