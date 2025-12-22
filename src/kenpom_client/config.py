from __future__ import annotations

from dataclasses import dataclass
import os


def _env_int(key: str, default: int) -> int:
    val = os.getenv(key)
    return default if val is None or val.strip() == "" else int(val)


def _env_float(key: str, default: float) -> float:
    val = os.getenv(key)
    return default if val is None or val.strip() == "" else float(val)


def _env_str(key: str, default: str) -> str:
    val = os.getenv(key)
    return default if val is None or val.strip() == "" else val


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str = "https://kenpom.com"
    timeout_seconds: float = 20.0
    max_retries: int = 5
    backoff_base_seconds: float = 0.6
    rate_limit_rps: float = 2.0
    cache_dir: str = ".cache/kenpom"
    cache_ttl_seconds: int = 21600
    out_dir: str = "data"

    @staticmethod
    def from_env() -> "Settings":
        api_key = os.getenv("KENPOM_API_KEY", "").strip()
        if not api_key:
            raise ValueError("Missing KENPOM_API_KEY in environment (.env)")

        return Settings(
            api_key=api_key,
            base_url=_env_str("KENPOM_BASE_URL", "https://kenpom.com"),
            timeout_seconds=_env_float("KENPOM_TIMEOUT_SECONDS", 20.0),
            max_retries=_env_int("KENPOM_MAX_RETRIES", 5),
            backoff_base_seconds=_env_float("KENPOM_BACKOFF_BASE_SECONDS", 0.6),
            rate_limit_rps=_env_float("KENPOM_RATE_LIMIT_RPS", 2.0),
            cache_dir=_env_str("KENPOM_CACHE_DIR", ".cache/kenpom"),
            cache_ttl_seconds=_env_int("KENPOM_CACHE_TTL_SECONDS", 21600),
            out_dir=_env_str("KENPOM_OUT_DIR", "data"),
        )
