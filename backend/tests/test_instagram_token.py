"""Fecha real de reconexión de las cuentas de Instagram (AD-4)."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from services.instagram_token import check_account_tokens, get_reconnect_deadline

DATA_ACCESS = int(datetime(2027, 1, 16, 12, 38, 55, tzinfo=timezone.utc).timestamp())


def _debug_response(**data):
    response = MagicMock()
    response.json.return_value = {"data": data}
    return response


def test_deadline_is_data_access_expiry_when_token_never_expires():
    with patch("services.instagram_token.requests.get",
               return_value=_debug_response(is_valid=True, expires_at=0, data_access_expires_at=DATA_ACCESS)) as mock_get:
        status = get_reconnect_deadline("tok")

    assert status == {"is_valid": True, "reconnect_by": datetime(2027, 1, 16, 12, 38, 55, tzinfo=timezone.utc)}
    assert mock_get.call_args[0][0].endswith("/debug_token")
    assert mock_get.call_args[1]["params"]["input_token"] == "tok"


def test_deadline_uses_token_expiry_when_earlier():
    token_expiry = DATA_ACCESS - 86400 * 30
    with patch("services.instagram_token.requests.get",
               return_value=_debug_response(is_valid=True, expires_at=token_expiry, data_access_expires_at=DATA_ACCESS)):
        status = get_reconnect_deadline("tok")

    assert status["reconnect_by"] == datetime.fromtimestamp(token_expiry, tz=timezone.utc)


def test_deadline_none_when_debug_token_fails():
    with patch("services.instagram_token.requests.get", side_effect=Exception("timeout")):
        assert get_reconnect_deadline("tok") is None


def _run_job(accounts, statuses):
    """Ejecuta el job con cuentas y estados de debug_token simulados (por token)."""
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=accounts)
    telegram = MagicMock()
    telegram.send_reconnect_reminder = AsyncMock()

    def deadline(token):
        status = statuses[token]
        if isinstance(status, Exception):
            raise status
        return status

    with patch("services.instagram_token.get_supabase_admin_client", return_value=db), \
         patch("services.instagram_token.decrypt_token", side_effect=lambda t: t), \
         patch("services.instagram_token.get_reconnect_deadline", side_effect=deadline), \
         patch("services.telegram_service.TelegramService", return_value=telegram):
        check_account_tokens()
    return db, telegram


def _account(account_id, token, chat="111"):
    return {"id": account_id, "username": f"user{account_id}", "long_lived_access_token": token,
            "telegram_chat_id": chat, "is_active": True}


def _in_days(days):
    """Mediodía UTC dentro de `days` días: el job cuenta días de calendario UTC."""
    day = datetime.now(timezone.utc).date() + timedelta(days=days)
    return datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc)


def test_job_updates_expires_at_without_reminder_far_from_deadline():
    reconnect_by = _in_days(60)
    db, telegram = _run_job([_account(1, "t1")], {"t1": {"is_valid": True, "reconnect_by": reconnect_by}})

    db.table.return_value.update.assert_called_once_with({"expires_at": reconnect_by.isoformat()})
    telegram.send_reconnect_reminder.assert_not_awaited()


def test_job_reminds_only_at_7_3_and_1_days():
    accounts = [_account(i, f"t{i}") for i in (1, 2, 3, 4, 5)]
    statuses = {f"t{i}": {"is_valid": True, "reconnect_by": _in_days(days)}
                for i, days in zip((1, 2, 3, 4, 5), (7, 3, 1, 5, 2))}
    _, telegram = _run_job(accounts, statuses)

    reminded = sorted(c.args[2] for c in telegram.send_reconnect_reminder.await_args_list)
    assert reminded == [1, 3, 7]


def test_job_marks_invalid_token_and_does_not_remind():
    reconnect_by = _in_days(7)
    db, telegram = _run_job([_account(1, "t1")], {"t1": {"is_valid": False, "reconnect_by": reconnect_by}})

    db.table.return_value.update.assert_called_once_with(
        {"token_invalid": True, "expires_at": reconnect_by.isoformat()}
    )
    telegram.send_reconnect_reminder.assert_not_awaited()


def test_job_leaves_account_untouched_when_debug_token_fails_and_continues():
    accounts = [_account(1, "t1"), _account(2, "t2"), _account(3, "t3")]
    statuses = {"t1": None, "t2": RuntimeError("boom"), "t3": {"is_valid": True, "reconnect_by": _in_days(3)}}
    db, telegram = _run_job(accounts, statuses)

    db.table.return_value.update.assert_called_once()
    db.table.return_value.update.return_value.eq.assert_called_once_with("id", 3)
    telegram.send_reconnect_reminder.assert_awaited_once_with("111", "user3", 3)


def test_job_only_checks_facebook_login_accounts():
    """debug_token no sirve para tokens de Instagram Login: el job filtra login_type='facebook'."""
    db, _ = _run_job([], {})

    db.table.return_value.select.return_value.eq.assert_called_once_with("login_type", "facebook")
