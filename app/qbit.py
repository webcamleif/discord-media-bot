import os
import requests
import logging
import time
import qbittorrentapi
from app.sslutil import build_requests_kwargs

log = logging.getLogger("qbit")

class QbitClient:
    def __init__(self, host: str, user: str, password: str,
                 ca_cert_path: str | None = None, insecure: bool = False):

        # Only use config value, no ENV fallback
        if ca_cert_path:
            chosen_ca = ca_cert_path
            log.info(f"[QbitClient] CA from config: {chosen_ca}")
        else:
            chosen_ca = None
            log.info("[QbitClient] No custom CA; will use system trust or insecure")

        # Validate CA exists
        use_ca = bool(chosen_ca and os.path.exists(chosen_ca))
        if chosen_ca and not use_ca:
            log.warning(f"[QbitClient] CA path {chosen_ca} does not exist; falling back to system trust or insecure")

        # Build requests args
        if insecure:
            requests_args = {"verify": False}
            verify_webui = False
            log.warning("[QbitClient] Running in INSECURE mode (no SSL verification)")
        elif use_ca:
            requests_args = {"verify": chosen_ca}
            verify_webui = True
            log.info(f"[QbitClient] Will use custom CA for verify: {chosen_ca}")
        else:
            requests_args = {"verify": True}
            verify_webui = True
            log.info("[QbitClient] Using system CA store")

        # Instantiate client
        self.client = qbittorrentapi.Client(
            host=host,
            username=user,
            password=password,
            VERIFY_WEBUI_CERTIFICATE=verify_webui,
            REQUESTS_ARGS=requests_args,
        )

        # Probe with requests directly
        try:
            resp = requests.get(f"{host}/api/v2/app/version", **requests_args, timeout=10)
            log.info(f"[QbitClient] Probe OK: status={resp.status_code}")
        except Exception as e:
            log.error(f"[QbitClient] Probe FAILED: {e}")

        # Force session.verify if session exists after login
        try:
            self.client.auth_log_in()
            session = getattr(self.client, "_request_session", None) or getattr(self.client, "_http_session", None)
            if session is not None:
                session.verify = requests_args["verify"]
                log.info(f"[QbitClient] Patched session.verify = {session.verify}")
            else:
                log.warning("[QbitClient] Could not patch session.verify – session object is None")
            self.connected = True
        except Exception as e:
            self.connected = False
            log.error(f"[QbitClient] Auth login failed: {e}")

        # Setup backoff
        self._backoff = 5
        self._backoff_max = 300
        self._next_try_at = 0.0
        self._last_error: str | None = None

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
            # Quick manual probe before qbittorrentapi
            test_url = f"{self.client.host}/api/v2/app/version"
            r = requests.get(
                test_url,
                verify=self.client._VERIFY_WEBUI_CERTIFICATE
            )
            log.debug(f"[QbitClient] Probe status={r.status_code}, body={r.text[:80]}")
            
            self.client.auth_log_in()
            self.connected = True
            self._reset_backoff()
            return True
        except qbittorrentapi.LoginFailed as e:
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

