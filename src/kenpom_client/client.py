from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from .cache import FileCache
from .config import Settings
from .http import RateLimiter, request_json
from .models import (
    ArchiveRating,
    Conference,
    FanmatchGame,
    FourFactors,
    Height,
    MiscStats,
    PointDistribution,
    Rating,
    Team,
)

log = logging.getLogger(__name__)


class KenPomClient:
    """
    KenPom API wrapper around /api.php?endpoint=...

    Your docs specify:
      - Base URL https://kenpom.com
      - Authorization: Bearer <API_KEY>
      - JSON response
    :contentReference[oaicite:5]{index=5}
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._http = httpx.Client(base_url=settings.base_url)
        self._cache = FileCache(settings.cache_dir, settings.cache_ttl_seconds)
        self._rl = RateLimiter(settings.rate_limit_rps)

    def close(self) -> None:
        self._http.close()

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.api_key}"}

    def _get(self, endpoint: str, params: Dict[str, Any]) -> Any:
        url = "/api.php"
        query = {"endpoint": endpoint, **params}

        cache_key = f"{self.settings.base_url}{url}?{sorted(query.items())}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        payload = request_json(
            client=self._http,
            method="GET",
            url=url,
            headers=self._headers(),
            params=query,
            timeout=self.settings.timeout_seconds,
            max_retries=self.settings.max_retries,
            backoff_base=self.settings.backoff_base_seconds,
            rate_limiter=self._rl,
        )
        self._cache.set(cache_key, payload)
        return payload

    # ---- endpoints ----

    def teams(self, *, y: int, c: Optional[str] = None) -> List[Team]:
        params: Dict[str, Any] = {"y": y}
        if c:
            params["c"] = c
        raw = self._get("teams", params)
        return [Team.model_validate(x) for x in raw]

    def conferences(self, *, y: int) -> List[Conference]:
        raw = self._get("conferences", {"y": y})
        return [Conference.model_validate(x) for x in raw]

    def ratings(
        self, *, y: Optional[int] = None, team_id: Optional[int] = None, c: Optional[str] = None
    ) -> List[Rating]:
        params: Dict[str, Any] = {}
        if y is not None:
            params["y"] = y
        if team_id is not None:
            params["team_id"] = team_id
        if c is not None:
            params["c"] = c
        if not params.get("y") and not params.get("team_id"):
            raise ValueError("ratings requires at least one of y or team_id")
        raw = self._get("ratings", params)
        return [Rating.model_validate(x) for x in raw]

    def archive(
        self,
        *,
        d: Optional[str] = None,
        preseason: bool = False,
        y: Optional[int] = None,
        team_id: Optional[int] = None,
        c: Optional[str] = None,
    ) -> List[ArchiveRating]:
        params: Dict[str, Any] = {}
        if d:
            params["d"] = d
        if preseason:
            params["preseason"] = "true"
        if y is not None:
            params["y"] = y
        if team_id is not None:
            params["team_id"] = team_id
        if c is not None:
            params["c"] = c

        # Docs: either d is required, OR (preseason=true AND y required)
        if not d and not (preseason and y is not None):
            raise ValueError("archive requires d=YYYY-MM-DD OR preseason=true with y")

        raw = self._get("archive", params)
        return [ArchiveRating.model_validate(x) for x in raw]

    def fanmatch(self, *, d: str) -> List[FanmatchGame]:
        raw = self._get("fanmatch", {"d": d})
        return [FanmatchGame.model_validate(x) for x in raw]

    def four_factors(self, *, y: int) -> List[FourFactors]:
        """Fetch Four Factors data for a season.

        The four factors are: effective FG%, turnover %, offensive rebound %, and FT rate.
        """
        raw = self._get("four-factors", {"y": y})
        return [FourFactors.model_validate(x) for x in raw]

    def point_distribution(self, *, y: int) -> List[PointDistribution]:
        """Fetch point distribution data for a season.

        Shows percentage of points from FTs, 2-pointers, and 3-pointers.
        """
        raw = self._get("pointdist", {"y": y})
        return [PointDistribution.model_validate(x) for x in raw]

    def height(self, *, y: int) -> List[Height]:
        """Fetch height, experience, and continuity data for a season."""
        raw = self._get("height", {"y": y})
        return [Height.model_validate(x) for x in raw]

    def misc_stats(self, *, y: int) -> List[MiscStats]:
        """Fetch miscellaneous team statistics for a season.

        Includes shooting percentages, block/steal rates, assist rates, etc.
        """
        raw = self._get("misc-stats", {"y": y})
        return [MiscStats.model_validate(x) for x in raw]
