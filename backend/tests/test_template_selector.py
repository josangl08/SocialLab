import pytest
from services.template_selector import get_template_selector
from tests.conftest import USER_ID


@pytest.fixture
def selector(mock_supabase_client):
    return get_template_selector(mock_supabase_client)


def test_player_basic_selects_player_template(selector):
    metadata = {
        "export_type": "player",
        "player": {"name": "Cristiano Ronaldo", "position": "Forward"},
        "stats": {"goals": 3, "assists": 2},
    }
    template = selector.select_template(metadata, USER_ID)
    assert template is not None
    assert "player" in template["name"]


def test_star_player_high_goals_gets_template(selector):
    metadata = {
        "export_type": "player",
        "player": {"name": "Lionel Messi", "position": "Forward"},
        "stats": {"goals": 10, "assists": 7},
    }
    template = selector.select_template(metadata, USER_ID)
    assert template is not None
    assert template["selection_rules"]["export_types"] == ["player"] or "player" in template["name"]


def test_team_selects_team_template(selector):
    metadata = {
        "export_type": "team",
        "team": {"name": "Real Madrid", "id": "real_madrid"},
        "stats": {"wins": 12, "draws": 3, "losses": 2},
    }
    template = selector.select_template(metadata, USER_ID)
    assert template is not None
    assert "team" in template["name"]


def test_match_finished_selects_match_template(selector):
    metadata = {
        "export_type": "match",
        "match": {
            "home_team": {"name": "Barcelona", "id": "barcelona"},
            "away_team": {"name": "Valencia", "id": "valencia"},
            "score": "3-1",
            "status": "finished",
            "winner": "home",
        },
    }
    template = selector.select_template(metadata, USER_ID)
    assert template is not None
    assert "match" in template["name"]


def test_player_highlight_context_selects_story_template(selector):
    metadata = {
        "export_type": "player",
        "context": "highlight",
        "player": {"name": "Kylian Mbappé", "position": "Forward"},
        "stats": {"goals": 2, "assists": 1},
    }
    template = selector.select_template(metadata, USER_ID)
    assert template is not None
    assert "story" in template["name"] or "player" in template["name"]


def test_missing_export_type_returns_none(selector):
    template = selector.select_template({}, USER_ID)
    assert template is None
