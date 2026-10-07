"""
Hermes Playbooks: Metodologías editoriales estructuradas (hooks, hashtags, matriz de contenido)
que se componen en los prompts de generación y estrategia.
"""

import os
from pathlib import Path
from typing import Dict, List

PLAYBOOKS: Dict[str, str] = {
    "hooks": "6 arquetipos de gancho de primera línea para maximizar retención",
    "hashtag-layering": "Estrategia de hashtags en 3 capas (específica, nicho, comunidad)",
    "content-matrix": "Matriz de contenidos con progresión de embudo adaptable de 4 fases",
}

_DIR = Path(__file__).parent


def list_playbooks() -> List[str]:
    """Devuelve la lista de nombres de playbooks disponibles."""
    return list(PLAYBOOKS.keys())


def load_playbook(name: str) -> str:
    """Carga el contenido markdown de un playbook hermano por su nombre.
    Lanza FileNotFoundError si el playbook no existe.
    """
    clean_name = name[:-3] if name.endswith(".md") else name
    file_path = _DIR / f"{clean_name}.md"
    if not file_path.exists():
        raise FileNotFoundError(f"Playbook '{name}' no encontrado en {file_path}")
    return file_path.read_text(encoding="utf-8").strip()
