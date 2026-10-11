import json
import pytest
from unittest.mock import MagicMock, patch
from services.publisher.instagram_publisher import InstagramPublisher


@pytest.fixture
def publisher():
    with patch("services.publisher.instagram_publisher.get_supabase_admin_client"):
        pub = InstagramPublisher()
        return pub


@pytest.fixture
def mock_account():
    return {
        "access_token": "mock-token-xyz",
        "instagram_user_id": "17841400000000",
    }


def test_publish_reel_with_trial_graduation_manual(publisher, mock_account):
    """Reel con trial_graduation='MANUAL' incluye trial_params en el payload del contenedor."""
    with patch.object(publisher, "_get_instagram_account", return_value=mock_account), \
         patch.object(publisher, "verify_media_url_accessibility", return_value=True), \
         patch.object(publisher, "_wait_for_container"), \
         patch.object(publisher, "_publish_container", return_value="published-media-id-1"), \
         patch.object(publisher, "_get_media_info", return_value={"permalink": "https://instagram.com/reel/1"}), \
         patch("services.publisher.instagram_publisher.requests.post") as mock_post:

        mock_post.return_value.json.return_value = {"id": "container-123"}
        mock_post.return_value.raise_for_status = MagicMock()

        res = publisher.publish_post(
            media_url="https://example.com/video.mp4",
            caption="Test Trial Reel Manual",
            instagram_account_id=1,
            post_type="REELS",
            video_url="https://example.com/video.mp4",
            trial_graduation="MANUAL",
        )

        assert res["id"] == "published-media-id-1"
        assert res["media_type"] == "REELS"

        assert mock_post.called
        sent_payload = mock_post.call_args[1]["data"]
        assert sent_payload["media_type"] == "REELS"
        assert "trial_params" in sent_payload
        parsed_trial = json.loads(sent_payload["trial_params"])
        assert parsed_trial == {"graduation_strategy": "MANUAL"}


def test_publish_reel_with_trial_graduation_ss_performance(publisher, mock_account):
    """Reel con trial_graduation='SS_PERFORMANCE' incluye trial_params adecuado."""
    with patch.object(publisher, "_get_instagram_account", return_value=mock_account), \
         patch.object(publisher, "verify_media_url_accessibility", return_value=True), \
         patch.object(publisher, "_wait_for_container"), \
         patch.object(publisher, "_publish_container", return_value="published-media-id-2"), \
         patch.object(publisher, "_get_media_info", return_value={"permalink": "https://instagram.com/reel/2"}), \
         patch("services.publisher.instagram_publisher.requests.post") as mock_post:

        mock_post.return_value.json.return_value = {"id": "container-456"}
        mock_post.return_value.raise_for_status = MagicMock()

        publisher.publish_post(
            media_url="https://example.com/video.mp4",
            caption="Test Trial Reel SS",
            instagram_account_id=1,
            post_type="REELS",
            video_url="https://example.com/video.mp4",
            trial_graduation="SS_PERFORMANCE",
        )

        sent_payload = mock_post.call_args[1]["data"]
        assert "trial_params" in sent_payload
        parsed_trial = json.loads(sent_payload["trial_params"])
        assert parsed_trial == {"graduation_strategy": "SS_PERFORMANCE"}


def test_publish_reel_without_trial_graduation(publisher, mock_account):
    """Reel sin trial_graduation NO incluye trial_params en el payload."""
    with patch.object(publisher, "_get_instagram_account", return_value=mock_account), \
         patch.object(publisher, "verify_media_url_accessibility", return_value=True), \
         patch.object(publisher, "_wait_for_container"), \
         patch.object(publisher, "_publish_container", return_value="published-media-id-3"), \
         patch.object(publisher, "_get_media_info", return_value={"permalink": "https://instagram.com/reel/3"}), \
         patch("services.publisher.instagram_publisher.requests.post") as mock_post:

        mock_post.return_value.json.return_value = {"id": "container-789"}
        mock_post.return_value.raise_for_status = MagicMock()

        publisher.publish_post(
            media_url="https://example.com/video.mp4",
            caption="Test Normal Reel",
            instagram_account_id=1,
            post_type="REELS",
            video_url="https://example.com/video.mp4",
            trial_graduation=None,
        )

        sent_payload = mock_post.call_args[1]["data"]
        assert "trial_params" not in sent_payload


def test_publish_feed_post_ignores_trial_graduation(publisher, mock_account):
    """Post FEED ignora trial_graduation (trial_params solo permitido en REELS)."""
    with patch.object(publisher, "_get_instagram_account", return_value=mock_account), \
         patch.object(publisher, "verify_media_url_accessibility", return_value=True), \
         patch.object(publisher, "_wait_for_container"), \
         patch.object(publisher, "_publish_container", return_value="published-feed-id"), \
         patch.object(publisher, "_get_media_info", return_value={"permalink": "https://instagram.com/p/feed"}), \
         patch("services.publisher.instagram_publisher.requests.post") as mock_post:

        mock_post.return_value.json.return_value = {"id": "container-feed"}
        mock_post.return_value.raise_for_status = MagicMock()

        publisher.publish_post(
            media_url="https://example.com/image.jpg",
            caption="Test Feed Post",
            instagram_account_id=1,
            post_type="FEED",
            trial_graduation="MANUAL",
        )

        sent_payload = mock_post.call_args[1]["data"]
        assert "trial_params" not in sent_payload
        assert sent_payload["image_url"] == "https://example.com/image.jpg"


def test_publish_story_ignores_trial_graduation(publisher, mock_account):
    """Story ignora trial_graduation."""
    with patch.object(publisher, "_get_instagram_account", return_value=mock_account), \
         patch.object(publisher, "verify_media_url_accessibility", return_value=True), \
         patch.object(publisher, "_wait_for_container"), \
         patch.object(publisher, "_publish_container", return_value="published-story-id"), \
         patch("services.publisher.instagram_publisher.requests.post") as mock_post:

        mock_post.return_value.json.return_value = {"id": "container-story"}
        mock_post.return_value.raise_for_status = MagicMock()

        publisher.publish_post(
            media_url="https://example.com/story.jpg",
            caption="Test Story",
            instagram_account_id=1,
            post_type="STORY",
            trial_graduation="MANUAL",
        )

        sent_payload = mock_post.call_args[1]["data"]
        assert "trial_params" not in sent_payload


def test_publish_carousel_ignores_trial_graduation(publisher, mock_account):
    """Carrusel ignora trial_graduation."""
    with patch.object(publisher, "_get_instagram_account", return_value=mock_account), \
         patch.object(publisher, "verify_media_url_accessibility", return_value=True), \
         patch.object(publisher, "_wait_for_container"), \
         patch.object(publisher, "_publish_container", return_value="published-carousel-id"), \
         patch.object(publisher, "_get_media_info", return_value={"permalink": "https://instagram.com/p/carousel"}), \
         patch("services.publisher.instagram_publisher.time.sleep"), \
         patch("services.publisher.instagram_publisher.requests.post") as mock_post:

        mock_post.return_value.json.return_value = {"id": "container-item"}
        mock_post.return_value.raise_for_status = MagicMock()

        publisher.publish_post(
            media_url="https://example.com/c1.jpg",
            caption="Test Carousel",
            instagram_account_id=1,
            post_type="FEED",
            is_carousel=True,
            carousel_children=["https://example.com/c1.jpg", "https://example.com/c2.jpg"],
            trial_graduation="MANUAL",
        )

        for call_item in mock_post.call_args_list:
            data = call_item[1].get("data", {})
            assert "trial_params" not in data

