import os
from unittest.mock import MagicMock

# Mock supabase create_client to prevent validation exceptions at module load time
import supabase
supabase.create_client = MagicMock()

# Set before any backend module is imported — supabase_client.py raises at module
# level if these are absent.
os.environ.setdefault("SUPABASE_URL", "https://mock.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "mock-anon-key-placeholder-xxxxxxxxxxxxxxxxx")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "mock-service-role-placeholder-xxxxxxxx")

import io
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image


# ---------------------------------------------------------------------------
# Mock Supabase infrastructure
# ---------------------------------------------------------------------------

class MockResponse:
    def __init__(self, data=None, error=None):
        self.data = data if data is not None else []
        self.error = error


class MockQueryBuilder:
    """Imitates supabase-py's fluent query builder chain."""

    def __init__(self, rows=None, return_rows=None):
        self._rows = rows or []
        self._return_rows = return_rows  # overrides rows on execute() when set

    def select(self, *a, **kw): return self
    def update(self, data, **kw):
        updated = [{**r, **data} for r in self._rows] if self._rows else [data]
        return MockQueryBuilder(return_rows=updated)
    def insert(self, data, **kw):
        return MockQueryBuilder(return_rows=[{"id": "mock-post-id", **data}])
    def eq(self, *a, **kw): return self
    def or_(self, *a, **kw): return self
    def order(self, *a, **kw): return self
    def limit(self, n): return MockQueryBuilder(rows=self._rows[:n])
    def execute(self):
        rows = self._return_rows if self._return_rows is not None else self._rows
        return MockResponse(rows)


class MockStorageClient:
    def from_(self, bucket): return self

    def upload(self, path, data, opts=None):
        return MockResponse([{"Key": path}])

    def get_public_url(self, path):
        return f"https://mock.storage.test/{path}"


class MockSupabaseClient:
    def __init__(self, table_data: dict):
        self._table_data = table_data
        self.storage = MockStorageClient()

    def table(self, name: str) -> MockQueryBuilder:
        return MockQueryBuilder(rows=list(self._table_data.get(name, [])))


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

USER_ID = "test-user-uuid-1234"

MOCK_TEMPLATES = [
    {
        "id": "tmpl-1",
        "name": "player_stats_modern_blue.png",
        "user_id": USER_ID,
        "is_active": True,
        "priority": 10,
        "image_url": "https://mock.storage.test/tmpl-1.png",
        "selection_rules": {
            "export_types": ["player"],
            "positions": ["Forward", "Midfielder", "Defender", "Goalkeeper"],
        },
        "template_config": {"graphic_position": "center", "graphic_scale": 0.75, "margin": 80},
        "description": "Template moderno azul para jugadores",
    },
    {
        "id": "tmpl-2",
        "name": "player_stats_dark_elegant.png",
        "user_id": USER_ID,
        "is_active": True,
        "priority": 8,
        "image_url": "https://mock.storage.test/tmpl-2.png",
        "selection_rules": {
            "export_types": ["player"],
            "min_goals": 5,
        },
        "template_config": {"graphic_position": "center", "graphic_scale": 0.7, "margin": 80},
        "description": "Template elegante para jugadores estrella",
    },
    {
        "id": "tmpl-3",
        "name": "team_performance_gradient.png",
        "user_id": USER_ID,
        "is_active": True,
        "priority": 10,
        "image_url": "https://mock.storage.test/tmpl-3.png",
        "selection_rules": {"export_types": ["team"]},
        "template_config": {"graphic_position": "center", "graphic_scale": 0.7, "margin": 100},
        "description": "Template para estadísticas de equipos",
    },
    {
        "id": "tmpl-4",
        "name": "match_result_victory_green.png",
        "user_id": USER_ID,
        "is_active": True,
        "priority": 10,
        "image_url": "https://mock.storage.test/tmpl-4.png",
        "selection_rules": {
            "export_types": ["match"],
            "match_status": ["finished"],
            "winners": ["home"],
        },
        "template_config": {"graphic_position": "center", "graphic_scale": 0.8, "margin": 60},
        "description": "Template verde para victorias en casa",
    },
    {
        "id": "tmpl-5",
        "name": "story_player_highlight.png",
        "user_id": USER_ID,
        "is_active": True,
        "priority": 9,
        "image_url": "https://mock.storage.test/tmpl-5.png",
        "selection_rules": {
            "export_types": ["player"],
            "contexts": ["highlight", "best_moment"],
        },
        "template_config": {"graphic_position": "center", "graphic_scale": 0.6, "margin": 100},
        "description": "Template Story 9:16 para jugadores",
    },
]

MOCK_POSTS = [{"user_id": USER_ID}]


def _make_png_bytes() -> bytes:
    img = Image.new("RGBA", (200, 200), (100, 150, 200, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# Generated once at import time — reused across all tests.
PNG_BYTES = _make_png_bytes()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def mock_supabase_client() -> MockSupabaseClient:
    return MockSupabaseClient({"templates": MOCK_TEMPLATES, "posts": MOCK_POSTS})


@pytest.fixture(autouse=True, scope="session")
def mock_http():
    """Patches requests.get globally so no test ever hits the network."""
    mock_resp = MagicMock()
    mock_resp.content = PNG_BYTES
    with patch("requests.get", return_value=mock_resp):
        yield PNG_BYTES


@pytest.fixture(scope="session")
def mock_caption_generator() -> MagicMock:
    gen = MagicMock()
    gen.generate_caption.return_value = "Caption de prueba #futbol #test"
    gen.generate_caption_fallback.return_value = "Caption fallback #test"
    return gen


@pytest.fixture(autouse=True)
def override_supabase_client(mock_supabase_client):
    from auth.dependencies import get_user_supabase_client
    from main import app
    from fastapi import Request

    def _mock_get_user_supabase_client(request: Request = None):
        if request:
            path = request.url.path
            if path.startswith("/api/posts"):
                try:
                    from routes import posts_routes
                    if hasattr(posts_routes, "supabase"):
                        return posts_routes.supabase
                except ImportError:
                    pass
            elif path.startswith("/api/agent"):
                try:
                    from routes import agent_routes
                    if hasattr(agent_routes, "supabase"):
                        return agent_routes.supabase
                except ImportError:
                    pass
        return mock_supabase_client

    app.dependency_overrides[get_user_supabase_client] = _mock_get_user_supabase_client
    yield
    if get_user_supabase_client in app.dependency_overrides:
        del app.dependency_overrides[get_user_supabase_client]

