import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from services.hermes.visual_backfill import backfill_visual_scores


@pytest.mark.asyncio
async def test_backfill_visual_scores_only_touches_rows_without_score():
    with patch("services.hermes.visual_backfill.get_supabase_admin_client") as mock_get_client,          patch("services.hermes.visual_backfill.get_drive_connector") as mock_get_drive,          patch("services.hermes.visual_backfill.analyze_image_vision", new_callable=AsyncMock) as mock_analyze:

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock instagram_accounts
        mock_client.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
            MagicMock(data=[{"user_id": "user123"}]),  # instagram_accounts
            MagicMock(data=[                           # visual_analyses
                {
                    "id": 1,
                    "drive_file_id": "file_with_score",
                    "gemini_description": {"theme": "sport", "aesthetic_score": 8},
                },
                {
                    "id": 2,
                    "drive_file_id": "file_without_score",
                    "gemini_description": {"theme": "travel", "objects": ["car"]},
                },
            ]),
        ]

        mock_drive = MagicMock()
        mock_drive.download_file_bytes.return_value = b"fake_bytes"
        mock_get_drive.return_value = mock_drive

        mock_analyze.return_value = {
            "aesthetic_score": 7,
            "composition_type": "paisaje",
            "content_type_fit": "feed_post",
            "suggested_hook": "Hook de viaje",
        }

        result = await backfill_visual_scores(account_id=1, batch_size=10)

        assert result["processed"] == 1
        assert result["updated"] == 1
        assert result["remaining_without_score"] == 0
        mock_drive.download_file_bytes.assert_called_once_with("file_without_score")


@pytest.mark.asyncio
async def test_backfill_visual_scores_merges_without_losing_existing_fields():
    with patch("services.hermes.visual_backfill.get_supabase_admin_client") as mock_get_client,          patch("services.hermes.visual_backfill.get_drive_connector") as mock_get_drive,          patch("services.hermes.visual_backfill.analyze_image_vision", new_callable=AsyncMock) as mock_analyze:

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
            MagicMock(data=[{"user_id": "user123"}]),
            MagicMock(data=[
                {
                    "id": 10,
                    "drive_file_id": "file_10",
                    "gemini_description": {
                        "theme": "running",
                        "objects": ["shoes", "road"],
                        "mood": "energetic",
                        "raw_description": "Runner on the road",
                    },
                },
            ]),
        ]

        mock_drive = MagicMock()
        mock_drive.download_file_bytes.return_value = b"bytes"
        mock_get_drive.return_value = mock_drive

        mock_analyze.return_value = {
            "aesthetic_score": 9,
            "composition_type": "accion",
            "content_type_fit": "feed_post",
            "suggested_hook": "Corre hoy",
        }

        result = await backfill_visual_scores(account_id=1, batch_size=10)

        assert result["updated"] == 1

        # Check what update was called with
        update_call = mock_client.table.return_value.update.call_args
        updated_desc = update_call[0][0]["gemini_description"]

        assert updated_desc["theme"] == "running"
        assert updated_desc["objects"] == ["shoes", "road"]
        assert updated_desc["mood"] == "energetic"
        assert updated_desc["raw_description"] == "Runner on the road"
        assert updated_desc["aesthetic_score"] == 9
        assert updated_desc["composition_type"] == "accion"
        assert updated_desc["content_type_fit"] == "feed_post"
        assert updated_desc["suggested_hook"] == "Corre hoy"


@pytest.mark.asyncio
async def test_backfill_visual_scores_respects_batch_size():
    with patch("services.hermes.visual_backfill.get_supabase_admin_client") as mock_get_client,          patch("services.hermes.visual_backfill.get_drive_connector") as mock_get_drive,          patch("services.hermes.visual_backfill.analyze_image_vision", new_callable=AsyncMock) as mock_analyze:

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        rows = [
            {"id": i, "drive_file_id": f"file_{i}", "gemini_description": {"theme": f"theme_{i}"}}
            for i in range(1, 6)
        ]

        mock_client.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
            MagicMock(data=[{"user_id": "user123"}]),
            MagicMock(data=rows),
        ]

        mock_drive = MagicMock()
        mock_drive.download_file_bytes.return_value = b"bytes"
        mock_get_drive.return_value = mock_drive

        mock_analyze.return_value = {
            "aesthetic_score": 7,
            "composition_type": "primer_plano",
            "content_type_fit": "feed_post",
            "suggested_hook": "Hook",
        }

        result = await backfill_visual_scores(account_id=1, batch_size=2)

        assert result["processed"] == 2
        assert result["updated"] == 2
        assert result["remaining_without_score"] == 3


@pytest.mark.asyncio
async def test_backfill_visual_scores_drive_failure_on_one_row_does_not_abort_rest():
    with patch("services.hermes.visual_backfill.get_supabase_admin_client") as mock_get_client,          patch("services.hermes.visual_backfill.get_drive_connector") as mock_get_drive,          patch("services.hermes.visual_backfill.analyze_image_vision", new_callable=AsyncMock) as mock_analyze:

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        rows = [
            {"id": 1, "drive_file_id": "file_error", "gemini_description": {"theme": "err"}},
            {"id": 2, "drive_file_id": "file_ok", "gemini_description": {"theme": "ok"}},
        ]

        mock_client.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
            MagicMock(data=[{"user_id": "user123"}]),
            MagicMock(data=rows),
        ]

        mock_drive = MagicMock()
        def download_mock(file_id):
            if file_id == "file_error":
                raise RuntimeError("Drive connection error")
            return b"ok_bytes"
        mock_drive.download_file_bytes.side_effect = download_mock
        mock_get_drive.return_value = mock_drive

        mock_analyze.return_value = {
            "aesthetic_score": 8,
            "composition_type": "detalle",
            "content_type_fit": "feed_post",
            "suggested_hook": "Hook",
        }

        result = await backfill_visual_scores(account_id=1, batch_size=10)

        assert result["processed"] == 2
        assert result["updated"] == 1
        assert result["remaining_without_score"] == 1
