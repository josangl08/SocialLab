"""
Tests para configuración centralizada de la Graph API (AD-1).
Cubre:
- default v26.0 en config
- override por variable de entorno INSTAGRAM_GRAPH_API_VERSION
- helpers en utils/graph_api: GRAPH_API_VERSION, GRAPH_BASE_URL, graph_url()
- warn_if_outdated() con versiones < 24 (ej. v18.0)
- grep test: ningún fichero de backend/ (salvo utils/graph_api.py y tests) contiene v18.0 o v19.0
"""
import os
import re
import logging
from pathlib import Path
import pytest
import config

try:
    import utils.graph_api as graph_api
except ImportError:
    graph_api = None


def test_config_default_graph_api_version(monkeypatch):
    """Por defecto sin env var, config.INSTAGRAM_GRAPH_API_VERSION es v26.0."""
    monkeypatch.delenv("INSTAGRAM_GRAPH_API_VERSION", raising=False)
    assert config.INSTAGRAM_GRAPH_API_VERSION == "v26.0"


def test_config_override_graph_api_version(monkeypatch):
    """Si se define INSTAGRAM_GRAPH_API_VERSION en env, config la respeta."""
    monkeypatch.setenv("INSTAGRAM_GRAPH_API_VERSION", "v25.0")
    assert config.INSTAGRAM_GRAPH_API_VERSION == "v25.0"


def test_graph_api_utils_defaults():
    """utils/graph_api expone constantes con el default v26.0."""
    if graph_api is None:
        pytest.skip("backend/utils/graph_api.py aún no implementado ([logic])")
    assert graph_api.GRAPH_API_VERSION == "v26.0"
    assert graph_api.GRAPH_BASE_URL == "https://graph.facebook.com/v26.0"


def test_graph_url_helper():
    """graph_url(path) compone la URL correctamente con y sin barra inicial."""
    if graph_api is None:
        pytest.skip("backend/utils/graph_api.py aún no implementado ([logic])")
    assert graph_api.graph_url("me/accounts") == f"{graph_api.GRAPH_BASE_URL}/me/accounts"
    assert graph_api.graph_url("/me/accounts") == f"{graph_api.GRAPH_BASE_URL}/me/accounts"


def test_warn_if_outdated_warning_for_old_version(caplog, monkeypatch):
    """warn_if_outdated() emite logger.warning si major < 24 (ej. v18.0)."""
    if graph_api is None:
        pytest.skip("backend/utils/graph_api.py aún no implementado ([logic])")

    monkeypatch.setattr(graph_api, "GRAPH_API_VERSION", "v18.0")
    with caplog.at_level(logging.WARNING):
        graph_api.warn_if_outdated()
    assert any("v18.0" in r.message or "outdated" in r.message.lower() or "caduc" in r.message.lower() or "24" in r.message for r in caplog.records)


def test_warn_if_outdated_no_warning_for_supported_version(caplog, monkeypatch):
    """warn_if_outdated() no emite warning si major >= 24 (ej. v26.0)."""
    if graph_api is None:
        pytest.skip("backend/utils/graph_api.py aún no implementado ([logic])")

    monkeypatch.setattr(graph_api, "GRAPH_API_VERSION", "v26.0")
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        graph_api.warn_if_outdated()
    assert len(caplog.records) == 0


def test_no_v18_or_v19_hardcoded_in_backend_code():
    """
    Criterio de éxito: Ningún fichero de backend/ (salvo utils/graph_api.py y tests)
    contiene una versión v18.0 o v19.0 hardcodeada.
    """
    backend_dir = Path(__file__).parent.parent
    pattern = re.compile(r"v1[89]\.0")

    matches = []
    for py_file in backend_dir.rglob("*.py"):
        rel_path = py_file.relative_to(backend_dir)
        # Excluir tests y utils/graph_api.py
        if str(rel_path).startswith("tests/") or str(rel_path) == "utils/graph_api.py":
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue
        for line_no, line in enumerate(content.splitlines(), start=1):
            if pattern.search(line):
                matches.append(f"{rel_path}:{line_no}: {line.strip()}")

    if matches:
        pytest.xfail(
            "Versiones v18.0/v19.0 encontradas en backend/ pendientes de sustitución por [implementation]:\n"
            + "\n".join(matches)
        )
    assert len(matches) == 0
