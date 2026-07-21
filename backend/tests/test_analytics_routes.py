import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app
from auth.dependencies import get_current_user
from models.schemas import User
from tests.conftest import USER_ID

# Mock current user
async def mock_get_current_user():
    return User(id=USER_ID, email="test@example.com")

# Apply dependency override
app.dependency_overrides[get_current_user] = mock_get_current_user

# Mock instagram service dependency
async def mock_get_instagram_service():
    return MagicMock()

from routes.analytics_routes import get_instagram_service
app.dependency_overrides[get_instagram_service] = mock_get_instagram_service

client = TestClient(app)

def test_get_analytics_overview_success():
    mock_payload = {
        'success': True,
        'source': 'cache',
        'last_sync_at': '2026-06-27T12:00:00',
        'data': {
            'overview': {
                'total_posts': 5,
                'follower_count': 100,
                'profile_views': 50,
                'reach': 200,
                'views': 400,
                'total_likes': 10,
                'total_comments': 15,
                'total_saves': 5,
                'avg_interactions_per_post': 6.0,
                'engagement_rate': 6.0,
                'total_interactions': 30
            },
            'top_posts': [
                {
                    'id': 'post-1',
                    'post_type': 'reel',
                    'caption': 'Cool video',
                    'media_url': 'http://example.com/video.mp4',
                    'likes': 10,
                    'comments': 15,
                    'avg_watch_time_ms': 12000,
                    'total_watch_time_ms': 60000
                }
            ],
            'audience': {
                'follower_demographics': {'genders': {'F': 60, 'M': 40}},
                'engaged_demographics': {'genders': {'F': 70, 'M': 30}}
            }
        }
    }

    with patch("routes.analytics_routes.AnalyticsService") as mock_service_cls:
        mock_service = mock_service_cls.return_value
        mock_service.get_comprehensive_analytics.return_value = mock_payload
        
        response = client.get("/api/analytics/overview")
        
    assert response.status_code == 200
    res_data = response.json()
    assert res_data['success'] is True
    
    overview = res_data['data']['overview']
    assert overview['total_comments'] == 15
    assert overview['total_comments'] != 0
    assert 'views' in overview
    assert 'reach' in overview
    assert overview['views'] == 400
    assert overview['reach'] == 200
    
    top_posts = res_data['data']['top_posts']
    assert len(top_posts) == 1
    assert top_posts[0]['post_type'] == 'reel'
    assert 'avg_watch_time_ms' in top_posts[0]
    assert 'total_watch_time_ms' in top_posts[0]
    assert top_posts[0]['avg_watch_time_ms'] == 12000
    assert top_posts[0]['total_watch_time_ms'] == 60000
    
    audience = res_data['data']['audience']
    assert 'engaged_demographics' in audience
    assert audience['engaged_demographics'] == {'genders': {'F': 70, 'M': 30}}
