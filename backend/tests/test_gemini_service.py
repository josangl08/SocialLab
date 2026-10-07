import pytest
from unittest.mock import patch, MagicMock
from google.genai import errors

from services.gemini_service import (
    clean_and_parse_json,
    generate_gemini_content,
    regenerate_slot_caption,
    analyze_image_vision,
)


def _quota_exhausted_error() -> errors.ClientError:
    return errors.ClientError(code=429, response_json={}, response=MagicMock())


@pytest.mark.asyncio
async def test_clean_and_parse_json():
    # Con fences json
    raw_with_fences = "```json\n{\"key\": \"value\"}\n```"
    result = await clean_and_parse_json(raw_with_fences)
    assert result == {"key": "value"}

    # Con fences simples
    raw_simple_fences = "```\n{\"key2\": \"value2\"}\n```"
    result2 = await clean_and_parse_json(raw_simple_fences)
    assert result2 == {"key2": "value2"}

    # Sin fences
    raw_no_fences = "{\"key3\": \"value3\"}"
    result3 = await clean_and_parse_json(raw_no_fences)
    assert result3 == {"key3": "value3"}

    # Invalid JSON
    with pytest.raises(Exception):
        await clean_and_parse_json("{invalid json")

@pytest.mark.asyncio
@patch("services.gemini_service.get_gemini_client")
async def test_generate_gemini_content_success(mock_get_client):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Generated content text"
    mock_client.models.generate_content.return_value = mock_response
    mock_get_client.return_value = mock_client

    result = await generate_gemini_content("Test prompt")
    assert result == "Generated content text"
    mock_client.models.generate_content.assert_any_call(model="gemini-pro-latest", contents="Test prompt")

@pytest.mark.asyncio
@patch("services.gemini_service.get_gemini_client")
async def test_generate_gemini_content_fallback_quota_exhausted(mock_get_client):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Flash model response"

    def generate_content_side_effect(model, contents):
        if model == "gemini-pro-latest":
            raise _quota_exhausted_error()
        return mock_response

    mock_client.models.generate_content.side_effect = generate_content_side_effect
    mock_get_client.return_value = mock_client

    result = await generate_gemini_content("Test prompt")
    assert result == "Flash model response"
    assert mock_client.models.generate_content.call_count == 2

@pytest.mark.asyncio
@patch("services.gemini_service.get_gemini_client")
async def test_generate_gemini_content_non_quota_error_raises_immediately(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = ValueError("something else broke")
    mock_get_client.return_value = mock_client

    with pytest.raises(ValueError):
        await generate_gemini_content("Test prompt")

    # Must not try the fallback model for a non-quota error
    assert mock_client.models.generate_content.call_count == 1

@pytest.mark.asyncio
@patch("services.gemini_service.generate_gemini_content")
async def test_regenerate_slot_caption_languages(mock_generate):
    # Test prompt in ES
    mock_generate.return_value = "Caption en español"
    result_es = await regenerate_slot_caption("tema", "contexto visual", "es")
    assert result_es == "Caption en español"
    args, _ = mock_generate.call_args
    assert "Genera un nuevo caption creativo" in args[0]

    # Test prompt in EN
    mock_generate.reset_mock()
    mock_generate.return_value = "Caption in English"
    result_en = await regenerate_slot_caption("theme", "visual context", "en")
    assert result_en == "Caption in English"
    args, _ = mock_generate.call_args
    assert "Generate a new creative Instagram caption" in args[0]

@pytest.mark.asyncio
@patch("services.gemini_service.get_gemini_client")
async def test_analyze_image_vision_success(mock_get_client):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"objects": ["logo"], "text_visible": "SocialLab", "mood": "professional", "theme": "marketing", "raw_description": "A nice logo.", "suggested_caption": "Check this out!"}'
    mock_client.models.generate_content.return_value = mock_response
    mock_get_client.return_value = mock_client

    image_bytes = b"fake_png_data"
    mime_type = "image/png"
    strategy = "brand colors, modern look"

    result = await analyze_image_vision(
        image_bytes=image_bytes,
        mime_type=mime_type,
        strategy_context=strategy
    )

    # Verify return dict
    assert result["mood"] == "professional"
    assert result["theme"] == "marketing"
    assert result["suggested_caption"] == "Check this out!"

    # Verify generate_content was called with the primary vision model (highest
    # free-tier RPD for this high-volume per-image call site) and the inline
    # image data + prompt containing the strategy
    assert mock_client.models.generate_content.called
    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-flash-lite-latest"

    contents = call_kwargs["contents"]
    assert isinstance(contents, list)
    assert len(contents) == 2

    image_part = contents[0]
    assert image_part.inline_data.data == image_bytes
    assert image_part.inline_data.mime_type == mime_type

    prompt = contents[1]
    assert "Analiza detalladamente" in prompt
    assert strategy in prompt


def test_visual_analysis_result_schema_defaults():
    from models.schemas import VisualAnalysisResult
    # Default instantiation
    res = VisualAnalysisResult()
    assert res.objects == []
    assert res.text_visible == ""
    assert res.mood == ""
    assert res.theme == ""
    assert res.raw_description == ""
    assert res.suggested_caption == ""
    assert res.aesthetic_score == 5
    assert res.composition_type == "primer_plano"
    assert res.content_type_fit == "feed_post"
    assert res.suggested_hook == ""


@pytest.mark.asyncio
@patch("services.gemini_service.get_gemini_client")
async def test_analyze_image_vision_parses_all_new_fields(mock_get_client):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '''{
        "objects": ["montaña", "zapatillas"],
        "text_visible": "Summit 2026",
        "mood": "inspiring",
        "theme": "trail running",
        "raw_description": "Corredor en la cima al amanecer.",
        "suggested_caption": "El esfuerzo siempre vale la pena.",
        "aesthetic_score": 9,
        "composition_type": "paisaje",
        "content_type_fit": "feed_post",
        "suggested_hook": "El 90% de los corredores nunca llegan a ver este amanecer."
    }'''
    mock_client.models.generate_content.return_value = mock_response
    mock_get_client.return_value = mock_client

    result = await analyze_image_vision(b"bytes", "image/jpeg")

    assert result["aesthetic_score"] == 9
    assert result["composition_type"] == "paisaje"
    assert result["content_type_fit"] == "feed_post"
    assert result["suggested_hook"] == "El 90% de los corredores nunca llegan a ver este amanecer."
    assert result["theme"] == "trail running"
    assert result["objects"] == ["montaña", "zapatillas"]


@pytest.mark.asyncio
@patch("services.gemini_service.get_gemini_client")
async def test_analyze_image_vision_tolerant_defaults_when_omitted(mock_get_client):
    mock_client = MagicMock()
    mock_response = MagicMock()
    # Omite los 4 campos nuevos y enums
    mock_response.text = '''{
        "objects": ["taza de café"],
        "text_visible": "",
        "mood": "calm",
        "theme": "cafe",
        "raw_description": "Una taza humeante.",
        "suggested_caption": "Buenos días."
    }'''
    mock_client.models.generate_content.return_value = mock_response
    mock_get_client.return_value = mock_client

    result = await analyze_image_vision(b"bytes", "image/jpeg")

    assert result["aesthetic_score"] == 5
    assert result["composition_type"] == "primer_plano"
    assert result["content_type_fit"] == "feed_post"
    assert result["suggested_hook"] == ""
    assert result["theme"] == "cafe"
