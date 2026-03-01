import logging
from datetime import datetime

import httpx

from ..config import settings
from ..models import BucketInfo

logger = logging.getLogger(__name__)


class AWService:
    """Async client for the ActivityWatch REST API."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.aw_server_url,
            timeout=10.0,
        )
        self._connected = False
        self._buckets_raw: dict = {}
        self.bucket_info = BucketInfo()

    async def startup(self) -> None:
        """Run health check and discover buckets. Safe to call even if AW is down."""
        self._connected = await self.health_check()
        if self._connected:
            await self._discover_buckets()

    async def shutdown(self) -> None:
        await self._client.aclose()

    @property
    def connected(self) -> bool:
        return self._connected

    async def health_check(self) -> bool:
        """Return True if the AW server is reachable."""
        try:
            resp = await self._client.get("/api/0/info")
            resp.raise_for_status()
            logger.info("Connected to ActivityWatch at %s", settings.aw_server_url)
            return True
        except (httpx.HTTPError, httpx.ConnectError):
            logger.warning(
                "Cannot reach ActivityWatch at %s — will retry on next request",
                settings.aw_server_url,
            )
            return False

    async def _discover_buckets(self) -> None:
        """Fetch bucket list from AW and identify relevant buckets by type."""
        self._buckets_raw = await self.get_buckets()

        window_buckets = []
        afk_buckets = []
        browser_buckets = []

        for bid, meta in self._buckets_raw.items():
            btype = meta.get("type", "")
            if btype == "currentwindow":
                window_buckets.append(bid)
            elif btype == "afkstatus":
                afk_buckets.append(bid)
            elif btype == "web.tab.current":
                browser_buckets.append(bid)

        self.bucket_info = BucketInfo(
            window=window_buckets[0] if window_buckets else None,
            afk=afk_buckets[0] if afk_buckets else None,
            browser=browser_buckets,
        )

        logger.info(
            "Discovered buckets — window: %s, afk: %s, browser: %s",
            self.bucket_info.window,
            self.bucket_info.afk,
            self.bucket_info.browser,
        )

    async def ensure_connected(self) -> bool:
        """Re-check connectivity if previously disconnected."""
        if not self._connected:
            self._connected = await self.health_check()
            if self._connected:
                await self._discover_buckets()
        return self._connected

    async def get_buckets(self) -> dict:
        """Fetch all buckets from AW."""
        resp = await self._client.get("/api/0/buckets/")
        resp.raise_for_status()
        return resp.json()

    async def get_events(
        self,
        bucket_id: str,
        start: datetime,
        end: datetime,
        limit: int = -1,
    ) -> list[dict]:
        """Fetch events from a specific AW bucket for a time range."""
        params: dict = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": limit,
        }
        resp = await self._client.get(
            f"/api/0/buckets/{bucket_id}/events",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()
