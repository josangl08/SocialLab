"""
Manifiesto único de las capacidades de Hermes, clasificadas por perfil de coste.

Tres clases (design.md §Manifiesto HERMES_CAPABILITIES):
- ``playbook``       — metodología inyectada verbatim en el prompt; coste ≈ 0 (solo tokens).
- ``runtime_skill``  — skill con caché; 1 llamada a Gemini solo al caducar; consume turnos
                       si la invoca el modelo.
- ``deterministic``  — cálculo determinista sobre datos; 1 consulta a base de datos.

Es un catálogo estático (sin parámetros de cuenta). Lo consume Hermes Mind vía
``GET /api/agent/capabilities``.
"""

from typing import Dict, List

from services.hermes.playbooks import PLAYBOOKS

HERMES_CAPABILITIES: List[Dict[str, str]] = [
    *(
        {
            "name": name,
            "kind": "playbook",
            "description": description,
            "cost_note": "tokens de prompt; coste ≈ 0",
        }
        for name, description in PLAYBOOKS.items()
    ),
    {
        "name": "niche_research",
        "kind": "runtime_skill",
        "description": "Investiga tendencias y mejores prácticas actuales de Instagram para "
                       "el nicho de la cuenta vía búsqueda web real (caché 30 días).",
        "cost_note": "1 llamada a Gemini al caducar la caché; consume turnos si la invoca el modelo",
    },
    {
        "name": "visual_performance_correlation",
        "kind": "runtime_skill",
        "description": "Correlaciona el tema/objetos/mood visual de los posts publicados con "
                       "su rendimiento real en Instagram (caché 14 días).",
        "cost_note": "1 llamada a Gemini al caducar la caché; consume turnos si la invoca el modelo",
    },
    {
        "name": "empirical_scheduling",
        "kind": "deterministic",
        "description": "Mejores horas de publicación derivadas del histórico real de la cuenta "
                       "(analytics_get_empirical_scheduling_data).",
        "cost_note": "1 consulta a base de datos",
    },
    {
        "name": "content_type_mix",
        "kind": "deterministic",
        "description": "Corrige el post_type de los posts creados en la sesión para que "
                       "cuadren con la cuota configurada (_correct_content_type_mix).",
        "cost_note": "1 consulta a base de datos",
    },
]
