from typing import Dict
from mcp.server.fastmcp import FastMCP
from services.hermes.skills import (
    run_visual_performance_skill,
    run_niche_research_for_account,
    VISUAL_PERFORMANCE_SKILL,
)

mcp = FastMCP("Hermes Skills Server")

@mcp.tool()
def hermes_run_skill(skill_name: str, account_id: int, force_refresh: bool = False) -> Dict:
    """Runs (or reuses, if recent enough) a dynamic Hermes skill for this account.
    Currently supported skill_name: 'visual_performance_correlation' — correlates
    the visual theme/content of posts with real Instagram performance. Set
    force_refresh=True only if the user explicitly asks to update/refresh the
    analysis; otherwise the last stored result is reused if still fresh."""
    if skill_name == VISUAL_PERFORMANCE_SKILL:
        return run_visual_performance_skill(account_id, force_refresh=force_refresh)
    return {"error": f"Skill desconocida: {skill_name}"}


@mcp.tool()
def hermes_run_niche_research(account_id: int, force_refresh: bool = False) -> Dict:
    """Investiga tendencias y mejores prácticas actuales de Instagram para el/los
    nicho(s) de esta cuenta (deportistas de élite y/o lifestyle de viajes y
    fotografía, detectados automáticamente por el sector/objetivo de la cuenta),
    vía búsqueda web real. Devuelve niches=[] si la cuenta no encaja en ningún
    nicho reconocido. Reutiliza el último resultado si sigue vigente, salvo que
    el usuario pida explícitamente actualizarlo."""
    return run_niche_research_for_account(account_id, force_refresh=force_refresh)
