import json, os, tempfile, base64, secrets, hashlib, hmac, logging
from typing import Optional
from app.config import Settings

log = logging.getLogger(__name__)

CONFIG_PATH = "/data/config.json"
ADMIN_PATH  = "/data/admin.json"

def ensure_data_dir():
    os.makedirs("/data", exist_ok=True)

def load_config() -> Settings:
    ensure_data_dir()
    if not os.path.exists(CONFIG_PATH):
        return Settings()
    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
        return Settings(**data)
    except Exception:
        return Settings()

def save_config(cfg: Settings) -> None:
    ensure_data_dir()
    tmp_fd, tmp_path = tempfile.mkstemp(dir="/data", prefix="cfg-", suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(cfg.model_dump(), f, indent=2)
        os.replace(tmp_path, CONFIG_PATH)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass

# ------- message ids persistence -------
def load_message_ids(path: str) -> dict:
    ensure_data_dir()
    try:
        d = os.path.dirname(path) or "/data"
        os.makedirs(d, exist_ok=True)
        if not os.path.exists(path):
            return {}
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        log.error("Failed to load message ids from %s: %s", path, e)
        return {}

def save_message_ids(path: str, data: dict) -> None:
    ensure_data_dir()
    try:
        d = os.path.dirname(path) or "/data"
        os.makedirs(d, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=d, prefix="msg-", suffix=".json")
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f)
        os.replace(tmp_path, path)
    except Exception as e:
        log.error("Failed to save message ids to %s: %s", path, e)

# ---------------- Admin user store ----------------
def _new_secret() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")

def _hash_password(password: str, salt: str) -> str:
    # PBKDF2-HMAC-SHA256
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.urlsafe_b64decode(salt + "=="), 200000)
    return base64.urlsafe_b64encode(dk).decode().rstrip("=")

def load_admin() -> Optional[dict]:
    ensure_data_dir()
    if not os.path.exists(ADMIN_PATH):
        return None
    try:
        with open(ADMIN_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return None

def save_admin(username: str, password: str) -> dict:
    ensure_data_dir()
    salt = _new_secret()
    pwd = _hash_password(password, salt)
    secret_key = _new_secret()
    data = {"username": username, "salt": salt, "password_hash": pwd, "secret_key": secret_key}
    tmp_fd, tmp_path = tempfile.mkstemp(dir="/data", prefix="admin-", suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, ADMIN_PATH)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass
    return data

def verify_password(admin: dict, password: str) -> bool:
    return hmac.compare_digest(admin.get("password_hash",""), _hash_password(password, admin.get("salt","")))

