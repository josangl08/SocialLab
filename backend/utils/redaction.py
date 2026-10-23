"""
Oculta secretos que viajan en query strings (tokens de Meta, JWT de SocialLab, códigos OAuth)
antes de que lleguen a los logs o a las respuestas de error. requests incluye la URL completa
en sus excepciones, así que `str(e)` de una llamada a la Graph API lleva el access_token.
"""
import logging
import re

_SECRET_PARAMS = re.compile(
    r"(?<![\w])(access_token|input_token|fb_exchange_token|client_secret|token|code)=[^&\s'\"]+"
)


def redact_secrets(text: str) -> str:
    """'...?access_token=IGAA...&limit=5' → '...?access_token=***&limit=5'."""
    return _SECRET_PARAMS.sub(r"\1=***", text)


class RedactSecretsFilter(logging.Filter):
    """Redacta mensaje y argumentos sin aplanarlos (el formatter de acceso de uvicorn usa args)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact_secrets(a) if isinstance(a, str) else a for a in record.args)
        return True


def install_log_redaction() -> None:
    """Añade el filtro a los handlers raíz y de uvicorn (los logs de otros módulos propagan a raíz)."""
    redaction_filter = RedactSecretsFilter()
    for name in (None, "uvicorn", "uvicorn.access", "uvicorn.error"):
        for handler in logging.getLogger(name).handlers:
            handler.addFilter(redaction_filter)
