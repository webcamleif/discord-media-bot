import os
import ssl
import logging

log = logging.getLogger("sslutil")


def build_requests_kwargs(ca_cert_path: str | None, insecure: bool) -> dict:
    """
    Build kwargs for requests-based clients (requests, qbittorrentapi).
    Returns {"verify": ...}
    """
    if insecure:
        log.warning("[SSL] Running in INSECURE mode (verification disabled)")
        return {"verify": False}

    if ca_cert_path and os.path.exists(ca_cert_path):
        log.info(f"[SSL] Using custom CA cert: {ca_cert_path}")
        return {"verify": ca_cert_path}

    log.info("[SSL] Using system CA store")
    return {"verify": True}


def build_aiohttp_ssl(ca_cert_path: str | None, insecure: bool):
    """
    Build the `ssl` argument for aiohttp.
    Returns either False, an SSLContext, or None.
    """
    if insecure:
        log.warning("[SSL] aiohttp: Running in INSECURE mode (verification disabled)")
        return False

    if ca_cert_path and os.path.exists(ca_cert_path):
        log.info(f"[SSL] aiohttp: Using custom CA cert: {ca_cert_path}")
        ctx = ssl.create_default_context(cafile=ca_cert_path)
        return ctx

    log.info("[SSL] aiohttp: Using system CA store")
    return None

