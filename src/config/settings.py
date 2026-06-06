"""Runtime configuration and JSON data access."""

from dataclasses import dataclass
from dataclasses import field
from functools import lru_cache
import json
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE entries without overriding process variables."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            os.environ.setdefault(key, value)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


_load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    data_dir: Path = PROJECT_ROOT / "data"
    frontend_dist: Path = PROJECT_ROOT / "frontend" / "dist"
    default_city: str = "上海"
    default_district: str = "徐汇区"
    default_address: str = "上海徐汇区（Demo 默认位置）"
    default_lat: float = 31.1886
    default_lng: float = 121.4365
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    enable_llm: bool = field(
        default_factory=lambda: _env_bool("ENABLE_LLM", False)
    )
    deepseek_api_key: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", "").strip()
    )
    deepseek_base_url: str = field(
        default_factory=lambda: os.getenv(
            "DEEPSEEK_BASE_URL",
            "https://api.deepseek.com",
        ).rstrip("/")
    )
    deepseek_model: str = field(
        default_factory=lambda: os.getenv(
            "DEEPSEEK_MODEL",
            "deepseek-chat",
        )
    )
    llm_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    )
    enable_amap: bool = field(
        default_factory=lambda: _env_bool("ENABLE_AMAP", False)
    )
    amap_api_key: str = field(
        default_factory=lambda: os.getenv("AMAP_API_KEY", "").strip()
    )
    amap_base_url: str = field(
        default_factory=lambda: os.getenv(
            "AMAP_BASE_URL",
            "https://restapi.amap.com",
        ).rstrip("/")
    )
    amap_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("AMAP_TIMEOUT_SECONDS", "10"))
    )


settings = Settings()


@lru_cache(maxsize=None)
def load_json(filename: str) -> dict:
    """Load and cache a JSON file from the project data directory."""
    path = settings.data_dir / filename
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)
