import asyncio
import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from services import media_thumbnails
from services.media_thumbnails import get_thumbnail, render_all_sizes


def _image_bytes(fmt: str = "JPEG", size=(3024, 4032)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (200, 80, 40)).save(out, format=fmt)
    return out.getvalue()


def _noisy_jpeg(size=(3024, 4032)) -> bytes:
    """JPEG con ruido (comprime mal): el caso pesimista para el tamaño de la miniatura."""
    import os
    img = Image.frombytes("RGB", (600, 800), os.urandom(600 * 800 * 3)).resize(size)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=95)
    return out.getvalue()


@pytest.fixture(autouse=True)
def _empty_cache():
    media_thumbnails.clear_cache()
    yield
    media_thumbnails.clear_cache()


def _storage_response(data: bytes) -> MagicMock:
    response = MagicMock()
    response.content = data
    return response


def test_storage_thumbnail_is_small_webp_with_longest_side_equal_to_size():
    with patch("services.media_thumbnails.requests.get", return_value=_storage_response(_noisy_jpeg())):
        data = asyncio.run(get_thumbnail("storage", "https://x.test/a.jpg", 320))

    img = Image.open(io.BytesIO(data))
    assert img.format == "WEBP"
    assert max(img.size) == 320
    assert len(data) <= 80 * 1024


def test_cache_hit_does_not_download_again():
    with patch("services.media_thumbnails.requests.get", return_value=_storage_response(_image_bytes())) as get:
        first = asyncio.run(get_thumbnail("storage", "https://x.test/a.jpg", 160))
        second = asyncio.run(get_thumbnail("storage", "https://x.test/a.jpg", 160))

    assert first == second
    assert get.call_count == 1


def test_cache_key_changes_with_source_and_size():
    with patch("services.media_thumbnails.requests.get", return_value=_storage_response(_image_bytes())) as get:
        asyncio.run(get_thumbnail("storage", "https://x.test/a.jpg", 160))
        asyncio.run(get_thumbnail("storage", "https://x.test/b.jpg", 160))
        asyncio.run(get_thumbnail("storage", "https://x.test/a.jpg", 320))

    assert get.call_count == 3


def test_lru_evicts_least_recently_used(monkeypatch):
    monkeypatch.setattr(media_thumbnails, "CACHE_MAX_ENTRIES", 2)
    with patch("services.media_thumbnails.requests.get", return_value=_storage_response(_image_bytes())) as get:
        asyncio.run(get_thumbnail("storage", "https://x.test/a.jpg", 160))
        asyncio.run(get_thumbnail("storage", "https://x.test/b.jpg", 160))
        asyncio.run(get_thumbnail("storage", "https://x.test/a.jpg", 160))  # a pasa a ser la más reciente
        asyncio.run(get_thumbnail("storage", "https://x.test/c.jpg", 160))  # expulsa b
        assert get.call_count == 3
        asyncio.run(get_thumbnail("storage", "https://x.test/a.jpg", 160))
        assert get.call_count == 3
        asyncio.run(get_thumbnail("storage", "https://x.test/b.jpg", 160))
        assert get.call_count == 4


def test_storage_video_returns_none_without_downloading():
    with patch("services.media_thumbnails.requests.get") as get:
        assert asyncio.run(get_thumbnail("storage", "https://x.test/reel.MP4?t=1", 320)) is None
    get.assert_not_called()


def test_drive_uses_google_thumbnail():
    drive = MagicMock()
    drive.get_thumbnail_bytes.return_value = _image_bytes(size=(240, 320))
    with patch("services.media_thumbnails.get_drive_connector", return_value=drive):
        data = asyncio.run(get_thumbnail("drive", "file-1", 320, user_id="u1"))

    drive.get_thumbnail_bytes.assert_called_once_with("file-1", 320)
    drive.get_image_bytes.assert_not_called()
    assert Image.open(io.BytesIO(data)).format == "WEBP"


def test_drive_without_thumbnail_link_falls_back_to_resized_original():
    drive = MagicMock()
    drive.get_thumbnail_bytes.return_value = None
    drive.get_image_bytes.return_value = (_image_bytes(), "image/jpeg")
    with patch("services.media_thumbnails.get_drive_connector", return_value=drive):
        data = asyncio.run(get_thumbnail("drive", "file-1", 160, user_id="u1"))

    assert max(Image.open(io.BytesIO(data)).size) == 160


