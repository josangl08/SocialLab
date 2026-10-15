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


def test_get_visual_performance_data_joins_posts_with_visual_analyses(mock_db):
    service = AnalyticsService(db_client=mock_db)

    posts_query = MagicMock()
    posts_query.select.return_value = posts_query
    posts_query.eq.return_value = posts_query
    posts_query.not_.is_.return_value = posts_query
    posts_query.gte.return_value = posts_query
    posts_query.execute.return_value = MagicMock(data=[
        {"drive_file_id": "file-1", "post_type": "post", "publication_date": "2026-01-01",
         "post_performance": {"likes": 10, "comments": 1, "saves": 2, "reach": 100, "impressions": 200, "total_interactions": 13}},
        {"drive_file_id": "file-2", "post_type": "reel", "publication_date": "2026-01-02",
         "post_performance": {"likes": 5, "comments": 0, "saves": 0, "reach": 50, "impressions": 80, "total_interactions": 5}},
        {"drive_file_id": "file-no-analysis", "post_type": "post", "publication_date": "2026-01-03",
         "post_performance": {"likes": 1, "comments": 0, "saves": 0, "reach": 10, "impressions": 20, "total_interactions": 1}},
    ])

    analyses_query = MagicMock()
    analyses_query.select.return_value = analyses_query
    analyses_query.in_.return_value = analyses_query
    analyses_query.execute.return_value = MagicMock(data=[
        {"drive_file_id": "file-1", "gemini_description": {"objects": ["playa"], "theme": "playa", "mood": "calm"}},
        {"drive_file_id": "file-2", "gemini_description": {"objects": ["ciudad"], "theme": "ciudad", "mood": "energetic"}},
    ])

    mock_db.table.side_effect = lambda name: {"posts": posts_query, "visual_analyses": analyses_query}[name]

    rows = service.get_visual_performance_data(instagram_account_id=7, days=180)

    # file-no-analysis has no visual_analyses row and must be skipped
    assert len(rows) == 2
    assert rows[0]["theme"] == "playa"
    assert rows[0]["total_interactions"] == 13
    assert rows[1]["theme"] == "ciudad"
    assert rows[1]["mood"] == "energetic"


def test_get_visual_performance_data_returns_empty_when_no_posts(mock_db):
    service = AnalyticsService(db_client=mock_db)

    posts_query = MagicMock()
    posts_query.select.return_value = posts_query
    posts_query.eq.return_value = posts_query
    posts_query.not_.is_.return_value = posts_query
    posts_query.gte.return_value = posts_query
    posts_query.execute.return_value = MagicMock(data=[])

    mock_db.table.return_value = posts_query

    rows = service.get_visual_performance_data(instagram_account_id=7)

    assert rows == []


# --- Tests Fase E: Métricas de Rendimiento, Mediana y Crecimiento ---

def test_sends_per_reach_normal():
    """Post con 40 compartidos y 2 000 de alcance -> 0.02 (2.0%)."""
    result = AnalyticsService.calculate_sends_per_reach(shares=40, reach=2000)
    assert result == 0.02


def test_sends_per_reach_division_by_zero():
    """Post con alcance 0 o desconocido -> None (sin ZeroDivisionError)."""
    assert AnalyticsService.calculate_sends_per_reach(shares=40, reach=0) is None
    assert AnalyticsService.calculate_sends_per_reach(shares=40, reach=None) is None
    assert AnalyticsService.calculate_sends_per_reach(shares=0, reach=0) is None


def test_calculate_median_views():
    """Mediana de los posts con vistas; < 5 posts con vistas -> None."""
    assert AnalyticsService.calculate_median_views([100, 200, 300, 400, 500]) == 300.0
    assert AnalyticsService.calculate_median_views([100, 200, 300, 400, 500, 600]) == 350.0
    assert AnalyticsService.calculate_median_views([100, 200, 300, 400]) is None
    # Los posts sin vistas no cuentan para el mínimo de 5
    assert AnalyticsService.calculate_median_views([0, 0, 100, 200, 300, 400]) is None
    assert AnalyticsService.calculate_median_views([]) is None


def test_outlier_multiple_calculation():
    """Post viral con 5 200 vistas y mediana 1 000 -> 5.2x."""
    assert AnalyticsService.calculate_outlier_multiple(views=5200, median_views=1000.0) == 5.2


def test_outlier_multiple_without_median():
    """Sin mediana (datos insuficientes) o mediana 0 -> None, sin ZeroDivisionError."""
    assert AnalyticsService.calculate_outlier_multiple(views=5200, median_views=None) is None
    assert AnalyticsService.calculate_outlier_multiple(views=5200, median_views=0.0) is None


