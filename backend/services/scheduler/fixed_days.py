"""
Días específicos estrictos (AD-3): si Hermes programa un post en un día que la
cuenta no permite, se mueve de forma determinista al día permitido más adecuado
de la misma semana, conservando la hora local. Lógica pura, sin I/O.
"""

from datetime import date, datetime, timedelta
from typing import Callable, Dict, Iterable, Optional, Set, Tuple, Union

WEEKDAY_INDEX: Dict[str, int] = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, "jueves": 3,
    "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6,
}

WeekdayScores = Union[Dict[int, float], Callable[[], Dict[int, float]], None]


def weekdays_from_names(names: Iterable[str]) -> Set[int]:
    """Nombres de día (inglés o español, sin distinguir mayúsculas) → índices 0=lunes."""
    return {WEEKDAY_INDEX[n.strip().lower()] for n in names if n and n.strip().lower() in WEEKDAY_INDEX}


def resolve_allowed_day(
    local_dt: datetime,
    allowed_weekdays: Set[int],
    occupied_dates: Set[date],
    weekday_scores: WeekdayScores,
    today: date,
) -> Tuple[datetime, Optional[str]]:
    """Devuelve (fecha local final, "fixed_days" | None).

    1. Día permitido → sin cambio.
    2. Candidatos: días permitidos de la misma semana ISO, >= today y libres.
    3. Sin libres → los mismos sin filtro de ocupación; si todos han pasado, primer
       día permitido de la semana siguiente.
    4. Orden: menor distancia → mayor puntuación del día → el posterior.
    weekday_scores puede ser un callable: solo se evalúa si hay empate.
    """
    if not allowed_weekdays or local_dt.weekday() in allowed_weekdays:
        return local_dt, None

    original = local_dt.date()
    week_start = original - timedelta(days=original.weekday())
    week_days = [week_start + timedelta(days=wd) for wd in sorted(allowed_weekdays)]
    upcoming = [d for d in week_days if d >= today]

    candidates = [d for d in upcoming if d not in occupied_dates] or upcoming
    if not candidates:
        chosen = week_start + timedelta(days=7 + min(allowed_weekdays))
    else:
        min_distance = min(abs((d - original).days) for d in candidates)
        tied = [d for d in candidates if abs((d - original).days) == min_distance]
        if len(tied) > 1:
            scores = weekday_scores() if callable(weekday_scores) else (weekday_scores or {})
            chosen = max(tied, key=lambda d: (scores.get(d.weekday(), 0.0), d))
        else:
            chosen = tied[0]

    return local_dt.replace(year=chosen.year, month=chosen.month, day=chosen.day), "fixed_days"
