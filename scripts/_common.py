# -*- coding: utf-8 -*-
"""Japan Shopping Buddy · shared utilities

Credentials are read from environment only (no hardcoding); HTTP via urllib (no third-party deps).

Priority: env vars > JSON file pointed to by JSB_SECRETS.
Keys read: RAKUTEN_APPLICATION_ID / RAKUTEN_ACCESS_KEY / PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET
"""
import base64
import json
import os
import ssl
import urllib.error
import urllib.request

DEFAULT_PROXY = "http://127.0.0.1:7890"


class JsbError(Exception):
    """Business/expected error: surfaced upward as a friendly message, never a raw stack trace."""


def load_secrets():
    """Return a credentials dict keyed by uppercase env-var names."""
    keys = [
        "RAKUTEN_APPLICATION_ID",
        "RAKUTEN_ACCESS_KEY",
        "PAYPAL_CLIENT_ID",
        "PAYPAL_CLIENT_SECRET",
    ]
    secrets = {k: os.environ.get(k) for k in keys}
    path = os.environ.get("JSB_SECRETS")
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if isinstance(v, str) and v and not secrets.get(k):
                secrets[k] = v
    return secrets


def proxy_enabled():
    return os.environ.get("JSB_PROXY", "1").strip().lower() not in ("0", "off", "false", "no")


def _opener(use_proxy):
    handlers = []
    if use_proxy:
        handlers.append(
            urllib.request.ProxyHandler({"http": DEFAULT_PROXY, "https": DEFAULT_PROXY})
        )
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    ctx = ssl.create_default_context()
    handlers.append(urllib.request.HTTPSHandler(context=ctx))
    return urllib.request.build_opener(*handlers)


def http_request(method, url, headers=None, body=None, use_proxy=None, timeout=15):
    """Return (status_code, text). Expected HTTP errors also return status+body for upstream parsing."""
    if use_proxy is None:
        use_proxy = proxy_enabled()
    payload = None
    if body is not None:
        payload = body.encode("utf-8") if isinstance(body, str) else body
    req = urllib.request.Request(url, data=payload, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    opener = _opener(use_proxy)
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raw = ""
        try:
            raw = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        return e.code, raw
    except urllib.error.URLError as e:
        raise JsbError(f"Network unreachable: {e.reason}")


def basic_auth(client_id, client_secret):
    token = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"