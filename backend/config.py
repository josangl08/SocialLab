import os
from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = ["SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"]

def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

SUPABASE_URL: str = _require("SUPABASE_URL")
SUPABASE_KEY: str = _require("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY: str = _require("SUPABASE_SERVICE_ROLE_KEY")

_OPTIONAL_DEFAULTS = {
    "GOOGLE_API_KEY": "",
    "INSTAGRAM_APP_ID": "",
    "INSTAGRAM_APP_SECRET": "",
    "INSTAGRAM_REDIRECT_URI": "",
    "TELEGRAM_BOT_TOKEN": "",
    "APP_BASE_URL": "http://localhost:8000",
    "APP_TIMEZONE": "Europe/Madrid",
    "GOOGLE_CLIENT_ID": "",
    "GOOGLE_CLIENT_SECRET": "",
    "GOOGLE_REDIRECT_URI": "",
    "FRONTEND_URL": "http://localhost:5173",
    "INSTAGRAM_GRAPH_API_VERSION": "v26.0",
}

def __getattr__(name: str) -> str:
    if name in _OPTIONAL_DEFAULTS:
        return os.environ.get(name, _OPTIONAL_DEFAULTS[name])
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
