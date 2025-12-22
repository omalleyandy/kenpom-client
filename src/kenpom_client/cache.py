from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class CacheEntry:
    created_ts: float
    payload: Any


class FileCache:
    """
    Simple deterministic on-disk cache:
      key -> sha256 -> json file
    """

    def __init__(self, cache_dir: str, ttl_seconds: int) -> None:
        self.root = Path(cache_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_seconds

    def _path_for_key(self, key: str) -> Path:
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / f"{h}.json"

    def get(self, key: str) -> Optional[Any]:
        path = self._path_for_key(key)
        if not path.exists():
            return None
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            created_ts = float(obj["created_ts"])
            if (time.time() - created_ts) > self.ttl:
                return None
            return obj["payload"]
        except Exception:
            # corrupt cache file: ignore
            return None

    def set(self, key: str, payload: Any) -> None:
        path = self._path_for_key(key)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"created_ts": time.time(), "payload": payload}, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, path)
