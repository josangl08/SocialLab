# ABOUTME: Unit tests for AI routes.
# Auth: Antigravity CLI

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from main import app
from auth.dependencies import get_current_user
from models.schemas import User
from tests.conftest import USER_ID

# Mock current user
async def mock_get_current_user():
    return User(id=USER_ID, email="test@example.com")

# Apply dependency override
app.dependency_overrides[get_current_user] = mock_get_current_user

client = TestClient(app)

@pytest.mark.asyncio
@patch("routes.ai_routes.tempfile.NamedTemporaryFile")
@patch("routes.ai_routes.analyze_image_vision", new_callable=AsyncMock)
async def test_analyze_image_no_tempfile(mock_analyze_image_vision, mock_tempfile):
    # Mock return value of analyze_image_vision
    expected_response = {
        "objects": ["cat"],
        "text_visible": "",
        "mood": "calm",
        "theme": "pets",
        "raw_description": "A sleeping cat.",
        "suggested_caption": "Cute cat!"
    }
    mock_analyze_image_vision.return_value = expected_response

    # Prepare fake file upload
    file_content = b"fake image content"
    files = {"file": ("cat.jpg", file_content, "image/jpeg")}

    # Call the endpoint
    response = client.post("/ai/analyze-image", files=files)

    # Assertions
    assert response.status_code == 200
    assert response.json() == expected_response

    # Verify tempfile.NamedTemporaryFile was NOT called
    mock_tempfile.assert_not_called()

    # Verify analyze_image_vision was called with the uploaded bytes and mime type
    mock_analyze_image_vision.assert_called_once_with(
        image_bytes=file_content,
        mime_type="image/jpeg"
    )
