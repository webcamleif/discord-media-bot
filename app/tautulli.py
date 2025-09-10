import aiohttp
from urllib.parse import quote


class TautulliClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def _get(self, cmd: str, params: dict | None = None) -> dict:
        """Generic GET wrapper for Tautulli API v2."""
        params = params or {}
        url = f"{self.base_url}/api/v2"
        q = {"apikey": self.api_key, "cmd": cmd}
        q.update(params)

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=q, timeout=10) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def get_activity(self) -> list[dict]:
        try:
            data = await self._get("get_activity")
            return data.get("response", {}).get("data", {}).get("sessions", []) or []
        except Exception:
            return []

    async def get_home_stats(
        self,
        stats_type: str,
        time_range: int,
        length: int = 5,
        order_column: str = "total_plays"
    ):
        try:
            params = {
                "stats_type": stats_type,
                "time_range": time_range,
                "length": length,
                "order_column": order_column,
            }
            data = await self._get("get_home_stats", params=params)
            items = data.get("response", {}).get("data", []) or []
            for block in items:
                if block.get("stat_id") == stats_type:
                    return block.get("rows", []) or []
        except Exception:
            return []
        return []

    def image_proxy_url(self, img_path: str, width: int = 400, height: int = 600) -> str:
        q_img = quote(img_path, safe="/:?=&")
        return (
            f"{self.base_url}/api/v2"
            f"?apikey={self.api_key}&cmd=pms_image_proxy&img={q_img}&width={width}&height={height}"
        )

    # ---------- Plex status helpers ----------

    async def count_library(self, section_type: str) -> int:
        """Return number of items in libraries filtered by section_type ('movie' or 'show')."""
        libs = await self._get("get_libraries")
        libs = libs.get("response", {}).get("data", []) or []
        count = 0
        for lib in libs:
            if lib.get("section_type") == section_type:
                count += int(lib.get("count", 0))
        return count

    async def count_users(self) -> int:
        """Return total number of users in Tautulli."""
        users = await self._get("get_users")
        users = users.get("response", {}).get("data", []) or []
        return len(users)

