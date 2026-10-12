import asyncio
import base64
import json
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from auth import dependencies
from auth.dependencies import get_current_user, get_current_user_from_query_token

DEPENDENCIES = [get_current_user, get_current_user_from_query_token]


def _auth_response(user_id: str = "user-1"):
    user = SimpleNamespace(id=user_id, email="a@test.dev", created_at="2026-01-01T00:00:00+00:00")
    return SimpleNamespace(user=user)


@pytest.mark.parametrize("dependency", DEPENDENCIES)
def test_valid_token_returns_user(dependency):
    with patch("auth.dependencies.supabase.auth.get_user", return_value=_auth_response()) as get_user:
        user = asyncio.run(dependency("good-token"))

    assert str(user.id) == "user-1"
    get_user.assert_called_once_with("good-token")


@pytest.mark.parametrize("dependency", DEPENDENCIES)
def test_unknown_user_is_401(dependency):
    with patch("auth.dependencies.supabase.auth.get_user", return_value=SimpleNamespace(user=None)):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(dependency("token"))
    assert exc.value.status_code == 401


@pytest.mark.parametrize("dependency", DEPENDENCIES)
def test_supabase_error_is_401(dependency):
    with patch("auth.dependencies.supabase.auth.get_user", side_effect=Exception("expired")):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(dependency("token"))
    assert exc.value.status_code == 401


@pytest.mark.parametrize("dependency", DEPENDENCIES)
def test_token_validation_does_not_block_event_loop(dependency):
    """Cuatro validaciones de 0,3 s en paralelo tardan ~0,3 s, no 1,2 s."""
    def slow_get_user(token):
        time.sleep(0.3)
        return _auth_response()

    async def four():
        start = time.perf_counter()
        await asyncio.gather(*(dependency(f"t{i}") for i in range(4)))
        return time.perf_counter() - start

    with patch("auth.dependencies.supabase.auth.get_user", side_effect=slow_get_user):
        assert asyncio.run(four()) < 0.8


def _jwt(expires_in: float) -> str:
    claims = base64.urlsafe_b64encode(json.dumps({"exp": time.time() + expires_in}).encode()).decode().rstrip("=")
    return f"header.{claims}.signature"


@pytest.fixture
def empty_token_cache():
    dependencies._validated_tokens.clear()
    yield
    dependencies._validated_tokens.clear()


@pytest.mark.parametrize("dependency", DEPENDENCIES)
def test_validated_token_is_cached(empty_token_cache, dependency):
    token = _jwt(3600)
    with patch("auth.dependencies.supabase.auth.get_user", return_value=_auth_response()) as get_user:
        asyncio.run(dependency(token))
        user = asyncio.run(dependency(token))

    assert str(user.id) == "user-1"
    assert get_user.call_count == 1


def test_cache_expires_after_ttl(empty_token_cache, monkeypatch):
    token = _jwt(3600)
    with patch("auth.dependencies.supabase.auth.get_user", return_value=_auth_response()) as get_user:
        asyncio.run(get_current_user(token))
        later = time.monotonic() + 61
        monkeypatch.setattr(dependencies.time, "monotonic", lambda: later)
        asyncio.run(get_current_user(token))

    assert get_user.call_count == 2


def test_cache_never_outlives_the_jwt(empty_token_cache):
    token = _jwt(-5)  # ya caducado (Supabase lo habría rechazado; aquí solo se comprueba la caché)
    with patch("auth.dependencies.supabase.auth.get_user", return_value=_auth_response()) as get_user:
        asyncio.run(get_current_user(token))
        asyncio.run(get_current_user(token))

    assert get_user.call_count == 2


def test_invalid_token_is_not_cached(empty_token_cache):
    token = _jwt(3600)
    with patch("auth.dependencies.supabase.auth.get_user", return_value=SimpleNamespace(user=None)) as get_user:
        for _ in range(2):
            with pytest.raises(HTTPException):
                asyncio.run(get_current_user(token))

    assert get_user.call_count == 2
