# ABOUTME: Tests de services/post_media.py (preparación de imágenes y original de Drive al aprobar)
# y de PostScheduler.schedule_post con posts que solo tienen drive_file_id.

import io
import os
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from services import post_media
from services.scheduler.post_scheduler import PostScheduler


def _image_bytes(fmt: str, size=(64, 48), noise: bool = False) -> bytes:
    img = Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3)) if noise else Image.new("RGB", size, (10, 20, 30))
    out = io.BytesIO()
    img.save(out, format=fmt, quality=100) if fmt == "JPEG" else img.save(out, format=fmt)
    return out.getvalue()


# --- prepare_image_for_instagram ---

def test_small_jpeg_is_published_untouched():
    original = _image_bytes("JPEG")

    assert post_media.prepare_image_for_instagram(original, "image/jpeg") is original


def test_heic_is_converted_to_jpeg():
    result = post_media.prepare_image_for_instagram(_image_bytes("HEIF"), "image/heic")

    with Image.open(io.BytesIO(result)) as img:
        assert img.format == "JPEG"
        assert img.size == (64, 48)


def test_png_is_converted_to_jpeg():
    result = post_media.prepare_image_for_instagram(_image_bytes("PNG"), "image/png")

    with Image.open(io.BytesIO(result)) as img:
        assert img.format == "JPEG"


def test_oversized_jpeg_is_shrunk_below_limit(monkeypatch):
    monkeypatch.setattr(post_media, "INSTAGRAM_IMAGE_MAX_BYTES", 30_000)
    original = _image_bytes("JPEG", size=(400, 400), noise=True)
    assert len(original) > 30_000

    result = post_media.prepare_image_for_instagram(original, "image/jpeg")

    assert len(result) <= 30_000
    with Image.open(io.BytesIO(result)) as img:
        assert img.format == "JPEG"


# --- materialize_drive_media ---

@pytest.fixture
def drive_and_storage():
    drive = MagicMock()
    drive.service.files.return_value.get.return_value.execute.return_value = {"name": "DJI_0090.JPG", "mimeType": "image/jpeg"}
    drive.download_file_bytes.return_value = _image_bytes("JPEG")
    admin = MagicMock()
    storage = admin.storage.from_.return_value
    storage.get_public_url.return_value = "https://storage.test/posts/drive/53577_f1.jpg"
    with patch("services.google_drive_connector.get_drive_connector", return_value=drive), \
         patch("services.post_media.get_supabase_admin_client", return_value=admin):
        yield drive, admin, storage


def test_materialize_uploads_original_and_saves_media_url(drive_and_storage):
    drive, admin, storage = drive_and_storage
    post = {"id": 53577, "drive_file_id": "f1", "user_id": "user-1"}

    url = post_media.materialize_drive_media(post)

    assert url == "https://storage.test/posts/drive/53577_f1.jpg"
    path, data, options = storage.upload.call_args.args
    assert path == "drive/53577_f1.jpg"
    assert data == drive.download_file_bytes.return_value  # el original, sin recomprimir
    assert options == {"content-type": "image/jpeg", "upsert": "true"}
    admin.table.return_value.update.assert_called_once_with({"media_url": url})


def test_materialize_keeps_video_as_is(drive_and_storage):
    drive, _, storage = drive_and_storage
    drive.service.files.return_value.get.return_value.execute.return_value = {"name": "clip.MOV", "mimeType": "video/quicktime"}
    drive.download_file_bytes.return_value = b"video-bytes"

    post_media.materialize_drive_media({"id": 1, "drive_file_id": "v1", "user_id": "user-1"})

    path, data, options = storage.upload.call_args.args
    assert (path, data, options["content-type"]) == ("drive/1_v1.mov", b"video-bytes", "video/quicktime")


def test_materialize_fails_when_drive_download_fails(drive_and_storage):
    drive, _, storage = drive_and_storage
    drive.download_file_bytes.return_value = None

    with pytest.raises(ValueError):
        post_media.materialize_drive_media({"id": 1, "drive_file_id": "f1", "user_id": "user-1"})
    storage.upload.assert_not_called()


# --- PostScheduler.schedule_post ---

