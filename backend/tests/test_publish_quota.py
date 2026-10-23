"""
Tests para guardia de cuota de publicación (AD-3).
Cubre:
- Sin cuota -> aplazado +60 min, retry_count intacto, quota_deferrals +1, y 1 aviso Telegram (1º aplazamiento).
- 24º aplazamiento -> marcado failed con error_message='PUBLISH_QUOTA_EXCEEDED' y aviso Telegram de fallo.
- Error en consulta de cuota -> fail-open: se procede a publicar igualmente.
- Con cuota disponible -> flujo normal de publicación.
- Helper get_publishing_quota de InstagramPublisher.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from services.publisher.instagram_publisher import InstagramPublisher
from services.scheduler.post_scheduler import publish_post_job


def test_get_publishing_quota_queries_content_publishing_limit():
    """get_publishing_quota debe consultar content_publishing_limit con fields=config,quota_usage."""
    pub = InstagramPublisher()
    pub._get_instagram_account = MagicMock(return_value={"access_token": "tok", "instagram_user_id": "ig-1", "base_url": "https://graph.facebook.com/v26.0"})
    mock_resp = {
        "data": [
            {
                "config": {"quota_total": 100},
                "quota_usage": 42
            }
        ]
    }
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_resp

        quota = pub.get_publishing_quota(instagram_account_id=1)
        assert quota is not None
        assert quota.get("quota_usage") == 42
        assert quota.get("quota_total") == 100
        assert "ig-1/content_publishing_limit" in mock_get.call_args[0][0]
        assert mock_get.call_args[1]["params"]["fields"] == "config,quota_usage"


def test_get_publishing_quota_returns_none_on_error():
    """Si la petición a content_publishing_limit falla, devuelve None (fail-open)."""
    pub = InstagramPublisher()
    pub._get_instagram_account = MagicMock(return_value={"access_token": "tok", "instagram_user_id": "ig-1", "base_url": "https://graph.facebook.com/v26.0"})
    with patch("requests.get", side_effect=Exception("API Error")):
        quota = pub.get_publishing_quota(instagram_account_id=1)
        assert quota is None


def test_publish_post_job_quota_exceeded_defers_and_notifies_telegram_first_time():
    """Sin cuota -> aplazado +60 min sin tocar retry_count, quota_deferrals=1, telegram avisado."""
    post_id = 100
    mock_supabase = MagicMock()

    mock_post_data = {
        "id": post_id,
        "status": "scheduled",
        "user_id": "u1",
        "media_url": "https://img.url/photo.jpg",
        "content": "Test caption",
        "post_type": "image",
    }
    mock_account_data = {
        "id": 1,
        "user_id": "u1",
        "telegram_chat_id": "12345",
        "is_active": True,
        "drive_folder_id": None,
    }
    mock_job_data = {
        "retry_count": 0,
        "max_retries": 3,
        "quota_deferrals": 0,
        "status": "pending",
    }

    tables = {}

    def table_mock(name):
        # Un mock por tabla: las aserciones leen las llamadas de update de cada una
        if name in tables:
            return tables[name]
        t = tables[name] = MagicMock()
        if name == "posts":
            t.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=mock_post_data)
        elif name == "instagram_accounts":
            t.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=mock_account_data)
        elif name == "scheduled_jobs":
            t.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=mock_job_data)
        return t

    mock_supabase.table.side_effect = table_mock

    mock_publisher = MagicMock()
    mock_publisher.get_publishing_quota.return_value = {"quota_usage": 100, "quota_total": 100}

    mock_telegram = MagicMock()
    mock_telegram.send_status_notification = AsyncMock()

    with patch("services.scheduler.post_scheduler.get_supabase_admin_client", return_value=mock_supabase), \
         patch("services.scheduler.post_scheduler.InstagramPublisher", return_value=mock_publisher), \
         patch("services.telegram_service.TelegramService", return_value=mock_telegram), \
         patch("services.scheduler.post_scheduler.PostScheduler") as mock_sched_cls:

        mock_scheduler_instance = MagicMock()
        mock_sched_cls.return_value = mock_scheduler_instance

        publish_post_job(post_id)

        # 1. No se llamó a publish_post
        mock_publisher.publish_post.assert_not_called()

        # 2. Se actualizó scheduled_jobs con status='deferred_quota' y quota_deferrals=1
        updates = [c[0][0] for c in mock_supabase.table("scheduled_jobs").update.call_args_list]
        deferred_update = next((u for u in updates if u.get("status") == "deferred_quota"), None)
        assert deferred_update is not None, "scheduled_jobs must be updated to status='deferred_quota'"
        assert deferred_update.get("quota_deferrals") == 1
        assert "retry_count" not in deferred_update or deferred_update.get("retry_count") == 0

        # 3. Se reprogramó +60 min en APScheduler con replace_existing=True
        mock_scheduler_instance.scheduler.add_job.assert_called_once()
        job_kwargs = mock_scheduler_instance.scheduler.add_job.call_args[1]
        assert job_kwargs.get("replace_existing") is True

        # 4. Telegram avisó una sola vez al ser el primer aplazamiento
        assert mock_telegram.send_status_notification.call_count == 1


def test_publish_post_job_quota_exceeded_24th_deferral_fails():
    """Al 24º aplazamiento -> status='failed', error_message='PUBLISH_QUOTA_EXCEEDED'."""
    post_id = 101
    mock_supabase = MagicMock()

    mock_post_data = {
        "id": post_id,
        "status": "scheduled",
        "user_id": "u1",
        "media_url": "https://img.url/photo.jpg",
        "content": "Test caption",
        "post_type": "image",
    }
    mock_account_data = {
        "id": 1,
        "user_id": "u1",
        "telegram_chat_id": "12345",
        "is_active": True,
        "drive_folder_id": None,
    }
    mock_job_data = {
        "retry_count": 0,
        "max_retries": 3,
        "quota_deferrals": 23,  # Próximo es el 24º
        "status": "deferred_quota",
    }

    tables = {}

    def table_mock(name):
        # Un mock por tabla: las aserciones leen las llamadas de update de cada una
        if name in tables:
            return tables[name]
        t = tables[name] = MagicMock()
        if name == "posts":
            t.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=mock_post_data)
        elif name == "instagram_accounts":
            t.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=mock_account_data)
        elif name == "scheduled_jobs":
            t.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=mock_job_data)
        return t

    mock_supabase.table.side_effect = table_mock

    mock_publisher = MagicMock()
    mock_publisher.get_publishing_quota.return_value = {"quota_usage": 100, "quota_total": 100}

    mock_telegram = MagicMock()
    mock_telegram.send_status_notification = AsyncMock()

    with patch("services.scheduler.post_scheduler.get_supabase_admin_client", return_value=mock_supabase), \
         patch("services.scheduler.post_scheduler.InstagramPublisher", return_value=mock_publisher), \
         patch("services.telegram_service.TelegramService", return_value=mock_telegram), \
         patch("services.scheduler.post_scheduler.PostScheduler") as mock_sched_cls:

        mock_scheduler_instance = MagicMock()
        mock_sched_cls.return_value = mock_scheduler_instance

        publish_post_job(post_id)

        updates = [c[0][0] for c in mock_supabase.table("scheduled_jobs").update.call_args_list]
        failed_update = next((u for u in updates if u.get("status") == "failed"), None)
        assert failed_update is not None, "scheduled_jobs must be updated to status='failed'"

        # 1. scheduled_jobs y posts marcados como failed
        assert failed_update.get("status") == "failed"
        assert failed_update.get("error_message") == "PUBLISH_QUOTA_EXCEEDED"
        post_updates = [c[0][0] for c in mock_supabase.table("posts").update.call_args_list]
        assert any(pu.get("status") == "failed" for pu in post_updates)

        # 2. No se reprogramó en APScheduler
        mock_scheduler_instance.scheduler.add_job.assert_not_called()

        # 3. Aviso Telegram de fallo
        assert mock_telegram.send_status_notification.call_count >= 1


def test_publish_post_job_quota_check_fails_open_and_publishes():
    """Fail-open: si get_publishing_quota devuelve None, se procede a publicar."""
    post_id = 102
    mock_supabase = MagicMock()

    mock_post_data = {
        "id": post_id,
        "status": "scheduled",
        "user_id": "u1",
        "media_url": "https://img.url/photo.jpg",
        "content": "Test caption",
        "post_type": "image",
    }
    mock_account_data = {
        "id": 1,
        "user_id": "u1",
        "telegram_chat_id": "12345",
        "is_active": True,
        "drive_folder_id": None,
    }

    tables = {}

    def table_mock(name):
        # Un mock por tabla: las aserciones leen las llamadas de update de cada una
        if name in tables:
            return tables[name]
        t = tables[name] = MagicMock()
        if name == "posts":
            t.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=mock_post_data)
        elif name == "instagram_accounts":
            t.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=mock_account_data)
        return t

    mock_supabase.table.side_effect = table_mock

    mock_publisher = MagicMock()
    # Consulta de cuota falla
    mock_publisher.get_publishing_quota.return_value = None
    mock_publisher.publish_post.return_value = {"id": "ig_post_102"}

    with patch("services.scheduler.post_scheduler.get_supabase_admin_client", return_value=mock_supabase), \
         patch("services.scheduler.post_scheduler.InstagramPublisher", return_value=mock_publisher):

        publish_post_job(post_id)

        # Debe haber llamado a publish_post igualmente
        mock_publisher.publish_post.assert_called_once()


def test_publish_post_job_with_available_quota_publishes_normally():
    """Con cuota disponible -> flujo normal de publicación."""
    post_id = 103
    mock_supabase = MagicMock()

    mock_post_data = {
        "id": post_id,
        "status": "scheduled",
        "user_id": "u1",
        "media_url": "https://img.url/photo.jpg",
        "content": "Test caption",
        "post_type": "image",
    }
    mock_account_data = {
        "id": 1,
        "user_id": "u1",
        "telegram_chat_id": "12345",
        "is_active": True,
        "drive_folder_id": None,
    }

    tables = {}

    def table_mock(name):
        # Un mock por tabla: las aserciones leen las llamadas de update de cada una
        if name in tables:
            return tables[name]
        t = tables[name] = MagicMock()
        if name == "posts":
            t.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=mock_post_data)
        elif name == "instagram_accounts":
            t.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=mock_account_data)
        return t

    mock_supabase.table.side_effect = table_mock

    mock_publisher = MagicMock()
    mock_publisher.get_publishing_quota.return_value = {"quota_usage": 10, "quota_total": 100}
    mock_publisher.publish_post.return_value = {"id": "ig_post_103"}

    with patch("services.scheduler.post_scheduler.get_supabase_admin_client", return_value=mock_supabase), \
         patch("services.scheduler.post_scheduler.InstagramPublisher", return_value=mock_publisher):

        publish_post_job(post_id)

        mock_publisher.publish_post.assert_called_once()


def test_publish_post_job_quota_exceeded_later_deferral_does_not_notify_again():
    """Del 2º aplazamiento en adelante no se repite el aviso de Telegram."""
    tables = {}

    def table_mock(name):
        if name in tables:
            return tables[name]
        t = tables[name] = MagicMock()
        if name == "posts":
            t.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data={"id": 104, "status": "scheduled", "user_id": "u1", "media_url": "https://img.url/p.jpg", "content": "", "post_type": "image"}
            )
        elif name == "instagram_accounts":
            t.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data={"id": 1, "telegram_chat_id": "12345", "drive_folder_id": None}
            )
        elif name == "scheduled_jobs":
            t.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data={"retry_count": 0, "max_retries": 3, "quota_deferrals": 1}
            )
        return t

    mock_supabase = MagicMock()
    mock_supabase.table.side_effect = table_mock
    mock_publisher = MagicMock()
    mock_publisher.get_publishing_quota.return_value = {"quota_usage": 100, "quota_total": 100}
    mock_telegram = MagicMock()
    mock_telegram.send_status_notification = AsyncMock()

    with patch("services.scheduler.post_scheduler.get_supabase_admin_client", return_value=mock_supabase), \
         patch("services.scheduler.post_scheduler.InstagramPublisher", return_value=mock_publisher), \
         patch("services.telegram_service.TelegramService", return_value=mock_telegram), \
         patch("services.scheduler.post_scheduler.PostScheduler"):
        publish_post_job(104)

    updates = [c[0][0] for c in tables["scheduled_jobs"].update.call_args_list]
    assert any(u.get("status") == "deferred_quota" and u.get("quota_deferrals") == 2 for u in updates)
    mock_telegram.send_status_notification.assert_not_called()