def test_growth_series_daily_calculation():
    """Semana con 120 altas y 30 bajas -> neto +90 (AD-9)."""
    daily_raw = [
        {"date": "2026-05-01", "follows": 70, "unfollows": 10},
        {"date": "2026-05-02", "follows": 50, "unfollows": 20},
    ]
    series = AnalyticsService.calculate_growth_series(daily_raw)
    assert series[0] == {"date": "2026-05-01", "follows": 70, "unfollows": 10, "net": 60}
    assert series[1] == {"date": "2026-05-02", "follows": 50, "unfollows": 20, "net": 30}
    assert sum(d["net"] for d in series) == 90


def test_follower_growth_from_snapshots(mock_db):
    """La serie y los toques de contacto salen de instagram_account_snapshots."""
    mock_db.table.return_value.select.return_value.eq.return_value.gte.return_value \
        .order.return_value.execute.return_value.data = [
            {"date": "2026-05-01", "follows": 70, "unfollows": 10, "profile_links_taps": 3},
            {"date": "2026-05-02", "follows": 50, "unfollows": 20, "profile_links_taps": None},
        ]
    service = AnalyticsService(db_client=mock_db)
    result = service._get_follower_growth(instagram_account_id=1, days=7)

    mock_db.table.assert_called_with('instagram_account_snapshots')
    growth = result['follower_growth']
    assert (growth['follows'], growth['unfollows'], growth['net']) == (120, 30, 90)
    assert len(growth['series']) == 2
    assert result['contact_button_taps'] == 3


def test_overview_includes_fase_e_metrics(mock_db):
    """Overview: median_views (la de 90 días que recibe) y Sends per Reach medio sin posts sin alcance."""
    service = AnalyticsService(db_client=mock_db)
    account_info = {'id': 1, 'follower_count': 1000, 'reach': 5000}
    posts = [
        {'post_performance': {'impressions': 100, 'reach': 1000, 'shares': 20}},
        {'post_performance': {'impressions': 200, 'reach': 1000, 'shares': 40}},
        {'post_performance': {'impressions': 300, 'reach': 0, 'shares': 50}},
        {'post_performance': None},
    ]
    overview = service._calculate_overview(posts, account_info, median_views=250.0)

    assert overview['median_views'] == 250.0
    assert overview['avg_sends_per_reach'] == 0.03  # media de 0.02 y 0.04; reach 0 no cuenta


def test_overview_sends_per_reach_none_without_reach(mock_db):
    service = AnalyticsService(db_client=mock_db)
    posts = [{'post_performance': {'impressions': 100, 'reach': 0, 'shares': 5}}]
    overview = service._calculate_overview(posts, {'id': 1, 'follower_count': 10})
    assert overview['avg_sends_per_reach'] is None
    assert overview['median_views'] is None


def test_recent_posts_includes_shares_sends_and_outlier(mock_db):
    """Recent posts incluye shares, sends_per_reach y outlier_multiple con la mediana recibida."""
    service = AnalyticsService(db_client=mock_db)
    posts = [
        {'instagram_post_id': 'p1', 'publication_date': '2026-05-05', 'post_performance': {'impressions': 600, 'reach': 2000, 'shares': 40}},
        {'instagram_post_id': 'p2', 'publication_date': '2026-05-04', 'post_performance': {'impressions': 200, 'reach': 0, 'shares': 10}},
    ]
    recent = service._get_recent_posts(posts, limit=5, median_views=400.0)
    p1 = next(p for p in recent if p['id'] == 'p1')
    p2 = next(p for p in recent if p['id'] == 'p2')
    assert p1['shares'] == 40
    assert p1['sends_per_reach'] == 0.02
    assert p1['outlier_multiple'] == 1.5
    assert p2['sends_per_reach'] is None

    no_median = service._get_recent_posts(posts, limit=5)
    assert all(p['outlier_multiple'] is None for p in no_median)


def test_top_posts_sorted_by_outlier(mock_db):
    """sort_by='outlier' ordena por Outlier Multiple; sin dato van al final."""
    service = AnalyticsService(db_client=mock_db)
    posts = [
        {'instagram_post_id': 'a', 'post_performance': {'likes': 100, 'impressions': 100}},
        {'instagram_post_id': 'b', 'post_performance': {'likes': 1, 'impressions': 900}},
        {'instagram_post_id': 'c', 'post_performance': {'likes': 50, 'impressions': 300}},
    ]
    by_outlier = service._get_top_posts(posts, limit=3, median_views=300.0, sort_by='outlier')
    assert [p['id'] for p in by_outlier] == ['b', 'c', 'a']
    assert by_outlier[0]['outlier_multiple'] == 3.0
    by_engagement = service._get_top_posts(posts, limit=3, median_views=300.0)
    assert by_engagement[0]['id'] == 'a'


