"""resolve_allowed_day: días específicos estrictos (AD-3)."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from services.scheduler.fixed_days import resolve_allowed_day, weekdays_from_names

MADRID = ZoneInfo("Europe/Madrid")
TUE, THU = 1, 3
# Semana del lunes 2026-11-02 al domingo 2026-11-08
MONDAY = date(2026, 11, 2)


def _dt(day: int, hour: int = 20, tz=MADRID) -> datetime:
    return datetime(2026, 11, day, hour, 0, tzinfo=tz)


def test_allowed_day_unchanged():
    dt = _dt(5)  # jueves
    assert resolve_allowed_day(dt, {TUE, THU}, set(), None, MONDAY) == (dt, None)


def test_moves_to_nearest_free_allowed_day_keeping_time():
    new, reason = resolve_allowed_day(_dt(6), {TUE, THU}, set(), None, MONDAY)  # viernes → jueves
    assert new == _dt(5)
    assert reason == "fixed_days"


def test_skips_occupied_day():
    new, _ = resolve_allowed_day(_dt(6), {TUE, THU}, {date(2026, 11, 5)}, None, MONDAY)
    assert new == _dt(3)


def test_tie_broken_by_weekday_score():
    # miércoles: martes y jueves a 1 día; el martes rinde más
    new, _ = resolve_allowed_day(_dt(4), {TUE, THU}, set(), {TUE: 4.5, THU: 2.0}, MONDAY)
    assert new == _dt(3)


def test_tie_without_data_picks_later_day():
    new, _ = resolve_allowed_day(_dt(4), {TUE, THU}, set(), {}, MONDAY)
    assert new == _dt(5)


def test_scores_callable_only_evaluated_on_tie():
    calls = []

    def scores():
        calls.append(1)
        return {}

    resolve_allowed_day(_dt(6), {TUE, THU}, set(), scores, MONDAY)
    assert calls == []
    resolve_allowed_day(_dt(4), {TUE, THU}, set(), scores, MONDAY)
    assert calls == [1]


def test_all_occupied_falls_back_to_nearest_even_if_taken():
    occupied = {date(2026, 11, 3), date(2026, 11, 5)}
    new, _ = resolve_allowed_day(_dt(6), {TUE, THU}, occupied, None, MONDAY)
    assert new == _dt(5)


def test_all_allowed_days_past_moves_to_next_week():
    new, reason = resolve_allowed_day(_dt(7), {TUE, THU}, set(), None, date(2026, 11, 7))
    assert new == datetime(2026, 11, 10, 20, 0, tzinfo=MADRID)  # martes siguiente
    assert reason == "fixed_days"


def test_past_allowed_day_excluded():
    # hoy viernes: el jueves ya pasó, así que el domingo se mueve al sábado
    new, _ = resolve_allowed_day(_dt(8), {THU, 5}, set(), None, date(2026, 11, 6))
    assert new == _dt(7)


def test_week_boundary_uses_local_zone_utc_plus_8():
    kl = ZoneInfo("Asia/Kuala_Lumpur")
    # Domingo 23:30 en UTC+8 (sábado en UTC): semana local del 2 al 8
    dt = datetime(2026, 11, 8, 23, 30, tzinfo=kl)
    new, _ = resolve_allowed_day(dt, {TUE, THU}, set(), None, MONDAY)
    assert new == datetime(2026, 11, 5, 23, 30, tzinfo=kl)


def test_weekdays_from_names_accepts_english_and_spanish():
    assert weekdays_from_names(["Tuesday", "jueves", "", "nope"]) == {TUE, THU}