def test_drive_video_without_thumbnail_returns_none():
    drive = MagicMock()
    drive.get_thumbnail_bytes.return_value = None
    drive.get_image_bytes.return_value = (b"not-an-image", "video/mp4")
    with patch("services.media_thumbnails.get_drive_connector", return_value=drive):
        assert asyncio.run(get_thumbnail("drive", "file-1", 160, user_id="u1")) is None


def test_drive_cache_is_per_user():
    drive = MagicMock()
    drive.get_thumbnail_bytes.return_value = _image_bytes(size=(160, 160))
    with patch("services.media_thumbnails.get_drive_connector", return_value=drive) as get_connector:
        asyncio.run(get_thumbnail("drive", "file-1", 160, user_id="u1"))
        asyncio.run(get_thumbnail("drive", "file-1", 160, user_id="u2"))

    assert get_connector.call_count == 2


def test_heic_original_is_converted():
    try:
        heic = _image_bytes(fmt="HEIF", size=(1200, 1600))
    except Exception:
        pytest.skip("pillow-heif sin codificador HEIF en este entorno")
    drive = MagicMock()
    drive.get_thumbnail_bytes.return_value = None
    drive.get_image_bytes.return_value = (heic, "image/heic")
    with patch("services.media_thumbnails.get_drive_connector", return_value=drive):
        data = asyncio.run(get_thumbnail("drive", "file-heic", 320, user_id="u1"))

    img = Image.open(io.BytesIO(data))
    assert img.format == "WEBP"
    assert img.size == (240, 320)


def test_drive_thumbnail_link_size_is_replaced():
    from services.google_drive_connector import GoogleDriveConnector

    connector = GoogleDriveConnector()
    session = MagicMock()
    session.get.side_effect = [
        MagicMock(json=lambda: {"thumbnailLink": "https://lh3.googleusercontent.com/abc=s220"}),
        MagicMock(content=b"thumb"),
    ]
    with patch.object(connector, "_session", return_value=session):
        assert connector.get_thumbnail_bytes("file-1", 640) == b"thumb"

    assert session.get.call_args_list[1].args[0] == "https://lh3.googleusercontent.com/abc=s640"


def test_render_all_sizes_makes_four_webps_with_one_drive_call():
    drive = MagicMock()
    drive.get_thumbnail_bytes.return_value = _image_bytes(size=(480, 640))
    with patch("services.media_thumbnails.get_drive_connector", return_value=drive):
        sizes = asyncio.run(render_all_sizes("drive", "file-1", user_id="u1"))

    drive.get_thumbnail_bytes.assert_called_once_with("file-1", 640)
    drive.get_image_bytes.assert_not_called()
    assert sorted(sizes) == [160, 320, 480, 640]
    for size, data in sizes.items():
        img = Image.open(io.BytesIO(data))
        assert img.format == "WEBP"
        assert max(img.size) == size


def test_render_all_sizes_downloads_storage_original_once_and_weighs_as_today():
    original = _noisy_jpeg()
    with patch("services.media_thumbnails.requests.get", return_value=_storage_response(original)) as get:
        sizes = asyncio.run(render_all_sizes("storage", "https://x.test/a.jpg"))

    get.assert_called_once()
    for size in (160, 320, 480, 640):  # reducir en cadena no pesa más que reducir desde el original
        assert len(sizes[size]) <= len(media_thumbnails.to_thumbnail(original, size)) * 1.05


def test_render_all_sizes_is_cached_and_shared_with_get_thumbnail():
    with patch("services.media_thumbnails.requests.get", return_value=_storage_response(_image_bytes())) as get:
        first = asyncio.run(render_all_sizes("storage", "https://x.test/a.jpg"))
        second = asyncio.run(render_all_sizes("storage", "https://x.test/a.jpg"))
        single = asyncio.run(get_thumbnail("storage", "https://x.test/a.jpg", 320))

    assert get.call_count == 1
    assert first == second
    assert single == first[320]


def test_render_all_sizes_of_storage_video_is_none():
    with patch("services.media_thumbnails.requests.get") as get:
        assert asyncio.run(render_all_sizes("storage", "https://x.test/reel.mp4")) is None
    get.assert_not_called()