def _swipe_db(mock_db, rows):
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value \
        .eq.return_value.gte.return_value.execute.return_value.data = rows
    return AnalyticsService(db_client=mock_db)


def test_swipe_file_sorted_by_outlier_with_formula_summary(mock_db):
    rows = [
        {'id': i, 'content': f'Gancho {i}\nCuerpo', 'trial_graduation': None,
         'post_performance': {'impressions': v, 'reach': 1000, 'shares': 20}}
        for i, v in enumerate([100, 200, 300, 400, 1500], start=1)
    ]
    rows[4]['trial_graduation'] = 'MANUAL'
    rows[4]['post_performance']['reels_skip_rate'] = 41.5
    service = _swipe_db(mock_db, rows)

    with patch('services.analytics.analytics_service.score_hook',
               return_value={'formula_id': 3, 'formula_name': 'Pérdida cuantificada'}):
        result = service.get_swipe_file(1)

    items = result['items']
    assert items[0]['post_id'] == 5
    assert items[0]['hook_text'] == 'Gancho 5'
    assert items[0]['outlier_multiple'] == 5.0  # mediana 300
    assert items[0]['sends_per_reach'] == 0.02
    assert items[0]['is_trial'] is True
    assert items[0]['reels_skip_rate'] == 41.5
    assert result['by_formula'] == [{
        'formula_id': 3, 'formula_name': 'Pérdida cuantificada', 'count': 5,
        'avg_outlier': round((1/3 + 2/3 + 1 + 4/3 + 5) / 5, 2),
    }]


def test_swipe_file_insufficient_data(mock_db):
    """< 5 posts con vistas -> outlier None; sin texto -> el post no entra."""
    rows = [
        {'id': 1, 'content': 'Solo un gancho', 'post_performance': {'impressions': 100, 'reach': 0}},
        {'id': 2, 'content': '', 'post_performance': {'impressions': 100}},
    ]
    service = _swipe_db(mock_db, rows)
    result = service.get_swipe_file(1)
    assert len(result['items']) == 1
    assert result['items'][0]['outlier_multiple'] is None
    assert result['items'][0]['sends_per_reach'] is None


def _post(pub_date: str, likes: int = 10) -> dict:
    return {'publication_date': pub_date, 'post_performance': {'likes': likes, 'comments': 0, 'reach': 100}}


def test_best_times_by_weekday_uses_account_timezone(mock_db):
    # 12:00 UTC del miércoles 14-oct es 20:00 del miércoles en Asia/Kuching (AD-14)
    service = AnalyticsService(db_client=mock_db)
    posts = [_post('2026-10-14T12:00:00Z'), _post('2026-10-07T12:00:00Z'), _post('2026-09-30T12:00:00Z')]

    result = service._calculate_best_times_by_weekday(posts, 'Asia/Kuching')

    assert result[2][0]['hour'] == '20:00'


def test_trends_group_days_in_account_timezone(mock_db):
    # 18:00 UTC del 14-oct ya es el 15 en Kuching: la tendencia lo cuenta el día 15
    service = AnalyticsService(db_client=mock_db)

    trend = service._calculate_trends([_post('2026-10-14T18:00:00Z')], 365, 'Asia/Kuching')

    days_with_posts = [d['date'] for d in trend if d['posts_count']]
    assert days_with_posts == ['2026-10-15']


def test_empirical_scheduling_data_reports_account_timezone(mock_db):
    service = AnalyticsService(db_client=mock_db)
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{'primary_timezone': 'Asia/Kuching', 'detected_timezone': None}]
    )
    with patch.object(service, '_get_posts_from_db', return_value=[]):
        result = service.get_empirical_scheduling_data(7)

    assert result['timezone'] == 'Asia/Kuching'
    assert result['has_data'] is False


@pytest.mark.parametrize("run", [
    lambda s: s._get_posts_from_db(instagram_account_id=1, days=30),
    lambda s: s._get_median_views_90d(1),
    lambda s: s.get_swipe_file(1),
])
def test_collaborations_are_excluded_from_analytics(mock_db, run):
    """Las publicaciones en colaboración son de otros autores: no cuentan como propias (AD-10)."""
    service = AnalyticsService(db_client=mock_db)

    run(service)

    assert "eq('is_collaboration', False)" in str(mock_db.mock_calls)
