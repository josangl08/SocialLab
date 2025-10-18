"""
Posts API Routes

Endpoints for managing and publishing posts to Instagram.
Handles manual publishing, status updates, and post metadata.

Author: SocialLab
Date: 2025-01-16
"""

from datetime import datetime
from typing import Optional
import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from auth.jwt_handler import get_current_user
from database.supabase_client import get_supabase_client
from services.publisher.instagram_publisher import (
    InstagramPublisher,
    InstagramPublishError
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/posts", tags=["posts"])


# Pydantic models
class PublishPostRequest(BaseModel):
    """Request model for manual post publishing."""
    post_type: Optional[str] = Field(
        default='FEED',
        description="Type of post: FEED, REELS, or STORY"
    )


class PublishPostResponse(BaseModel):
    """Response model for published post."""
    success: bool
    message: str
    instagram_post_id: Optional[str] = None
    permalink: Optional[str] = None
    published_at: Optional[datetime] = None


@router.post("/{post_id}/publish", response_model=PublishPostResponse)
async def publish_post_now(
    post_id: int,
    request: PublishPostRequest = PublishPostRequest(),
    current_user: dict = Depends(get_current_user)
):
    """
    Publish a post immediately to Instagram.

    This endpoint publishes a post directly to Instagram using
    the Instagram Graph API. The post must have a valid media_url
    that is publicly accessible.

    **Requirements:**
    - Post must exist in the database
    - Post must have a valid media_url
    - Post must belong to current user
    - Instagram account must be connected and active

    **Process:**
    1. Validates post exists and has media
    2. Verifies user owns the post
    3. Publishes to Instagram using InstagramPublisher
    4. Updates post status to 'published'
    5. Stores Instagram post ID and permalink

    **Args:**
    - post_id: ID of the post to publish
    - post_type: Type of Instagram content (FEED, REELS, STORY)

    **Returns:**
    - success: Whether publication succeeded
    - instagram_post_id: ID of the post on Instagram
    - permalink: URL to view the post on Instagram
    - published_at: Timestamp of publication

    **Example:**
    ```bash
    POST /api/posts/123/publish
    {
      "post_type": "FEED"
    }
    ```
    """
    try:
        logger.info(
            f"User {current_user['id']} attempting to publish post {post_id}"
        )

        supabase = get_supabase_client()

        # Get post data
        post_result = supabase.table('posts')\
            .select('*, instagram_accounts(long_lived_access_token, '
                    'instagram_business_account_id)')\
            .eq('id', post_id)\
            .single()\
            .execute()

        if not post_result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Post {post_id} not found"
            )

        post = post_result.data

        # Verify ownership
        if post['user_id'] != current_user['id']:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to publish this post"
            )

        # Validate post has media
        if not post.get('media_url'):
            raise HTTPException(
                status_code=400,
                detail="Post must have a media_url to be published"
            )

        # Validate post is not already published
        if post['status'] == 'published':
            raise HTTPException(
                status_code=400,
                detail="Post is already published"
            )

        # Get Instagram account ID
        instagram_account_id = post.get('instagram_account_id')
        if not instagram_account_id:
            raise HTTPException(
                status_code=400,
                detail="Post must be associated with an Instagram account"
            )

        # Initialize publisher
        publisher = InstagramPublisher()

        # Determine post type from request or post data
        post_type = request.post_type or post.get(
            'post_type',
            'FEED'
        )

        logger.info(
            f"Publishing post {post_id} as {post_type} "
            f"to Instagram account {instagram_account_id}"
        )

        # Publish to Instagram
        result = publisher.publish_post(
            media_url=post['media_url'],
            caption=post.get('caption', ''),
            instagram_account_id=instagram_account_id,
            post_type=post_type
        )

        logger.info(
            f"Successfully published post {post_id} "
            f"as Instagram post {result['id']}"
        )

        # Update post in database
        published_at = datetime.utcnow()
        update_data = {
            'status': 'published',
            'instagram_post_id': result['id'],
            'publication_date': published_at.isoformat(),
        }

        # Note: instagram_permalink column doesn't exist in schema
        # Permalink can be generated from instagram_post_id if needed

        supabase.table('posts')\
            .update(update_data)\
            .eq('id', post_id)\
            .execute()

        logger.info(f"Updated post {post_id} status to 'published'")

        return PublishPostResponse(
            success=True,
            message='Post published successfully to Instagram',
            instagram_post_id=result['id'],
            permalink=result.get('permalink'),
            published_at=published_at
        )

    except InstagramPublishError as e:
        logger.error(f"Instagram API error publishing post {post_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Instagram API error: {str(e)}"
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            f"Unexpected error publishing post {post_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to publish post: {str(e)}"
        )


@router.get("/{post_id}")
async def get_post(
    post_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get details of a specific post.

    **Args:**
    - post_id: ID of the post

    **Returns:**
    - Post data including status, media URL, caption, etc.
    """
    try:
        supabase = get_supabase_client()

        result = supabase.table('posts')\
            .select('*')\
            .eq('id', post_id)\
            .single()\
            .execute()

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Post {post_id} not found"
            )

        post = result.data

        # Verify ownership
        if post['user_id'] != current_user['id']:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to view this post"
            )

        return post

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error getting post {post_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get post: {str(e)}"
        )


@router.get("/")
async def list_posts(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """
    List posts for the current user.

    **Query Parameters:**
    - status: Filter by status (draft, scheduled, published)
    - limit: Max number of posts to return (default: 20)
    - offset: Offset for pagination (default: 0)

    **Returns:**
    - List of posts matching the criteria
    """
    try:
        supabase = get_supabase_client()

        query = supabase.table('posts')\
            .select('*')\
            .eq('user_id', current_user['id'])\
            .order('created_at', desc=True)\
            .range(offset, offset + limit - 1)

        if status:
            query = query.eq('status', status)

        result = query.execute()

        return {
            'posts': result.data,
            'count': len(result.data),
            'limit': limit,
            'offset': offset
        }

    except Exception as e:
        logger.error(f"Error listing posts: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list posts: {str(e)}"
        )
