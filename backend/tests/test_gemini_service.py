import pytest
from unittest.mock import patch, MagicMock
from google.api_core.exceptions import ResourceExhausted

from services.gemini_service import (
    clean_and_parse_json,
    generate_gemini_content,
    regenerate_slot_caption,
    analyze_image_vision,
)

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
@patch("google.generativeai.GenerativeModel")
@patch("services.gemini_service._configure_genai")
async def test_generate_gemini_content_success(mock_configure, mock_gen_model):
    mock_model_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Generated content text"
    mock_model_instance.generate_content.return_value = mock_response
    mock_gen_model.return_value = mock_model_instance

    result = await generate_gemini_content("Test prompt")
    assert result == "Generated content text"
    mock_gen_model.assert_any_call("gemini-2.5-pro")

@pytest.mark.asyncio
@patch("google.generativeai.GenerativeModel")
@patch("services.gemini_service._configure_genai")
async def test_generate_gemini_content_fallback_resource_exhausted(mock_configure, mock_gen_model):
    mock_model_pro = MagicMock()
    mock_model_pro.generate_content.side_effect = ResourceExhausted("Resource Exhausted Details")

    mock_model_flash = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Flash model response"
    mock_model_flash.generate_content.return_value = mock_response

    def get_mock_model(model_name):
        if model_name == "gemini-2.5-pro":
            return mock_model_pro
        return mock_model_flash

    mock_gen_model.side_effect = get_mock_model

    result = await generate_gemini_content("Test prompt")
    assert result == "Flash model response"
    mock_model_pro.generate_content.assert_called_once()
    mock_model_flash.generate_content.assert_called_once()

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
@patch("google.generativeai.GenerativeModel")
@patch("google.generativeai.upload_file")
@patch("services.gemini_service._configure_genai")
async def test_analyze_image_vision_success(mock_configure, mock_upload_file, mock_gen_model):
    mock_model_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"objects": ["logo"], "text_visible": "SocialLab", "mood": "professional", "theme": "marketing", "raw_description": "A nice logo.", "suggested_caption": "Check this out!"}'
    mock_model_instance.generate_content.return_value = mock_response
    mock_gen_model.return_value = mock_model_instance

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

    # Verify upload_file was NOT called
    mock_upload_file.assert_not_called()

    # Verify GenerativeModel was instantiated with gemini-2.5-flash
    mock_gen_model.assert_called_once_with("gemini-2.5-flash")

    # Verify generate_content was called with the inline data and the prompt containing the strategy
    assert mock_model_instance.generate_content.called
    call_args = mock_model_instance.generate_content.call_args[0][0]
    
    assert isinstance(call_args, list)
    assert len(call_args) == 2
    
    inline_data = call_args[0]
    assert inline_data == {"mime_type": mime_type, "data": image_bytes}
    
    prompt = call_args[1]
    assert "Analiza detalladamente" in prompt
    assert strategy in prompt

