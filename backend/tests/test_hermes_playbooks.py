import pytest
from services.hermes.playbooks import load_playbook, list_playbooks, PLAYBOOKS


def test_list_playbooks():
    playbooks = list_playbooks()
    assert isinstance(playbooks, list)
    assert "hooks" in playbooks
    assert "hashtag-layering" in playbooks
    assert "content-matrix" in playbooks
    assert len(playbooks) >= 3


def test_playbooks_descriptions():
    assert isinstance(PLAYBOOKS, dict)
    assert len(PLAYBOOKS) >= 3
    for name, desc in PLAYBOOKS.items():
        assert isinstance(name, str) and len(name) > 0
        assert isinstance(desc, str) and len(desc) > 0


def test_load_playbook_returns_content():
    content_hooks = load_playbook("hooks")
    assert isinstance(content_hooks, str)
    assert len(content_hooks) > 0

    content_hashtags = load_playbook("hashtag-layering")
    assert isinstance(content_hashtags, str)
    assert len(content_hashtags) > 0

    content_matrix = load_playbook("content-matrix")
    assert isinstance(content_matrix, str)
    assert len(content_matrix) > 0


def test_load_playbook_with_md_extension():
    content_hooks = load_playbook("hooks.md")
    assert isinstance(content_hooks, str)
    assert len(content_hooks) > 0


def test_load_playbook_nonexistent_raises_error():
    with pytest.raises((FileNotFoundError, Exception)) as exc_info:
        load_playbook("nonexistent_playbook_xyz")
    assert "nonexistent_playbook_xyz" in str(exc_info.value) or "no encontrado" in str(exc_info.value).lower()


def test_hashtag_playbook_layer3_prefers_community_or_place_over_personal_brand():
    content = load_playbook("hashtag-layering")
    assert "#marcapersonal" not in content
    assert "lugar" in content
    assert "solo si la voz es de marca profesional" in content


def test_hooks_playbook_contains_26_formulas_and_modes():
    from services.content_quality._data import load_json
    hooks_data = load_json("hooks_data.json")
    formulas = hooks_data.get("formulas", [])
    assert len(formulas) == 26

    content = load_playbook("hooks")
    content_lower = content.lower()

    # Todas las 26 fórmulas deben estar documentadas en el playbook
    for f in formulas:
        f_name_part = f["name"].lower().split("/")[0].strip()
        assert (f"fórmula {f['id']}" in content_lower or
                f"formula {f['id']}" in content_lower or
                f"{f['id']}." in content or
                f_name_part in content_lower), f"Fórmula {f['id']} ({f['name']}) ausente en hooks.md"

    # Agrupadas o clasificadas por modo
    assert "comercial" in content_lower or "commercial" in content_lower
    assert "personal" in content_lower or "storyline" in content_lower

    # Dealbreakers explícitos (aperturas prohibidas)
    assert "stop scrolling" in content_lower
    assert "hola a todos" in content_lower

    # Límite visible de 125 caracteres
    assert "125" in content


def test_content_matrix_playbook_defines_weekly_matrices_by_strategy():
    content = load_playbook("content-matrix")
    content_lower = content.lower()

    # Matriz comercial: 1 Proof-Reel, 2 Teach, 1 Opinion, 1 Offer
    assert "proof" in content_lower or "prueba" in content_lower
    assert "teach" in content_lower or "educativo" in content_lower or "enseñanza" in content_lower
    assert "opinion" in content_lower or "opinión" in content_lower
    assert "offer" in content_lower or "oferta" in content_lower

    # Matriz personal: 2 Story, 1 Aprendizaje, 1 Reflexión
    assert "story" in content_lower or "historia" in content_lower
    assert "aprendizaje" in content_lower
    assert "reflexi" in content_lower  # reflexión / reflexion

    # Regla dura: sin venta directa en personal_storyline
    assert "sin venta" in content_lower

