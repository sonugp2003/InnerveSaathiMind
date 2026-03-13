import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _as_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "SaathiMind API"
    use_vertex_ai: bool = _as_bool("USE_VERTEX_AI", False)
    gcp_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    gcp_location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "asia-south1").strip()
    vertex_model: str = os.getenv("VERTEX_MODEL", "gemini-1.5-flash").strip()
    host: str = os.getenv("HOST", "127.0.0.1").strip()
    port: int = int(os.getenv("PORT", "8000"))
    max_history_messages: int = 6
