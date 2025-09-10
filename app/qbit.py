import time
import qbittorrentapi

class QbitClient:
    """
    qBittorrent client with resilient reconnect & exponential backoff.
    - Does NOT raise on connection errors.
    - get_downloading() returns:
        * list[...]  when connected
        * None       when currently disconnected (will retry automatically)
    """
    def __init__(self, host: str, port: int, user: str, password: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password

        self.client = qbittorrentapi.Client(host=host, port=port, username=user, password=password)
        self.connected: bool = False

        # Backoff control
        self._backoff = 5            # seconds (min)
        self._backoff_max = 300      # seconds (max)
        self._next_try_at = 0.0
        self._last_error: str | None = None

        # Try initial connect (non-fatal)
        self._try_connect(initial=True)

    # ---------- Public API ----------
    def get_downloading(self):
        """
        Returns a list of downloading torrents if connected.
        Returns None if currently disconnected and waiting for retry.
        """
        if not self._ensure_connected():
            return None

        try:
            torrents = self.client.torrents_info()
            # If we can talk to qBittorrent, reset backoff
            self._reset_backoff()
            return [t for t in torrents if (getattr(t, "state", "") or "").lower() == "downloading"]
        except Exception as e:
            # Connection dropped mid-loop; mark as disconnected and backoff
            self._on_failure(e)
            return None

    def status_text(self) -> str | None:
        """
        Human text for current state if disconnected, else None.
        """
        if self.connected:
            return None
        retry_in = max(0, int(round(self._next_try_at - time.time())))
        base = self._last_error or "connection failed"
        return f"qBittorrent unreachable: {base}. Retrying in {retry_in}s."

    # ---------- Internals ----------
    def _ensure_connected(self) -> bool:
        if self.connected:
            return True
        now = time.time()
        if now < self._next_try_at:
            return False
        return self._try_connect()

    def _try_connect(self, initial: bool = False) -> bool:
        try:
            self.client.auth_log_in()
            self.connected = True
            self._reset_backoff()
            return True
        except qbittorrentapi.LoginFailed as e:
            # Bad creds are unlikely to recover; still backoff to avoid log spam
            self._on_failure(e)
            return False
        except Exception as e:
            self._on_failure(e)
            return False

    def _on_failure(self, err: Exception):
        self.connected = False
        self._last_error = str(err)
        # increase backoff
        self._next_try_at = time.time() + self._backoff
        self._backoff = min(self._backoff * 2, self._backoff_max)

    def _reset_backoff(self):
        self.connected = True
        self._last_error = None
        self._backoff = 5
        self._next_try_at = 0.0

