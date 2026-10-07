from typing import Optional, List, Dict
from mcp.server.mcpserver import MCPServer
from services.publisher.instagram_publisher import InstagramPublisher

mcp = MCPServer("Instagram Publisher Server")

@mcp.tool()
def instagram_publish_post(
    media_url: str,
    caption: str,
    instagram_account_id: int,
    post_type: str = 'FEED',
    video_url: Optional[str] = None,
    cover_url: Optional[str] = None,
    is_carousel: bool = False,
    carousel_children: Optional[List[str]] = None
) -> Dict:
    """Publish a post (Feed, Reel, Story, or Carousel) to Instagram."""
    publisher = InstagramPublisher()
    return publisher.publish_post(
        media_url=media_url,
        caption=caption,
        instagram_account_id=instagram_account_id,
        post_type=post_type,
        video_url=video_url,
        cover_url=cover_url,
        is_carousel=is_carousel,
        carousel_children=carousel_children
    )

@mcp.tool()
def instagram_verify_media_url(url: str, timeout: int = 10) -> bool:
    """Verify that a media URL is publicly accessible for Instagram to ingest."""
    publisher = InstagramPublisher()
    return publisher.verify_media_url_accessibility(url=url, timeout=timeout)
