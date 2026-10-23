import time

import pytest

from utils.oauth_state import generate_state_token, verify_state_token
from tests.conftest import USER_ID


def test_generate_and_verify_round_trip():
    token = generate_state_token(USER_ID)
    payload = verify_state_token(token)
    assert payload["user_id"] == USER_ID
    assert payload["account_id"] is None
    assert payload["login_type"] == "instagram"


def test_generate_and_verify_round_trip_with_account_id():
    token = generate_state_token(USER_ID, account_id="7")
    payload = verify_state_token(token)
    assert payload["user_id"] == USER_ID
    assert payload["account_id"] == "7"


def test_verify_tampered_token_raises():
    token = generate_state_token(USER_ID)
    tampered = token[:-4] + ("A" if token[-4] != "A" else "B") + token[-3:]
    with pytest.raises(ValueError):
        verify_state_token(tampered)


def test_verify_expired_token_raises():
    token = generate_state_token(USER_ID)
    time.sleep(1)
    with pytest.raises(ValueError):
        verify_state_token(token, ttl=0)


def test_tokens_for_same_user_are_not_identical():
    token_a = generate_state_token(USER_ID)
    token_b = generate_state_token(USER_ID)
    assert token_a != token_b


def test_token_length_within_provider_limits():
    token = generate_state_token(USER_ID)
    assert len(token) < 512


def test_round_trip_with_facebook_login_type():
    payload = verify_state_token(generate_state_token(USER_ID, account_id="7", login_type="facebook"))
    assert payload["login_type"] == "facebook"
