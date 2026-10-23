"""Los secretos de query strings no llegan a logs ni a respuestas de error."""
import logging

from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from utils.redaction import RedactSecretsFilter, redact_secrets

URL = "https://graph.instagram.com/v26.0/1/media?fields=id&access_token=IGAAsecret&limit=5"


def test_redact_secrets_hides_tokens_and_codes():
    assert redact_secrets(URL) == "https://graph.instagram.com/v26.0/1/media?fields=id&access_token=***&limit=5"
    assert redact_secrets("GET /instagram/login?token=eyJjwt&account_id=7") == "GET /instagram/login?token=***&account_id=7"
    assert redact_secrets("/callback/instagram?code=AQabc&state=s") == "/callback/instagram?code=***&state=s"
    assert redact_secrets("client_secret=abc input_token=def fb_exchange_token=ghi") == \
        "client_secret=*** input_token=*** fb_exchange_token=***"


def test_redact_secrets_keeps_similar_names():
    assert redact_secrets("status_code=400 error_code=190") == "status_code=400 error_code=190"


def test_filter_redacts_message_and_args_without_flattening():
    record = logging.LogRecord("x", logging.ERROR, __file__, 1, "Error: %s %s", (URL, 400), None)
    RedactSecretsFilter().filter(record)
    assert record.args == (URL.replace("IGAAsecret", "***"), 400)
    assert "IGAAsecret" not in record.getMessage()


def test_http_exception_detail_is_redacted():
    @app.get("/__test_redaction")
    def boom():
        raise HTTPException(status_code=500, detail=f"Error al obtener datos de Instagram: 400 for url: {URL}")

    response = TestClient(app).get("/__test_redaction")
    assert response.status_code == 500
    assert "IGAAsecret" not in response.json()["detail"]
    assert "access_token=***" in response.json()["detail"]
