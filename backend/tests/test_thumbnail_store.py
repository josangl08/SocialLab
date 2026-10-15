import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services import thumbnail_store
from services.thumbnail_store import (
    cleanup_orphan_thumbnails,
    current_key,
    generate_once,
    remove_stale_versions,
    save_thumbnails,
)

USER = "u1"
PUBLIC = "https://p.supabase.co/storage/v1/object/public/thumbnails"
SIZES = {640: b"a", 480: b"b", 320: b"c", 160: b"d"}
OLD = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()


class FakeBucket:
    """Bucket de Storage en memoria: path → {data, options, created_at}."""

    def __init__(self):
        self.objects: dict[str, dict] = {}
        self.removed: list[str] = []

    def upload(self, path, data, options):
        self.objects[path] = {"data": data, "options": options, "created_at": datetime.now(timezone.utc).isoformat()}

    def put_old(self, path):
        self.objects[path] = {"data": b"x", "options": {}, "created_at": OLD}

    def get_public_url(self, path):
        return f"{PUBLIC}/{path}"

    def list(self, path, options):
        prefix = f"{path}/" if path else ""
        children: dict[str, dict] = {}
        for full, obj in self.objects.items():
            if not full.startswith(prefix):
                continue
            name, _, rest = full[len(prefix):].partition("/")
            children[name] = {"name": name, "id": None} if rest else {"name": name, "id": full, "created_at": obj["created_at"]}
        items = sorted(children.values(), key=lambda item: item["name"])
        return items[options["offset"]:options["offset"] + options["limit"]]

    def remove(self, paths):
        self.removed.extend(paths)
        for path in paths:
            self.objects.pop(path, None)


class FakeQuery:
    def __init__(self, rows: dict, update=None):
        self.rows, self.update_data, self.filters = rows, update, []

    def select(self, *_):
        return self

    def update(self, data):
        return FakeQuery(self.rows, data)

    def eq(self, column, value):
        self.filters.append(lambda row: row.get(column) == value)
        return self

    def is_(self, column, _):
        self.filters.append(lambda row: row.get(column) is None)
        return self

    def in_(self, column, values):
        self.filters.append(lambda row: row.get(column) in values)
        return self

    def limit(self, _):
        return self

    def execute(self):
        matched = [row for row in self.rows.values() if all(f(row) for f in self.filters)]
        if self.update_data is not None:
            for row in matched:
                row.update(self.update_data)
        return SimpleNamespace(data=[dict(row) for row in matched])


class FakeAdmin:
    def __init__(self):
        self.bucket = FakeBucket()
        self.posts: dict[int, dict] = {}
        self.storage = SimpleNamespace(from_=lambda _: self.bucket)

    def table(self, _):
        return FakeQuery(self.posts)


@pytest.fixture
def admin():
    fake = FakeAdmin()
    with patch("services.thumbnail_store.get_supabase_admin_client", return_value=fake):
        yield fake


def _post(admin: FakeAdmin, post_id: int, **fields) -> dict:
    row = {"id": post_id, "user_id": USER, "media_url": None, "drive_file_id": "f1", "thumbnail_url_base": None, **fields}
    admin.posts[post_id] = row
    return row


def _keys(admin: FakeAdmin, post_id: int) -> set[str]:
    folder = f"{USER}/{post_id}/"
    return {path[len(folder):].split("_")[0] for path in admin.bucket.objects if path.startswith(folder)}


def test_save_uploads_four_sizes_with_long_cache_and_stores_base(admin):
    _post(admin, 42)

    base = asyncio.run(save_thumbnails(USER, 42, SIZES, {"media_url": None, "drive_file_id": "f1"}))

    key = current_key(base, USER, 42)
    assert base == f"{PUBLIC}/{USER}/42/{key}" and len(key) == 32
    assert admin.posts[42]["thumbnail_url_base"] == base
    for size, data in SIZES.items():
        obj = admin.bucket.objects[f"{USER}/42/{key}_{size}.webp"]
        assert obj["data"] == data
        assert obj["options"] == {"content-type": "image/webp", "cache-control": "31536000"}


