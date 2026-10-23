"""
Tests for PostScheduler guards and defense-in-depth publishing checks.

Verifies:
1. Rescheduling a draft post updates scheduled_at, keeps status as draft, and creates no job.
2. Rescheduling a scheduled post recreates the APScheduler job.
3. publish_post_job cancels the job and aborts publication if the post is not in 'scheduled' status.
4. publish_post_job proceeds normally if the post is in 'scheduled' status.
5. PUT /api/scheduler/reschedule/{post_id} handles reschedule_post returning None gracefully.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest

from services.scheduler.post_scheduler import PostScheduler, publish_post_job


def _make_mock_supabase_client(post_data: dict, account_data: dict = None):
    """
    Creates a mock Supabase client routed by table name.
    """
    client = MagicMock()

    posts_mock = MagicMock()
    posts_mock.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=post_data)
    posts_mock.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[post_data] if post_data else [])
    posts_mock.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[post_data] if post_data else [])

    jobs_mock = MagicMock()
    jobs_mock.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=None)
    jobs_mock.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    jobs_mock.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    jobs_mock.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    jobs_mock.insert.return_value.execute.return_value = MagicMock(data=[])
    jobs_mock.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    accounts_mock = MagicMock()
    if account_data:
        accounts_mock.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=account_data)
    else:
        accounts_mock.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=None)

    proposals_mock = MagicMock()
    proposals_mock.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    def table_router(table_name: str):
        if table_name == "posts":
            return posts_mock
        if table_name == "scheduled_jobs":
            return jobs_mock
        if table_name == "instagram_accounts":
            return accounts_mock
        if table_name == "content_proposals":
            return proposals_mock
        return MagicMock()

    client.table.side_effect = table_router
    return client, posts_mock, jobs_mock, accounts_mock


def _create_scheduler_instance(mock_client: MagicMock) -> PostScheduler:
    """Instantiate PostScheduler bypassing __init__ (avoids DB connection requirement)."""
    scheduler = object.__new__(PostScheduler)
    scheduler.supabase = mock_client
    scheduler.scheduler = MagicMock()
    scheduler.publisher = MagicMock()
    return scheduler


def test_reschedule_draft_post_updates_time_without_creating_job():
    """
    Reprogramar un draft: si el post no está en 'scheduled', solo se actualiza
    'scheduled_at' y se devuelve None, sin cancelar ni crear job en APScheduler ni en DB.
    """
    draft_post = {
        "id": 501,
        "status": "draft",
        "media_url": "https://example.com/draft.jpg",
        "user_id": "user-uuid-1",
        "scheduled_at": None,
    }
    db, posts_mock, jobs_mock, _ = _make_mock_supabase_client(draft_post)
    scheduler = _create_scheduler_instance(db)

    new_time = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
    job_id = scheduler.reschedule_post(501, new_time)

    # 1. Debe devolver None
    assert job_id is None

    # 2. No debe interactuar con el scheduler de APScheduler
    scheduler.scheduler.add_job.assert_not_called()
    scheduler.scheduler.remove_job.assert_not_called()

    # 3. No debe insertar ninguna fila en scheduled_jobs
    jobs_mock.insert.assert_not_called()

    # 4. Debe haber actualizado el scheduled_at del post pero sin cambiar status a scheduled
    posts_mock.update.assert_called_once()
    updated_fields = posts_mock.update.call_args[0][0]
    assert "scheduled_at" in updated_fields
    assert updated_fields.get("status") != "scheduled"


def test_reschedule_scheduled_post_recreates_job():
    """
    Reprogramar un post en 'scheduled': cancela el job anterior y crea uno nuevo a la nueva hora.
    """
    scheduled_post = {
        "id": 502,
        "status": "scheduled",
        "media_url": "https://example.com/approved.jpg",
        "user_id": "user-uuid-1",
        "scheduled_at": "2026-10-18T10:00:00+00:00",
    }
    db, posts_mock, jobs_mock, _ = _make_mock_supabase_client(scheduled_post)
    scheduler = _create_scheduler_instance(db)
    scheduler.scheduler.add_job.return_value = MagicMock(id="post_502")

    new_time = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
    job_id = scheduler.reschedule_post(502, new_time)

    # 1. Debe devolver el nuevo job_id
    assert job_id == "post_502"

    # 2. Debe crear el nuevo job en APScheduler
    scheduler.scheduler.add_job.assert_called_once()

    # 3. Debe insertar la nueva entrada en scheduled_jobs
    jobs_mock.insert.assert_called_once()
    inserted_data = jobs_mock.insert.call_args[0][0]
    assert inserted_data["post_id"] == 502
    assert inserted_data["status"] == "pending"


def test_publish_post_job_cancels_if_post_not_scheduled():
    """
    publish_post_job con un draft: sirve como defensa en profundidad.
    Si el post no está en 'scheduled', marca el job como 'cancelled' y sale sin publicar.
    """
    draft_post = {
        "id": 601,
        "status": "draft",
        "media_url": "https://example.com/draft.jpg",
        "user_id": "user-uuid-1",
        "content": "Contenido en borrador",
    }
    db, posts_mock, jobs_mock, _ = _make_mock_supabase_client(draft_post)
    publisher = MagicMock()

    with patch("services.scheduler.post_scheduler.get_supabase_admin_client", return_value=db), \
         patch("services.scheduler.post_scheduler.InstagramPublisher", return_value=publisher):
        publish_post_job(601)

    # 1. El publicador de Instagram NUNCA debe llamarse
    publisher.publish_post.assert_not_called()

    # 2. El job en scheduled_jobs debe marcarse como cancelled
    cancelled_updates = [
        call[0][0] for call in jobs_mock.update.call_args_list
        if call[0][0].get("status") == "cancelled"
    ]
    assert len(cancelled_updates) >= 1, "El job programado debe marcarse con status='cancelled'"

    # 3. El post NO debe marcarse como publicado
    published_updates = [
        call[0][0] for call in posts_mock.update.call_args_list
        if call[0][0].get("status") == "published"
    ]
    assert len(published_updates) == 0, "Un borrador no debe marcarse como published"


def test_publish_post_job_publishes_when_scheduled():
    """
    publish_post_job con un post en 'scheduled': publica normalmente en Instagram
    y actualiza post a 'published' y job a 'completed'.
    """
    scheduled_post = {
        "id": 602,
        "status": "scheduled",
        "media_url": "https://example.com/approved.jpg",
        "user_id": "user-uuid-1",
        "content": "Post aprobado",
        "post_type": "post",
    }
    account_data = {
        "id": 10,
        "user_id": "user-uuid-1",
        "is_active": True,
        "telegram_chat_id": None,
        "drive_folder_id": None,
    }
    db, posts_mock, jobs_mock, accounts_mock = _make_mock_supabase_client(scheduled_post, account_data)
    publisher = MagicMock()
    publisher.publish_post.return_value = {"id": "ig-12345", "permalink": "https://instagram.com/p/12345"}
    publisher.get_publishing_quota.return_value = None  # cupo no consultable: se publica igual

    with patch("services.scheduler.post_scheduler.get_supabase_admin_client", return_value=db), \
         patch("services.scheduler.post_scheduler.InstagramPublisher", return_value=publisher), \
         patch("services.post_cleanup.PostCleanupService"):
        publish_post_job(602)

    # 1. El publicador debe haberse ejecutado
    publisher.publish_post.assert_called_once()

    # 2. El job debe marcarse como completed
    completed_updates = [
        call[0][0] for call in jobs_mock.update.call_args_list
        if call[0][0].get("status") == "completed"
    ]
    assert len(completed_updates) >= 1

    # 3. El post debe marcarse como published
    published_updates = [
        call[0][0] for call in posts_mock.update.call_args_list
        if call[0][0].get("status") == "published"
    ]
    assert len(published_updates) >= 1


def test_reschedule_route_returns_null_job_when_post_not_approved():
    """
    Ruta PUT /api/scheduler/reschedule/{id}: cuando reschedule_post devuelve None
    (porque el post no está aprobado/scheduled), debe responder con job_id: null
    y el mensaje de que la hora se actualizó sin job de publicación.
    """
    from fastapi.testclient import TestClient
    from main import app
    from auth.dependencies import get_current_user, get_user_supabase_client
    from models.schemas import User

    async def mock_user():
        return User(id="user-uuid-1", email="test@example.com")

    post_row = {"id": 701, "media_url": "https://example.com/photo.jpg"}
    db = MagicMock()
    # Mock posts select by id
    db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[post_row])

    mock_scheduler = MagicMock()
    mock_scheduler.reschedule_post.return_value = None

    prev_user = app.dependency_overrides.get(get_current_user)
    prev_client = app.dependency_overrides.get(get_user_supabase_client)
    app.dependency_overrides[get_current_user] = mock_user
    app.dependency_overrides[get_user_supabase_client] = lambda: db

    try:
        with patch("routes.scheduler_routes.get_scheduler", return_value=mock_scheduler):
            client = TestClient(app)
            future_time = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
            response = client.put(
                "/api/scheduler/reschedule/701",
                json={"new_scheduled_time": future_time}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["job_id"] is None
            assert data["message"] == "Scheduled time updated (post not approved — no publish job)"
    finally:
        for dep, prev in ((get_current_user, prev_user), (get_user_supabase_client, prev_client)):
            if prev is None:
                app.dependency_overrides.pop(dep, None)
            else:
                app.dependency_overrides[dep] = prev
