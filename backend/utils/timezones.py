"""
Utilidades de zonas horarias para SocialLab (AD-2, AD-3, AD-11).

Maneja zona efectiva de cuentas, conversiones UTC ↔ hora de pared local,
y normalización de fechas con o sin offset.
"""
from datetime import datetime, timezone
from typing import Any, Optional, Union
import zoneinfo
from zoneinfo import ZoneInfo


def get_zone_info(tz: Union[str, ZoneInfo]) -> ZoneInfo:
    """Valida y devuelve un objeto ZoneInfo para el string IANA dado."""
    if isinstance(tz, ZoneInfo):
        return tz
    if not isinstance(tz, str) or not tz.strip():
        raise ValueError(f"Zona horaria inválida: {tz}")
    try:
        return ZoneInfo(tz.strip())
    except (zoneinfo.ZoneInfoNotFoundError, KeyError) as e:
        raise ValueError(f"Zona horaria no encontrada en la base IANA: {tz}") from e


def effective_timezone(account: Optional[Any] = None, client_tz: Optional[str] = None) -> str:
    """
    Determina la zona horaria efectiva (AD-2).
    Prioridad:
      1. client_tz si se proporciona explícitamente en la petición
      2. primary_timezone de la cuenta
      3. detected_timezone de la cuenta (detectada del navegador)
      4. 'UTC' por defecto
    """
    if client_tz and client_tz.strip():
        # Validar que sea IANA válida
        get_zone_info(client_tz)
        return client_tz.strip()

    if account is not None:
        primary = None
        detected = None

        if isinstance(account, dict):
            primary = account.get("primary_timezone")
            detected = account.get("detected_timezone")
        else:
            primary = getattr(account, "primary_timezone", None)
            detected = getattr(account, "detected_timezone", None)

        if primary and primary.strip():
            get_zone_info(primary)
            return primary.strip()

        if detected and detected.strip():
            get_zone_info(detected)
            return detected.strip()

    return "UTC"


def to_local(dt: datetime, tz: Union[str, ZoneInfo]) -> datetime:
    """
    Convierte una fecha UTC a la zona horaria indicada.
    Si dt es naive, se asume UTC.
    """
    zi = get_zone_info(tz)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(zi)


def local_to_utc(dt: datetime, tz: Union[str, ZoneInfo]) -> datetime:
    """
    Convierte una fecha local (en la zona tz) a UTC consciente.
    Si dt es naive, se interpreta en tz.
    """
    zi = get_zone_info(tz)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=zi)
    else:
        dt = dt.astimezone(zi)
    return dt.astimezone(timezone.utc)


def parse_schedule_time(value: Union[str, datetime], tz: Union[str, ZoneInfo]) -> datetime:
    """
    Normaliza una fecha de programación a datetime consciente en UTC (AD-11).
    - Si value incluye offset/zona (ej. '...Z' o '...+02:00'): se respeta el offset y se pasa a UTC.
    - Si value no incluye offset (ej. '2026-10-14T18:00:00'): se interpreta en tz y se pasa a UTC.
    """
    zi = get_zone_info(tz)

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=zi).astimezone(timezone.utc)
        return value.astimezone(timezone.utc)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Fecha inválida: {value}")

    raw = value.strip()

    # Si termina en Z o z, normalizar a +00:00 para fromisoformat si es necesario
    if raw.endswith("Z") or raw.endswith("z"):
        dt = datetime.fromisoformat(raw[:-1] + "+00:00")
        return dt.astimezone(timezone.utc)

    dt = datetime.fromisoformat(raw)

    if dt.tzinfo is not None:
        # Tenía offset explícito
        return dt.astimezone(timezone.utc)

    # Naive: interpretar en la zona indicada
    return dt.replace(tzinfo=zi).astimezone(timezone.utc)
