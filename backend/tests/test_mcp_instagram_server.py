import pytest
import asyncio
from unittest.mock import MagicMock, patch
from mcp.instagram_server import mcp, instagram_publish_post, instagram_verify_media_url

def test_instagram_publish_post():
    with patch("mcp.instagram_server.InstagramPublisher") as mock_publisher_cls:
        mock_publisher = MagicMock()
        mock_publisher.publish_post.return_value = {"id": "12345", "permalink": "https://instagram.com/p/12345"}
        mock_publisher_cls.return_value = mock_publisher

        result = instagram_publish_post(
            media_url="https://example.com/image.jpg",
            caption="Amazing post!",
            instagram_account_id=99,
            post_type="FEED",
            video_url=None,
            cover_url=None,
            is_carousel=False,
            carousel_children=None
        )

        assert result == {"id": "12345", "permalink": "https://instagram.com/p/12345"}
        mock_publisher_cls.assert_called_once()
        mock_publisher.publish_post.assert_called_once_with(
            media_url="https://example.com/image.jpg",
            caption="Amazing post!",
            instagram_account_id=99,
            post_type="FEED",
            video_url=None,
            cover_url=None,
            is_carousel=False,
            carousel_children=None
        )

def test_instagram_verify_media_url():
    with patch("mcp.instagram_server.InstagramPublisher") as mock_publisher_cls:
        mock_publisher = MagicMock()
        mock_publisher.verify_media_url_accessibility.return_value = True
        mock_publisher_cls.return_value = mock_publisher

        result = instagram_verify_media_url(url="https://example.com/image.jpg", timeout=15)

        assert result is True
        mock_publisher_cls.assert_called_once()
        mock_publisher.verify_media_url_accessibility.assert_called_once_with(
            url="https://example.com/image.jpg",
            timeout=15
        )

@pytest.mark.asyncio
async def test_instagram_publish_post_via_mcp():
    with patch("mcp.instagram_server.InstagramPublisher") as mock_publisher_cls:
        mock_publisher = MagicMock()
        mock_publisher.publish_post.return_value = {"id": "123"}
        mock_publisher_cls.return_value = mock_publisher

        response = await mcp.call_tool("instagram_publish_post", {
            "media_url": "https://example.com/image.jpg",
            "caption": "Awesome",
            "instagram_account_id": 99
        })
        
        assert len(response) == 1
        assert response[0].type == "text"
        assert "123" in response[0].text
