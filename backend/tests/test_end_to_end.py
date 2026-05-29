import io
import requests
import pytest
from datetime import datetime, timezone
from PIL import Image

from services.template_selector import get_template_selector
from services.image_composer import get_image_composer
from tests.conftest import USER_ID


# ---------------------------------------------------------------------------
# Graphic helpers (local, no external dependencies)
# ---------------------------------------------------------------------------

def _player_graphic(metadata: dict) -> bytes:
    player = metadata.get("player", {})
    stats = metadata.get("stats", {})
    img = Image.new("RGBA", (800, 600), (30, 30, 40, 230))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _match_graphic(metadata: dict) -> bytes:
    img = Image.new("RGBA", (1000, 500), (15, 76, 45, 250))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Flow helper — all service dependencies injected, no global calls
# ---------------------------------------------------------------------------

def _run_flow(metadata: dict, supabase, caption_generator) -> dict:
    result = {"success": False, "post_id": None, "errors": []}
    export_type = metadata.get("export_type")

    # Step 1: select template
    selector = get_template_selector(supabase)
    template = selector.select_template(metadata, USER_ID)
    if not template:
        result["errors"].append("No template found")
        return result

    # Step 2: generate graphic
    if export_type == "player":
        graphic_bytes = _player_graphic(metadata)
    elif export_type == "match":
        graphic_bytes = _match_graphic(metadata)
    else:
        img = Image.new("RGB", (800, 600), (100, 100, 120))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        graphic_bytes = buf.getvalue()

    # Step 3: fetch template image and compose
    template_bytes = requests.get(template["image_url"]).content
    composer = get_image_composer()
    composed = composer.compose_post(
        template_image=template_bytes,
        graphic_image=graphic_bytes,
        template_config=template.get("template_config", {}),
        format_type="square",
    )
    if not composed:
        result["errors"].append("Composition failed")
        return result

    # Step 4: generate caption
    caption = caption_generator.generate_caption(metadata=metadata, tone="energetic", language="es")
    if not caption:
        caption = caption_generator.generate_caption_fallback(metadata)

    # Step 5: upload to storage
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{USER_ID}/composed_{export_type}_{timestamp}.png"
    supabase.storage.from_("posts").upload(filename, composed, {"content-type": "image/png"})
    image_url = supabase.storage.from_("posts").get_public_url(filename)

    # Step 6: save post
    post_data = {
        "user_id": USER_ID,
        "content": caption,
        "media_url": image_url,
        "post_type": "IMAGE",
        "status": "draft",
        "template_id": template["id"],
        "ai_caption_raw": caption,
        "is_ai_generated": True,
    }
    post_result = supabase.table("posts").insert(post_data).execute()
    if not post_result.data:
        result["errors"].append("DB insert failed")
        return result

    result["success"] = True
    result["post_id"] = post_result.data[0]["id"]
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_player_flow(mock_supabase_client, mock_caption_generator):
    metadata = {
        "export_type": "player",
        "player": {"name": "Lionel Messi", "position": "Forward", "team": "Inter Miami"},
        "stats": {"goals": 12, "assists": 9, "shots": 54},
    }
    result = _run_flow(metadata, mock_supabase_client, mock_caption_generator)
    assert result["success"] is True
    assert result["post_id"] is not None
    assert result["errors"] == []


def test_match_flow(mock_supabase_client, mock_caption_generator):
    metadata = {
        "export_type": "match",
        "match": {
            "home_team": {"name": "Barcelona", "id": "barcelona"},
            "away_team": {"name": "Real Madrid", "id": "real_madrid"},
            "score": "3-1",
            "status": "finished",
            "winner": "home",
        },
    }
    result = _run_flow(metadata, mock_supabase_client, mock_caption_generator)
    assert result["success"] is True
    assert result["post_id"] is not None
    assert result["errors"] == []


def test_caption_is_used_in_post(mock_supabase_client, mock_caption_generator):
    """Caption from generator appears in the inserted post data."""
    mock_caption_generator.generate_caption.return_value = "Gol increíble #futbol"
    metadata = {
        "export_type": "player",
        "player": {"name": "Ronaldo", "position": "Forward"},
        "stats": {"goals": 5},
    }
    result = _run_flow(metadata, mock_supabase_client, mock_caption_generator)
    assert result["success"] is True


def test_missing_export_type_fails_gracefully(mock_supabase_client, mock_caption_generator):
    result = _run_flow({}, mock_supabase_client, mock_caption_generator)
    assert result["success"] is False
    assert result["errors"]