def _scheduler_with_post(post: dict) -> PostScheduler:
    scheduler = object.__new__(PostScheduler)
    scheduler.supabase = MagicMock()
    scheduler.supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=post)
    scheduler.scheduler = MagicMock()
    scheduler.scheduler.add_job.return_value = MagicMock(id=f"post_{post['id']}")
    return scheduler


def test_schedule_post_with_only_drive_file_materializes_original():
    from datetime import datetime, timezone
    scheduler = _scheduler_with_post({"id": 53577, "media_url": None, "drive_file_id": "f1", "user_id": "user-1"})

    with patch("services.post_media.materialize_drive_media") as materialize:
        scheduler.schedule_post(53577, datetime(2026, 10, 30, 9, tzinfo=timezone.utc))

    materialize.assert_called_once()
    scheduler.scheduler.add_job.assert_called_once()


def test_schedule_post_with_media_url_does_not_touch_drive():
    from datetime import datetime, timezone
    scheduler = _scheduler_with_post({"id": 1, "media_url": "https://x/y.jpg", "drive_file_id": "f1", "user_id": "u"})

    with patch("services.post_media.materialize_drive_media") as materialize:
        scheduler.schedule_post(1, datetime(2026, 10, 30, 9, tzinfo=timezone.utc))

    materialize.assert_not_called()


def test_schedule_post_without_any_media_fails():
    from datetime import datetime, timezone
    scheduler = _scheduler_with_post({"id": 1, "media_url": None, "drive_file_id": None, "user_id": "u"})

    with pytest.raises(ValueError):
        scheduler.schedule_post(1, datetime(2026, 10, 30, 9, tzinfo=timezone.utc))
    scheduler.scheduler.add_job.assert_not_called()


# --- Proporción del feed y máxima resolución ---

@pytest.mark.parametrize("size, expected", [
    ((3024, 4032), ("4:5", 3024, 3780)),     # vertical de móvil 3:4
    ((4000, 1000), ("1.91:1", 1910, 1000)),  # panorámica 4:1
    ((8192, 4608), None),                    # 16:9 cabe
    ((1080, 1350), None),                    # 4:5 exacto
    ((1910, 1000), None),                    # 1.91:1 exacto
])
def test_feed_crop_target(size, expected):
    assert post_media.feed_crop_target(*size) == expected


def test_feed_crop_target_result_fits_feed():
    _, w, h = post_media.feed_crop_target(3001, 4007)
    assert post_media.FEED_MIN_RATIO <= w / h <= post_media.FEED_MAX_RATIO
    assert w == 3001  # se recorta el alto, no se pierde ancho


def test_image_size_applies_exif_rotation():
    img = Image.new("RGB", (400, 300))
    exif = img.getexif(); exif[0x0112] = 6  # girada 90°
    out = io.BytesIO(); img.save(out, format="JPEG", exif=exif)

    assert post_media.image_size(out.getvalue()) == (300, 400)


def test_oversized_jpeg_keeps_resolution_when_quality_is_enough(monkeypatch):
    original = _image_bytes("JPEG", size=(400, 400), noise=True)
    at_q50 = io.BytesIO(); Image.open(io.BytesIO(original)).save(at_q50, format="JPEG", quality=50)
    monkeypatch.setattr(post_media, "INSTAGRAM_IMAGE_MAX_BYTES", at_q50.tell())
    assert len(original) > at_q50.tell()

    result = post_media.prepare_image_for_instagram(original, "image/jpeg")

    assert Image.open(io.BytesIO(result)).size == (400, 400)


def test_materialize_refuses_feed_image_out_of_ratio(drive_and_storage):
    drive, _, storage = drive_and_storage
    drive.download_file_bytes.return_value = _image_bytes("JPEG", size=(300, 400))

    with pytest.raises(ValueError, match="4:5"):
        post_media.materialize_drive_media({"id": 1, "drive_file_id": "f1", "user_id": "u", "post_type": "post"})
    storage.upload.assert_not_called()


def test_materialize_allows_vertical_image_for_story(drive_and_storage):
    drive, _, storage = drive_and_storage
    drive.download_file_bytes.return_value = _image_bytes("JPEG", size=(300, 400))

    post_media.materialize_drive_media({"id": 1, "drive_file_id": "f1", "user_id": "u", "post_type": "story"})

    storage.upload.assert_called_once()
