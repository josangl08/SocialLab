"""
Tests unitarios de utilidades de zona horaria (backend/utils/timezones.py).
Cubre:
- Ida y vuelta UTC ↔ pared
- Cambio de horario 25-oct-2026 en Madrid (DST CEST -> CET)
- Zona inválida (error)
- Sin offset vs con offset en parse_schedule_time
- Día distinto entre zonas
- effective_timezone con varias combinaciones de cuenta y client_tz
"""
from datetime import datetime, timezone
import pytest
from zoneinfo import ZoneInfo

from utils.timezones import (
    effective_timezone,
    get_zone_info,
    local_to_utc,
    parse_schedule_time,
    to_local,
)


def test_effective_timezone_priorities():
    # 1. client_tz tiene máxima prioridad
    acc = {"primary_timezone": "America/New_York", "detected_timezone": "Asia/Tokyo"}
    assert effective_timezone(acc, client_tz="Europe/Madrid") == "Europe/Madrid"

    # 2. primary_timezone de la cuenta
    assert effective_timezone(acc) == "America/New_York"

    # 3. detected_timezone si primary es None/vacío
    acc_detected = {"primary_timezone": None, "detected_timezone": "Asia/Kuching"}
    assert effective_timezone(acc_detected) == "Asia/Kuching"

    # 4. Fallback a UTC si nada configurado
    assert effective_timezone({"primary_timezone": None, "detected_timezone": None}) == "UTC"
    assert effective_timezone(None) == "UTC"
    assert effective_timezone({}) == "UTC"


def test_effective_timezone_object_attribute():
    class MockAccount:
        primary_timezone = "Europe/Paris"
        detected_timezone = "UTC"

    assert effective_timezone(MockAccount()) == "Europe/Paris"


def test_invalid_timezone_raises():
    with pytest.raises(ValueError):
        get_zone_info("Invalid/NonExistent_Zone")

    with pytest.raises(ValueError):
        effective_timezone(client_tz="Invalid/Zone")

    with pytest.raises(ValueError):
        effective_timezone({"primary_timezone": "Invalid/Zone"})


def test_roundtrip_utc_to_local_and_back():
    # 2026-10-14 18:00 UTC en Europe/Madrid (horario de verano CEST, UTC+2)
    utc_dt = datetime(2026, 10, 14, 18, 0, 0, tzinfo=timezone.utc)
    local_dt = to_local(utc_dt, "Europe/Madrid")

    assert local_dt.year == 2026
    assert local_dt.month == 10
    assert local_dt.day == 14
    assert local_dt.hour == 20
    assert local_dt.minute == 0

    back_to_utc = local_to_utc(local_dt, "Europe/Madrid")
    assert back_to_utc == utc_dt


def test_dst_change_madrid_october_2026():
    """
    En Europa/Madrid, el cambio de horario de verano a invierno ocurre
    el domingo 25 de octubre de 2026 (a las 03:00 CEST pasa a ser 02:00 CET).
    """
    # Antes del cambio: 24 de octubre, CEST (UTC+2)
    # 18:00 UTC -> 20:00 Madrid
    before_dst = datetime(2026, 10, 24, 18, 0, 0, tzinfo=timezone.utc)
    local_before = to_local(before_dst, "Europe/Madrid")
    assert local_before.hour == 20
    assert local_before.utcoffset().total_seconds() == 7200  # +2h

    # Después del cambio: 26 de octubre, CET (UTC+1)
    # 18:00 UTC -> 19:00 Madrid
    after_dst = datetime(2026, 10, 26, 18, 0, 0, tzinfo=timezone.utc)
    local_after = to_local(after_dst, "Europe/Madrid")
    assert local_after.hour == 19
    assert local_after.utcoffset().total_seconds() == 3600  # +1h

    # Hora de pared 20:00 conservada:
    # 20:00 local el 24-oct -> 18:00 UTC
    # 20:00 local el 26-oct -> 19:00 UTC
    wall_before = datetime(2026, 10, 24, 20, 0, 0)
    assert local_to_utc(wall_before, "Europe/Madrid") == datetime(2026, 10, 24, 18, 0, 0, tzinfo=timezone.utc)

    wall_after = datetime(2026, 10, 26, 20, 0, 0)
    assert local_to_utc(wall_after, "Europe/Madrid") == datetime(2026, 10, 26, 19, 0, 0, tzinfo=timezone.utc)


def test_different_day_between_zones():
    # 2026-10-14 23:00 UTC es 2026-10-15 01:00 en Europe/Madrid (+2)
    utc_dt = datetime(2026, 10, 14, 23, 0, 0, tzinfo=timezone.utc)
    madrid_dt = to_local(utc_dt, "Europe/Madrid")
    assert madrid_dt.day == 15
    assert madrid_dt.hour == 1

    # 2026-10-14 18:00 UTC es 2026-10-15 02:00 en Asia/Kuching (UTC+8)
    utc_post = datetime(2026, 10, 14, 18, 0, 0, tzinfo=timezone.utc)
    kuching_dt = to_local(utc_post, "Asia/Kuching")
    assert kuching_dt.day == 15
    assert kuching_dt.hour == 2


def test_parse_schedule_time_without_offset():
    # Sin offset: se interpreta en la zona indicada y devuelve UTC
    # '2026-10-14T20:00:00' en Europe/Madrid (UTC+2) -> 18:00 UTC
    parsed = parse_schedule_time("2026-10-14T20:00:00", "Europe/Madrid")
    expected = datetime(2026, 10, 14, 18, 0, 0, tzinfo=timezone.utc)
    assert parsed == expected


def test_parse_schedule_time_with_offset():
    # Con offset explícito: respeta el offset del string y lo pasa a UTC, ignorando el tz provisto
    # '2026-10-14T20:00:00+08:00' -> 12:00 UTC
    parsed = parse_schedule_time("2026-10-14T20:00:00+08:00", "Europe/Madrid")
    expected = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
    assert parsed == expected

    # Con 'Z': 18:00Z -> 18:00 UTC
    parsed_z = parse_schedule_time("2026-10-14T18:00:00Z", "Europe/Madrid")
    assert parsed_z == datetime(2026, 10, 14, 18, 0, 0, tzinfo=timezone.utc)
