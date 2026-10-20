from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from main import app


def test_lifespan_arranca_y_apaga_los_servicios() -> None:
    with patch("main.startup_event", new_callable=AsyncMock) as startup, \
         patch("main.shutdown_event", new_callable=AsyncMock) as shutdown:
        with TestClient(app):
            startup.assert_awaited_once()
            shutdown.assert_not_awaited()
        shutdown.assert_awaited_once()
