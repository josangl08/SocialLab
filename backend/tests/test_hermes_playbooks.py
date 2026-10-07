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
