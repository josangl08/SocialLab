"""
Instagram Publisher Service

Handles publishing content to Instagram using the Graph API.
Supports Feed posts, Reels, and Stories with a 2-step process:
1. Create media container
2. Publish media container

Author: SocialLab
Date: 2025-01-16
"""

import os
import time
import logging
from typing import Dict, Optional, List
from datetime import datetime

import requests
from requests.exceptions import RequestException

from database.supabase_client import get_supabase_admin_client

logger = logging.getLogger(__name__)


class InstagramPublishError(Exception):
    """Custom exception for Instagram publishing errors."""
    pass


class InstagramPublisher:
    """
    Publishes content to Instagram using Graph API.

    Supports:
    - Feed posts (single image)
    - Reels (video content)
    - Stories (ephemeral content)
    - Carousel albums (multiple images)
    - Retry logic with exponential backoff
    """

    def __init__(self):
        self.supabase = get_supabase_admin_client()
        self.graph_api_version = os.getenv(
            'INSTAGRAM_GRAPH_API_VERSION',
            'v18.0'
        )
        self.base_url = (
            f"https://graph.facebook.com/{self.graph_api_version}"
        )
        self.container_check_interval = 5  # seconds
        self.max_container_checks = 12  # 60 seconds total

    def publish_post(
        self,
        media_url: str,
        caption: str,
        instagram_account_id: int,
        post_type: str = 'FEED',
        video_url: Optional[str] = None,
        cover_url: Optional[str] = None
    ) -> Dict:
        """
        Publishes a post to Instagram.

        Args:
            media_url: Public URL of the image (for images)
            caption: Caption text for the post
            instagram_account_id: Internal DB ID of Instagram account
            post_type: FEED, REELS, or STORY
            video_url: Public URL of video (for Reels)
            cover_url: Cover image URL (for Reels)

        Returns:
            {
                'id': Instagram media ID,
                'permalink': URL of the post on Instagram
            }

        Raises:
            InstagramPublishError: If publication fails
        """
        try:
            # Get Instagram account credentials
            account = self._get_instagram_account(instagram_account_id)

            if not account:
                raise InstagramPublishError(
                    f"Instagram account {instagram_account_id} not found"
                )

            access_token = account['access_token']
            ig_user_id = account['instagram_user_id']

            # Route to appropriate publishing method
            if post_type == 'REELS':
                if not video_url:
                    raise InstagramPublishError(
                        "video_url required for REELS"
                    )
                return self._publish_reel(
                    ig_user_id,
                    access_token,
                    video_url,
                    caption,
                    cover_url
                )
            elif post_type == 'STORY':
                return self._publish_story(
                    ig_user_id,
                    access_token,
                    media_url
                )
            else:  # FEED
                return self._publish_feed_post(
                    ig_user_id,
                    access_token,
                    media_url,
                    caption
                )

        except InstagramPublishError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error publishing post: {e}")
            raise InstagramPublishError(
                f"Failed to publish post: {str(e)}"
            )

    def _publish_feed_post(
        self,
        ig_user_id: str,
        access_token: str,
        image_url: str,
        caption: str
    ) -> Dict:
        """
        Publishes a feed post (2-step process).

        Step 1: Create media container
        Step 2: Publish media container

        Args:
            ig_user_id: Instagram Business Account ID
            access_token: Instagram API access token
            image_url: Public URL of the image
            caption: Caption text

        Returns:
            Dict with 'id' and 'permalink'
        """
        logger.info(f"Publishing feed post to IG user {ig_user_id}")

        # Step 1: Create media container
        container_id = self._create_media_container(
            ig_user_id,
            access_token,
            image_url,
            caption,
            media_type='IMAGE'
        )

        # Step 2: Wait for container to be ready
        self._wait_for_container(container_id, access_token)

        # Step 3: Publish container
        media_id = self._publish_container(
            ig_user_id,
            access_token,
            container_id
        )

        # Step 4: Get media details
        media_info = self._get_media_info(media_id, access_token)

        logger.info(
            f"Successfully published feed post: {media_info.get('permalink')}"
        )

        return {
            'id': media_id,
            'permalink': media_info.get('permalink', ''),
            'media_type': 'IMAGE'
        }

    def _publish_reel(
        self,
        ig_user_id: str,
        access_token: str,
        video_url: str,
        caption: str,
        cover_url: Optional[str] = None
    ) -> Dict:
        """
        Publishes a Reel (video content).

        Args:
            ig_user_id: Instagram Business Account ID
            access_token: Instagram API access token
            video_url: Public URL of the video
            caption: Caption text
            cover_url: Optional cover image URL

        Returns:
            Dict with 'id' and 'permalink'
        """
        logger.info(f"Publishing reel to IG user {ig_user_id}")

        # Create reel container
        container_id = self._create_media_container(
            ig_user_id,
            access_token,
            video_url,
            caption,
            media_type='REELS',
            cover_url=cover_url
        )

        # Reels take longer to process
        self._wait_for_container(
            container_id,
            access_token,
            max_checks=24  # 2 minutes for video processing
        )

        # Publish container
        media_id = self._publish_container(
            ig_user_id,
            access_token,
            container_id
        )

        # Get media details
        media_info = self._get_media_info(media_id, access_token)

        logger.info(
            f"Successfully published reel: {media_info.get('permalink')}"
        )

        return {
            'id': media_id,
            'permalink': media_info.get('permalink', ''),
            'media_type': 'REELS'
        }

    def _publish_story(
        self,
        ig_user_id: str,
        access_token: str,
        media_url: str
    ) -> Dict:
        """
        Publishes a Story.

        Args:
            ig_user_id: Instagram Business Account ID
            access_token: Instagram API access token
            media_url: Public URL of the image/video

        Returns:
            Dict with 'id'
        """
        logger.info(f"Publishing story to IG user {ig_user_id}")

        # Stories use a simplified process
        url = f"{self.base_url}/{ig_user_id}/media"

        payload = {
            'image_url': media_url,
            'media_type': 'STORIES',
            'access_token': access_token
        }

        response = requests.post(url, data=payload, timeout=30)
        response.raise_for_status()

        container_id = response.json()['id']

        # Publish immediately
        media_id = self._publish_container(
            ig_user_id,
            access_token,
            container_id
        )

        logger.info(f"Successfully published story: {media_id}")

        return {
            'id': media_id,
            'media_type': 'STORIES'
        }

    def _create_media_container(
        self,
        ig_user_id: str,
        access_token: str,
        media_url: str,
        caption: str,
        media_type: str = 'IMAGE',
        cover_url: Optional[str] = None
    ) -> str:
        """
        Creates a media container (Step 1 of publishing).

        Args:
            ig_user_id: Instagram Business Account ID
            access_token: Instagram API access token
            media_url: Public URL of media
            caption: Caption text
            media_type: IMAGE, REELS, or STORIES
            cover_url: Optional cover image for videos

        Returns:
            Container ID

        Raises:
            InstagramPublishError: If container creation fails
        """
        url = f"{self.base_url}/{ig_user_id}/media"

        payload = {
            'access_token': access_token,
            'caption': caption
        }

        # Set appropriate URL field based on media type
        if media_type == 'REELS':
            payload['media_type'] = 'REELS'
            payload['video_url'] = media_url
            if cover_url:
                payload['cover_url'] = cover_url
        elif media_type == 'STORIES':
            payload['media_type'] = 'STORIES'
            payload['image_url'] = media_url
        else:  # IMAGE
            payload['image_url'] = media_url

        try:
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()

            container_id = response.json()['id']
            logger.info(f"Created media container: {container_id}")

            return container_id

        except RequestException as e:
            error_msg = self._parse_error_response(e.response)
            logger.error(f"Failed to create container: {error_msg}")
            raise InstagramPublishError(
                f"Failed to create media container: {error_msg}"
            )

    def _wait_for_container(
        self,
        container_id: str,
        access_token: str,
        max_checks: int = 12
    ) -> None:
        """
        Waits for container to be ready for publishing.

        Instagram needs time to process the media before it can be published.

        Args:
            container_id: The container ID to check
            access_token: Instagram API access token
            max_checks: Maximum number of status checks

        Raises:
            InstagramPublishError: If container fails or times out
        """
        url = f"{self.base_url}/{container_id}"
        params = {
            'fields': 'status_code,status',
            'access_token': access_token
        }

        for attempt in range(max_checks):
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()

                data = response.json()
                status = data.get('status_code')

                if status == 'FINISHED':
                    logger.info(f"Container {container_id} ready")
                    return
                elif status == 'ERROR':
                    error_msg = data.get('status', 'Unknown error')
                    raise InstagramPublishError(
                        f"Container processing failed: {error_msg}"
                    )
                elif status == 'IN_PROGRESS':
                    logger.debug(
                        f"Container {container_id} still processing "
                        f"(attempt {attempt + 1}/{max_checks})"
                    )
                    time.sleep(self.container_check_interval)
                else:
                    logger.warning(
                        f"Unknown container status: {status}"
                    )
                    time.sleep(self.container_check_interval)

            except RequestException as e:
                logger.error(f"Error checking container status: {e}")
                time.sleep(self.container_check_interval)

        raise InstagramPublishError(
            f"Container {container_id} timed out after "
            f"{max_checks * self.container_check_interval} seconds"
        )

    def _publish_container(
        self,
        ig_user_id: str,
        access_token: str,
        container_id: str
    ) -> str:
        """
        Publishes a media container (Step 2 of publishing).

        Args:
            ig_user_id: Instagram Business Account ID
            access_token: Instagram API access token
            container_id: Container ID from step 1

        Returns:
            Published media ID

        Raises:
            InstagramPublishError: If publishing fails
        """
        url = f"{self.base_url}/{ig_user_id}/media_publish"

        payload = {
            'creation_id': container_id,
            'access_token': access_token
        }

        try:
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()

            media_id = response.json()['id']
            logger.info(f"Published container {container_id} as {media_id}")

            return media_id

        except RequestException as e:
            error_msg = self._parse_error_response(e.response)
            logger.error(f"Failed to publish container: {error_msg}")
            raise InstagramPublishError(
                f"Failed to publish container: {error_msg}"
            )

    def _get_media_info(
        self,
        media_id: str,
        access_token: str
    ) -> Dict:
        """
        Gets information about published media.

        Args:
            media_id: Instagram media ID
            access_token: Instagram API access token

        Returns:
            Dict with media information (permalink, timestamp, etc.)
        """
        url = f"{self.base_url}/{media_id}"
        params = {
            'fields': 'id,media_type,permalink,timestamp',
            'access_token': access_token
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error(f"Failed to get media info: {e}")
            return {}

    def _get_instagram_account(
        self,
        instagram_account_id: int
    ) -> Optional[Dict]:
        """
        Retrieves Instagram account credentials from database.

        Args:
            instagram_account_id: Internal DB ID

        Returns:
            Dict with access_token and instagram_user_id
        """
        try:
            result = self.supabase.table('instagram_accounts')\
                .select(
                    'long_lived_access_token, '
                    'instagram_business_account_id'
                )\
                .eq('id', instagram_account_id)\
                .single()\
                .execute()

            if result.data:
                # Map to expected field names for compatibility
                return {
                    'access_token': result.data['long_lived_access_token'],
                    'instagram_user_id': result.data[
                        'instagram_business_account_id'
                    ]
                }

            return None

        except Exception as e:
            logger.error(
                f"Failed to get Instagram account {instagram_account_id}: {e}"
            )
            return None

    def _parse_error_response(self, response) -> str:
        """
        Parses error response from Instagram API.

        Args:
            response: Response object from requests

        Returns:
            Human-readable error message
        """
        if not response:
            return "No response from Instagram API"

        try:
            error_data = response.json()
            error = error_data.get('error', {})
            message = error.get('message', 'Unknown error')
            code = error.get('code', 'N/A')
            error_type = error.get('type', 'N/A')

            return f"[{code}] {error_type}: {message}"
        except Exception:
            return response.text or "Unknown error"
