"""
Comparación horario configurado vs. histórico real. Compartida por el orquestador
(sugerencias de fin de sesión) y strategy_linter (BEST_TIMES_DISAGREE).
"""

from typing import Any, Dict, List, Optional


def schedule_disagreement(configured_best_times: List[Any], empirical: Dict[str, Any]) -> Optional[str]:
    """Decide si los horarios reales del histórico difieren *de forma significativa*
    de los que el usuario configuró a mano, y devuelve la razón concreta (para el
    rationale de la sugerencia) o None si no hay discrepancia relevante.

    `empirical` es el dict de AnalyticsService.get_empirical_scheduling_data:
    {has_data, top_times: ["HH:00", ...], best_times_by_weekday, summary_text}.
    La configuración manual del usuario NO se toca — esto solo alimenta una
    sugerencia visible en el timeline.

    Criterio: se sugiere solo cuando NINGUNA de las horas top del histórico cae a
    ±1h de alguna hora configurada — así "09:00 vs 10:00" no dispara nada, pero
    "mañanas configuradas vs. histórico que rinde de noche" sí. Barra alta a
    propósito: pocas sugerencias, todas con señal real."""
    def _hour(hhmm: Any) -> Optional[int]:
        try:
            return int(str(hhmm).split(":")[0])
        except (ValueError, IndexError):
            return None

    configured_hours = {h for h in (_hour(t) for t in configured_best_times) if h is not None}
    empirical_hours = [h for h in (_hour(t) for t in empirical.get("top_times", [])) if h is not None]
    if not configured_hours or not empirical_hours:
        return None

    if any(min(abs(eh - ch) for ch in configured_hours) <= 1 for eh in empirical_hours):
        return None

    configured_label = ", ".join(str(t) for t in configured_best_times)
    empirical_label = empirical.get("summary_text") or ", ".join(
        f"{h:02d}:00" for h in empirical_hours
    )
    return (
        f"Tus horarios configurados ({configured_label}) no coinciden con las mejores "
        f"horas de tu histórico real ({empirical_label}). Considera revisarlos en "
        "la pestaña Publicación de la estrategia. Esta sesión respetó tu configuración sin cambios."
    )
