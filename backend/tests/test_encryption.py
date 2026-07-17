# backend/tests/test_encryption.py

import os
from unittest.mock import patch
import pytest
from cryptography.fernet import Fernet

from utils.encryption import encrypt_token, decrypt_token


def test_encrypt_decrypt_roundtrip_with_explicit_key():
    """
    Verify that when TOKENS_ENCRYPTION_KEY is explicitly set to a valid Fernet key,
    encrypt_token and decrypt_token perform a successful round-trip.
    """
    key = Fernet.generate_key().decode("utf-8")
    env_mock = {
        "TOKENS_ENCRYPTION_KEY": key,
        "SUPABASE_KEY": "should-not-be-used",
    }
    
    with patch.dict(os.environ, env_mock):
        original_value = "super-secret-token-123"
        
        # Encrypt the token
        ciphertext = encrypt_token(original_value)
        assert ciphertext != original_value
        
        # Decrypt the token
        decrypted_value = decrypt_token(ciphertext)
        assert decrypted_value == original_value


def test_encrypt_decrypt_roundtrip_with_derived_key():
    """
    Verify that when TOKENS_ENCRYPTION_KEY is unset, the key is derived from
    SUPABASE_KEY deterministically, and performs a successful round-trip.
    """
    env_mock = {
        "SUPABASE_KEY": "some-arbitrary-supabase-key-value-12345",
    }
    if "TOKENS_ENCRYPTION_KEY" in os.environ:
        del os.environ["TOKENS_ENCRYPTION_KEY"]
        
    with patch.dict(os.environ, env_mock), patch.dict(os.environ, {}, clear=True):
        # We ensure TOKENS_ENCRYPTION_KEY is not in the environment
        if "TOKENS_ENCRYPTION_KEY" in os.environ:
            del os.environ["TOKENS_ENCRYPTION_KEY"]
            
        original_value = "another-secret-token-456"
        
        ciphertext = encrypt_token(original_value)
        assert ciphertext != original_value
        
        decrypted_value = decrypt_token(ciphertext)
        assert decrypted_value == original_value


def test_empty_or_none_inputs():
    """
    Verify that None or empty string inputs are returned unchanged by
    both encrypt_token and decrypt_token.
    """
    for val in [None, ""]:
        assert encrypt_token(val) == val
        assert decrypt_token(val) == val


def test_decrypt_legacy_plaintext_fallback():
    """
    Verify that passing legacy plain text (which is not valid Fernet ciphertext)
    to decrypt_token returns the input value unchanged.
    """
    legacy_token = "gho_legacyPlaintextTokenThatIsNotFernetCompatible123"
    
    # Regardless of the key in environment, legacy plaintext should fall back
    key = Fernet.generate_key().decode("utf-8")
    env_mock = {"TOKENS_ENCRYPTION_KEY": key}
    
    with patch.dict(os.environ, env_mock):
        decrypted = decrypt_token(legacy_token)
        assert decrypted == legacy_token


def test_decrypt_wrong_key_fallback():
    """
    Verify that if a token was encrypted with Key A, but decrypted when
    Key B is active, the decryption failure is handled and the ciphertext
    is returned unchanged.
    """
    key_a = Fernet.generate_key().decode("utf-8")
    key_b = Fernet.generate_key().decode("utf-8")
    
    original_value = "secret-token-key-rotation"
    
    # Encrypt with Key A
    with patch.dict(os.environ, {"TOKENS_ENCRYPTION_KEY": key_a}):
        ciphertext = encrypt_token(original_value)
        
    # Attempt to decrypt with Key B
    with patch.dict(os.environ, {"TOKENS_ENCRYPTION_KEY": key_b}):
        decrypted = decrypt_token(ciphertext)
        
        # Decryption should fail (InvalidToken) and return the ciphertext unchanged
        assert decrypted == ciphertext
