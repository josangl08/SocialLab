import pytest
from unittest.mock import MagicMock, patch
from mcp.analytics_server import mcp, analytics_get_empirical_scheduling_data, analytics_get_visual_performance_data


def test_analytics_get_empirical_scheduling_data_with_history():
    with patch("mcp.analytics_server.get_supabase_admin_client") as mock_get_client, \
         patch("mcp.analytics_server.AnalyticsService") as mock_service_class:
        mock_get_client.return_value = MagicMock()

        mock_service = MagicMock()
        mock_service.get_empirical_scheduling_data.return_value = {
            "has_data": True,
            "top_times": ["09:00", "18:00", "20:00"],
            "best_times_by_weekday": {0: "09:00", 2: "18:00"},
            "summary_text": "Lun 09:00, Miér 18:00 — basado en tu histórico real"
        }
        mock_service_class.return_value = mock_service

        result = analytics_get_empirical_scheduling_data(account_id=123, days=90)

        assert result["has_data"] is True
        assert result["best_times_by_weekday"] == {0: "09:00", 2: "18:00"}
        mock_service_class.assert_called_once_with(db_client=mock_get_client.return_value)
        mock_service.get_empirical_scheduling_data.assert_called_once_with(123, 90)


def test_analytics_get_empirical_scheduling_data_no_history():
    with patch("mcp.analytics_server.get_supabase_admin_client") as mock_get_client, \
         patch("mcp.analytics_server.AnalyticsService") as mock_service_class:
        mock_get_client.return_value = MagicMock()

        mock_service = MagicMock()
        mock_service.get_empirical_scheduling_data.return_value = {
            "has_data": False,
            "top_times": [],
            "best_times_by_weekday": {},
            "summary_text": ""
        }
        mock_service_class.return_value = mock_service

        result = analytics_get_empirical_scheduling_data(account_id=123)

        assert result["has_data"] is False
        assert result["best_times_by_weekday"] == {}
        mock_service.get_empirical_scheduling_data.assert_called_once_with(123, 90)


@pytest.mark.asyncio
async def test_analytics_get_empirical_scheduling_data_via_mcp():
    with patch("mcp.analytics_server.get_supabase_admin_client") as mock_get_client, \
         patch("mcp.analytics_server.AnalyticsService") as mock_service_class:
        mock_get_client.return_value = MagicMock()

        mock_service = MagicMock()
        mock_service.get_empirical_scheduling_data.return_value = {
            "has_data": True,
            "top_times": ["09:00"],
            "best_times_by_weekday": {0: "09:00"},
            "summary_text": "Lun 09:00 — basado en tu histórico real"
        }
        mock_service_class.return_value = mock_service

        response = await mcp.call_tool("analytics_get_empirical_scheduling_data", {"account_id": 123})

        assert len(response) == 1
        assert response[0].type == "text"
        assert "has_data" in response[0].text


def test_analytics_get_visual_performance_data_returns_raw_rows():
    with patch("mcp.analytics_server.get_supabase_admin_client") as mock_get_client, \
         patch("mcp.analytics_server.AnalyticsService") as mock_service_class:
        mock_get_client.return_value = MagicMock()

        mock_service = MagicMock()
        mock_service.get_visual_performance_data.return_value = [
            {"theme": "playa", "total_interactions": 100},
            {"theme": "ciudad", "total_interactions": 50},
        ]
        mock_service_class.return_value = mock_service

        result = analytics_get_visual_performance_data(account_id=7, days=90)

        assert len(result) == 2
        mock_service_class.assert_called_once_with(db_client=mock_get_client.return_value)
        mock_service.get_visual_performance_data.assert_called_once_with(7, 90)
