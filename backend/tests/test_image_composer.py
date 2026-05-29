import io
import requests
import pytest
from PIL import Image
from services.image_composer import get_image_composer


def _create_player_graphic() -> bytes:
    img = Image.new("RGBA", (800, 600), (30, 30, 40, 230))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_team_graphic() -> bytes:
    img = Image.new("RGBA", (900, 700), (20, 20, 30, 240))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_match_graphic() -> bytes:
    img = Image.new("RGBA", (1000, 500), (15, 76, 45, 250))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_compose_player_stats(mock_supabase_client):
    composer = get_image_composer()
    templates = mock_supabase_client.table("templates").select("*").execute()
    template = next(t for t in templates.data if "modern_blue" in t["name"])

    template_bytes = requests.get(template["image_url"]).content
    result = composer.compose_post(
        template_image=template_bytes,
        graphic_image=_create_player_graphic(),
        template_config=template.get("template_config", {}),
        format_type="square",
    )

    assert result is not None
    assert isinstance(result, bytes)
    img = Image.open(io.BytesIO(result))
    assert img.size == (1080, 1080)


def test_compose_team_performance(mock_supabase_client):
    composer = get_image_composer()
    templates = mock_supabase_client.table("templates").select("*").execute()
    template = next(t for t in templates.data if "team_performance" in t["name"])

    template_bytes = requests.get(template["image_url"]).content
    result = composer.compose_post(
        template_image=template_bytes,
        graphic_image=_create_team_graphic(),
        template_config=template.get("template_config", {}),
        format_type="square",
    )

    assert result is not None
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_compose_match_result(mock_supabase_client):
    composer = get_image_composer()
    templates = mock_supabase_client.table("templates").select("*").execute()
    template = next(t for t in templates.data if "match_result" in t["name"])

    template_bytes = requests.get(template["image_url"]).content
    result = composer.compose_post(
        template_image=template_bytes,
        graphic_image=_create_match_graphic(),
        template_config=template.get("template_config", {}),
        format_type="square",
    )

    assert result is not None
    assert isinstance(result, bytes)


def test_compose_story_format(mock_supabase_client):
    composer = get_image_composer()
    templates = mock_supabase_client.table("templates").select("*").execute()
    template = next(t for t in templates.data if "story" in t["name"])

    template_bytes = requests.get(template["image_url"]).content
    result = composer.compose_post(
        template_image=template_bytes,
        graphic_image=_create_player_graphic(),
        template_config=template.get("template_config", {}),
        format_type="story",
    )

    assert result is not None
    assert isinstance(result, bytes)
    img = Image.open(io.BytesIO(result))
    assert img.size == (1080, 1920)


def test_compose_returns_valid_png(mock_supabase_client):
    """Result must be parseable as PNG by Pillow."""
    composer = get_image_composer()
    templates = mock_supabase_client.table("templates").select("*").execute()
    template = templates.data[0]

    template_bytes = requests.get(template["image_url"]).content
    result = composer.compose_post(
        template_image=template_bytes,
        graphic_image=_create_player_graphic(),
        format_type="square",
    )

    assert result is not None
    img = Image.open(io.BytesIO(result))
    assert img.format == "PNG"
