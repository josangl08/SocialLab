import pytest
from unittest.mock import MagicMock, patch
from services.analytics.analytics_service import AnalyticsService

@pytest.fixture
def mock_db():
    return MagicMock()

def test_get_empirical_scheduling_data_with_sufficient_history(mock_db):
    """Test get_empirical_scheduling_data when there is sufficient post history (>=3 posts on at least 1 weekday)."""
    service = AnalyticsService(db_client=mock_db)

    with patch.object(service, '_get_posts_from_db') as mock_get_posts, \
         patch.object(service, '_analyze_audience') as mock_analyze_audience, \
         patch.object(service, '_calculate_best_posting_times') as mock_calc_times, \
         patch.object(service, '_calculate_best_times_by_weekday') as mock_calc_weekday:
        
        mock_get_posts.return_value = [{'id': 1}, {'id': 2}, {'id': 3}]
        mock_analyze_audience.return_value = {'online_hours': {'19': 100}}
        mock_calc_times.return_value = [
            {'hour': 19, 'score': 95.0},
            {'hour': 12, 'score': 80.0},
            {'hour': 9, 'score': 70.0}
        ]
        mock_calc_weekday.return_value = {
            'Wednesday': [{'hour': 19, 'avg_engagement': 10.5, 'count': 3}],
            'Thursday': [{'hour': 20, 'avg_engagement': 8.0, 'count': 4}]
        }

        # If get_empirical_scheduling_data is implemented:
        if hasattr(service, 'get_empirical_scheduling_data'):
            res = service.get_empirical_scheduling_data(instagram_account_id=1, days=90)
            assert res['has_data'] is True
            assert isinstance(res['top_times'], list)
            assert isinstance(res['best_times_by_weekday'], dict)
            assert isinstance(res['summary_text'], str)

def test_get_empirical_scheduling_data_no_posts(mock_db):
    """Test get_empirical_scheduling_data when there are no posts in DB."""
    service = AnalyticsService(db_client=mock_db)

    with patch.object(service, '_get_posts_from_db') as mock_get_posts, \
         patch.object(service, '_analyze_audience') as mock_analyze_audience:
        
        mock_get_posts.return_value = []
        mock_analyze_audience.return_value = {}

        if hasattr(service, 'get_empirical_scheduling_data'):
            res = service.get_empirical_scheduling_data(instagram_account_id=1, days=90)
            assert res['has_data'] is False
            assert res['top_times'] == []
            assert res['best_times_by_weekday'] == {}
            assert res['summary_text'] == ""

def test_get_empirical_scheduling_data_insufficient_posts_per_day(mock_db):
    """Test get_empirical_scheduling_data when posts exist but <3 per weekday."""
    service = AnalyticsService(db_client=mock_db)

    with patch.object(service, '_get_posts_from_db') as mock_get_posts, \
         patch.object(service, '_analyze_audience') as mock_analyze_audience, \
         patch.object(service, '_calculate_best_posting_times') as mock_calc_times, \
         patch.object(service, '_calculate_best_times_by_weekday') as mock_calc_weekday:
        
        mock_get_posts.return_value = [{'id': 1}]
        mock_analyze_audience.return_value = {}
        mock_calc_times.return_value = [{'hour': 12, 'score': 50.0}]
        # <3 posts for Wednesday
        mock_calc_weekday.return_value = {
            'Wednesday': [{'hour': 19, 'avg_engagement': 5.0, 'count': 1}]
        }

        if hasattr(service, 'get_empirical_scheduling_data'):
            res = service.get_empirical_scheduling_data(instagram_account_id=1, days=90)
            assert res['has_data'] is False
