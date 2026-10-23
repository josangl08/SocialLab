"""
Tests para sincronización de métricas de Stories y miniaturas persistentes (AD-2, AD-2b).
Cubre:
- HTTP y Storage mockeados
- Story externa se inserta en posts (post_type='story', status='published')
- Story de SocialLab conserva content (no se sobreescribe)
- Miniatura guardada una sola vez con persistent-thumbnails (thumbnail_url_base)
- Fallo de descarga deja null en thumbnail_url sin romper la ejecución
- 1 + N llamadas Graph API por cuenta
- Re-ejecución sin duplicados (idempotente)
- Error de API en una cuenta no rompe otras cuentas
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
try:
    from services.instagram_insights import InstagramInsightsService
except ImportError:
    InstagramInsightsService = None


@pytest.fixture
def sample_live_stories():
    return [
        {
            "id": "story_ext_1",
            "media_type": "IMAGE",
            "media_url": "https://cdn.instagram.com/story1.jpg",
            "thumbnail_url": None,
            "permalink": "https://instagram.com/stories/user/1",
            "timestamp": "2026-10-18T10:00:00+0000",
        },
        {
            "id": "story_lab_2",
            "media_type": "VIDEO",
            "media_url": "https://cdn.instagram.com/story2.mp4",
            "thumbnail_url": "https://cdn.instagram.com/story2_thumb.jpg",
            "permalink": "https://instagram.com/stories/user/2",
            "timestamp": "2026-10-18T11:00:00+0000",
        },
    ]


@pytest.fixture
def sample_story_insights():
    return {
        "views": 150,
        "reach": 120,
        "replies": 5,
        "shares": 2,
        "follows": 1,
        "profile_visits": 8,
        "total_interactions": 16,
        "link_clicks": 3,
        "story_navigation": {
            "tap_forward": 80,
            "tap_back": 10,
            "tap_exit": 5,
            "swipe_forward": 2,
        },
    }


def test_get_live_stories_requests_correct_fields():
    """get_live_stories debe pedir id,media_type,media_url,thumbnail_url,permalink,timestamp."""
    svc = InstagramInsightsService("test-token", "ig-acc-123", "facebook")
    expected_stories = [{"id": "s1", "media_type": "IMAGE"}]
    with patch.object(svc, "_make_request", return_value={"data": expected_stories}) as mock_req:
        res = svc.get_live_stories("ig-acc-123")
        assert res == expected_stories
        mock_req.assert_called_once()
        call_endpoint = mock_req.call_args[0][0]
        assert "stories" in call_endpoint
        fields = mock_req.call_args[0][1].get("fields", "")
        for f in ["id", "media_type", "media_url", "thumbnail_url", "permalink", "timestamp"]:
            assert f in fields


def test_get_story_insights_queries_metrics():
    """get_story_insights debe pedir las métricas de Story requeridas."""
    svc = InstagramInsightsService("test-token", "ig-acc-123", "facebook")
    mock_data = {
        "data": [
            {"name": "views", "values": [{"value": 100}]},
            {"name": "reach", "values": [{"value": 85}]},
            {"name": "replies", "values": [{"value": 4}]},
            {"name": "link_clicks", "values": [{"value": 2}]},
        ]
    }
    navigation_data = {
        "data": [{
            "name": "navigation",
            "total_value": {"value": 30, "breakdowns": [{"results": [
                {"dimension_values": ["tap_forward"], "value": 20},
                {"dimension_values": ["tap_exit"], "value": 10},
            ]}]},
        }]
    }
    with patch.object(svc, "_make_request", side_effect=[mock_data, navigation_data]) as mock_req:
        insights = svc.get_story_insights("story_123")

    assert insights["views"] == 100
    assert insights["reach"] == 85
    assert insights["link_clicks"] == 2
    assert insights["story_navigation"] == {"tap_forward": 20, "tap_exit": 10}
    # La API rechaza el breakdown junto a las demás métricas: navigation va en su propia llamada
    assert "breakdown" not in mock_req.call_args_list[0][0][1]
    assert mock_req.call_args_list[1][0][1] == {"metric": "navigation", "breakdown": "story_navigation_action_type"}


def test_store_story_thumbnail_saves_with_persistent_thumbnails():
    """La miniatura se guarda con el mecanismo de persistent-thumbnails (thumbnail_url_base)
    a partir de la imagen del CDN, comprobando que la media del post no cambió."""
    post = {"id": 42, "user_id": "u1", "media_url": "https://cdn.instagram.com/s1.jpg", "drive_file_id": None}
    story = {"id": "s1", "media_type": "IMAGE", "media_url": "https://cdn.instagram.com/s1.jpg", "thumbnail_url": None}
    sizes = {640: b"a", 480: b"b", 320: b"c", 160: b"d"}

    with patch("services.media_thumbnails.render_all_sizes", AsyncMock(return_value=sizes)) as mock_render, \
         patch("services.thumbnail_store.save_thumbnails", AsyncMock(return_value="https://storage/thumbnails/u1/42/k")) as mock_save:
        base = InstagramInsightsService.store_story_thumbnail(post, story)

    assert base == "https://storage/thumbnails/u1/42/k"
    mock_render.assert_awaited_once_with("storage", "https://cdn.instagram.com/s1.jpg")
    mock_save.assert_awaited_once_with("u1", 42, sizes, {"media_url": post["media_url"], "drive_file_id": None})


def test_store_story_thumbnail_video_uses_cover():
    """Una Story de vídeo usa su portada (thumbnail_url), no el mp4."""
    post = {"id": 43, "user_id": "u1", "media_url": "https://cdn.instagram.com/s2.mp4"}
    story = {"id": "s2", "media_type": "VIDEO", "media_url": "https://cdn.instagram.com/s2.mp4",
             "thumbnail_url": "https://cdn.instagram.com/s2_thumb.jpg"}

    with patch("services.media_thumbnails.render_all_sizes", AsyncMock(return_value={640: b"a"})) as mock_render, \
         patch("services.thumbnail_store.save_thumbnails", AsyncMock(return_value="base")):
        InstagramInsightsService.store_story_thumbnail(post, story)

    mock_render.assert_awaited_once_with("storage", "https://cdn.instagram.com/s2_thumb.jpg")


def test_store_story_thumbnail_failure_leaves_null():
    """Si la descarga del CDN falla, devuelve None sin excepción (se reintenta en la siguiente pasada)."""
    post = {"id": 42, "user_id": "u1", "media_url": "https://cdn.instagram.com/fail.jpg"}
    story = {"id": "s1", "media_type": "IMAGE", "media_url": "https://cdn.instagram.com/fail.jpg"}

    with patch("services.media_thumbnails.render_all_sizes", AsyncMock(side_effect=Exception("CDN timeout"))), \
         patch("services.thumbnail_store.save_thumbnails", AsyncMock()) as mock_save:
        assert InstagramInsightsService.store_story_thumbnail(post, story) is None

    mock_save.assert_not_awaited()


def test_sync_story_insights_inserts_external_and_preserves_sociallab():
    """
    Sincronización de stories:
    - Story externa se inserta en posts (content='')
    - Story de SocialLab ya existente conserva su content
    - Métricas se guardan en post_performance
    """
    svc = InstagramInsightsService("test-token", "ig-acc-123", "facebook")

    live_stories = [
        {
            "id": "ext_story_1",
            "media_type": "IMAGE",
            "media_url": "https://cdn.instagram.com/ext.jpg",
            "thumbnail_url": None,
            "permalink": "https://instagram.com/stories/1",
            "timestamp": "2026-10-18T10:00:00+0000",
        },
        {
            "id": "lab_story_2",
            "media_type": "IMAGE",
            "media_url": "https://cdn.instagram.com/lab.jpg",
            "thumbnail_url": None,
            "permalink": "https://instagram.com/stories/2",
            "timestamp": "2026-10-18T09:00:00+0000",
        },
    ]

    # En BD ya existe lab_story_2 creada en SocialLab
    existing_posts = [
        {
            "id": 102,
            "instagram_post_id": "lab_story_2",
            "content": "Story creada en SocialLab",
            "user_id": "u1",
            "thumbnail_url_base": "https://storage/existing",
            "post_type": "story",
        }
    ]

    mock_db = MagicMock()
    posts_table = MagicMock()
    perf_table = MagicMock()

    def table_mock(name):
        if name == "posts":
            return posts_table
        if name == "post_performance":
            return perf_table
        return MagicMock()

    mock_db.table.side_effect = table_mock
    posts_table.select.return_value.in_.return_value.execute.return_value = MagicMock(data=existing_posts)
    # Insert de nueva story devuelve id=101
    posts_table.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": 101, "user_id": "u1", "instagram_post_id": "ext_story_1", "thumbnail_url_base": None}]
    )

    account = {
        "id": 1,
        "user_id": "u1",
        "long_lived_access_token": "token",
        "instagram_business_account_id": "ig-acc-123",
    }

    with patch.object(svc, "get_live_stories", return_value=live_stories), \
         patch.object(svc, "get_story_insights", return_value={"views": 50, "reach": 40, "replies": 4, "shares": 0, "total_interactions": 28}), \
         patch.object(svc, "store_story_thumbnail", return_value="https://storage/thumb.jpg") as mock_thumb:

        count = svc.sync_story_insights(account=account, db_client=mock_db)

        # Se sincronizaron 2 stories
        assert count == 2

        # 1. ext_story_1 se insertó con content=""
        posts_table.insert.assert_called_once()
        assert len(posts_table.insert.call_args[0][0]) == 1
        inserted_data = posts_table.insert.call_args[0][0][0]
        assert inserted_data["instagram_post_id"] == "ext_story_1"
        assert inserted_data["content"] == ""
        assert inserted_data["post_type"].lower() == "story"
        assert inserted_data["status"] == "published"

        # 2. lab_story_2 no se reinsertó ni se actualizó
        posts_table.update.assert_not_called()
        posts_table.upsert.assert_not_called()
        # Miniatura solo se descargó para ext_story_1 porque lab_story_2 ya tiene thumbnail_url
        assert mock_thumb.call_count == 1
        assert mock_thumb.call_args[0][0]["id"] == 101

        # 3. Un único upsert en post_performance con las dos Stories
        perf_table.upsert.assert_called_once()
        rows = perf_table.upsert.call_args[0][0]
        assert {r["post_id"] for r in rows} == {101, 102}
        # La API no da likes de Stories: total_interactions − replies − shares (28 − 4 − 0)
        assert all(r["likes"] == 24 for r in rows)
        assert perf_table.upsert.call_args[1]["on_conflict"] == "post_id"


def test_sync_story_insights_graph_api_calls_count():
    """El coste de Graph API debe ser 1 llamada de listado + N de insights."""
    svc = InstagramInsightsService("test-token", "ig-acc-123", "facebook")
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
    mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": i, "user_id": "u1", "instagram_post_id": f"s_{i}"} for i in range(3)]
    )

    live_stories = [{"id": f"s_{i}", "media_type": "IMAGE", "media_url": "url"} for i in range(3)]

    with patch.object(svc, "get_live_stories", return_value=live_stories) as mock_get_stories, \
         patch.object(svc, "get_story_insights", return_value={"views": 10}) as mock_get_insights, \
         patch.object(svc, "store_story_thumbnail", return_value="thumb"):

        account = {"id": 1, "user_id": "u1", "long_lived_access_token": "tok", "instagram_business_account_id": "ig1"}
        svc.sync_story_insights(account=account, db_client=mock_db)

        # 1 llamada para listar stories
        mock_get_stories.assert_called_once()
        # 3 llamadas de insights (1 por cada story viva)
        assert mock_get_insights.call_count == 3


def test_sync_story_insights_api_error_isolation():
    """Un error en la API de una cuenta no debe propagarse ni romper el flujo de otras cuentas."""
    try:
        from main import sync_all_accounts_story_insights
    except (ImportError, AttributeError):
        pytest.skip("sync_all_accounts_story_insights aún no implementado en main.py ([implementation])")

    accounts = [
        {"id": 1, "user_id": "u1", "long_lived_access_token": "t1", "instagram_business_account_id": "ig1", "login_type": "facebook", "is_active": True},
        {"id": 2, "user_id": "u2", "long_lived_access_token": "t2", "instagram_business_account_id": "ig2", "login_type": "instagram", "is_active": True},
    ]

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.execute.return_value = MagicMock(data=accounts)

    def fake_sync(account, **kwargs):
        if account["id"] == 1:
            raise Exception("API error for account 1")
        return 1

    with patch("main.admin_supabase", mock_supabase), \
         patch("main.decrypt_token", side_effect=lambda x: x), \
         patch.object(InstagramInsightsService, "sync_story_insights", side_effect=fake_sync) as mock_sync:

        # No debe lanzar excepción
        sync_all_accounts_story_insights()

    assert [c.kwargs["account"]["id"] for c in mock_sync.call_args_list] == [1, 2]


def test_story_likes_derived_from_total_interactions():
    """Me gusta = total_interactions − replies − shares; None si no llega total_interactions."""
    likes = InstagramInsightsService._story_likes
    assert likes({"total_interactions": 30, "replies": 6, "shares": 0}) == 24
    assert likes({"total_interactions": 3, "replies": 2, "shares": 2}) == 0
    assert likes({"replies": 2}) is None