def test_save_does_not_store_base_if_image_changed_meanwhile(admin):
    _post(admin, 42, drive_file_id="f2")  # la imagen cambió mientras se generaba

    base = asyncio.run(save_thumbnails(USER, 42, SIZES, {"media_url": None, "drive_file_id": "f1"}))

    assert base is None
    assert admin.posts[42]["thumbnail_url_base"] is None


def test_save_removes_previous_versions_only(admin):
    _post(admin, 42)
    admin.bucket.put_old(f"{USER}/42/oldkey_160.webp")
    admin.bucket.put_old(f"{USER}/7/otherpost_160.webp")

    base = asyncio.run(save_thumbnails(USER, 42, SIZES, {"media_url": None, "drive_file_id": "f1"}))

    assert _keys(admin, 42) == {current_key(base, USER, 42)}
    assert f"{USER}/7/otherpost_160.webp" in admin.bucket.objects


def test_recent_objects_of_other_generations_are_kept(admin):
    _post(admin, 42, thumbnail_url_base=f"{PUBLIC}/{USER}/42/current")
    admin.bucket.upload(f"{USER}/42/inprogress_160.webp", b"x", {})  # otra instancia aún subiendo

    assert remove_stale_versions(USER, 42) == 0
    assert f"{USER}/42/inprogress_160.webp" in admin.bucket.objects


def test_current_key_ignores_base_of_another_post():
    assert current_key(f"{PUBLIC}/{USER}/42/abc", USER, 42) == "abc"
    assert current_key(f"{PUBLIC}/{USER}/43/abc", USER, 42) is None
    assert current_key(None, USER, 42) is None


def test_cleanup_removes_orphans_and_is_idempotent(admin):
    _post(admin, 1, thumbnail_url_base=f"{PUBLIC}/{USER}/1/keep")  # vigente
    _post(admin, 2)  # imagen cambiada: base anulada por el trigger
    for path in (f"{USER}/1/keep_160.webp", f"{USER}/1/old_160.webp", f"{USER}/2/old_160.webp",
                 f"{USER}/3/gone_160.webp", "u2/1/foreign_160.webp"):  # 3: post borrado; u2: no es su dueño
        admin.bucket.put_old(path)

    assert cleanup_orphan_thumbnails() == 4
    assert set(admin.bucket.objects) == {f"{USER}/1/keep_160.webp"}
    assert cleanup_orphan_thumbnails() == 0
    assert set(admin.bucket.objects) == {f"{USER}/1/keep_160.webp"}


def test_cleanup_paginates_listings(admin, monkeypatch):
    monkeypatch.setattr(thumbnail_store, "_LIST_PAGE", 2)
    for post_id in range(1, 6):
        admin.bucket.put_old(f"{USER}/{post_id}/gone_160.webp")

    assert cleanup_orphan_thumbnails() == 5


def test_cleanup_failure_does_not_raise(admin):
    admin.bucket.list = lambda *_: (_ for _ in ()).throw(RuntimeError("Storage caído"))
    assert cleanup_orphan_thumbnails() == 0


def test_lock_avoids_generating_twice_for_concurrent_requests(admin):
    _post(admin, 42)
    calls = 0

    async def render():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        admin.posts[42]["thumbnail_url_base"] = f"{PUBLIC}/{USER}/42/k"  # lo que hace save_thumbnails
        return SIZES

    async def two_requests():
        return await asyncio.gather(generate_once(42, render), generate_once(42, render))

    first, second = asyncio.run(two_requests())

    assert calls == 1
    assert first == (None, SIZES)
    assert second == (f"{PUBLIC}/{USER}/42/k", None)


def test_waiting_request_generates_if_first_could_not_save(admin):
    _post(admin, 42)
    calls = 0

    async def render():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return SIZES  # fallo al subir: no queda base guardada

    async def two_requests():
        return await asyncio.gather(generate_once(42, render), generate_once(42, render))

    asyncio.run(two_requests())

    assert calls == 2
