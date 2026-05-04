"""
Defaults for on-prem / LAN deployments (CORS, CSRF, email links).

``LAN_SUBNET_CIDR`` documents the site network (e.g. 192.168.1.0/24). Browser ``Origin`` /
``CSRF_TRUSTED_ORIGINS`` must always be full URLs (``http://host:port``), never CIDR notation.
Override host with env ``LAN_HOST`` (default ``192.168.1.4``).
"""

import os

LAN_SUBNET_CIDR = (os.environ.get("LAN_SUBNET_CIDR") or "192.168.1.0/24").strip()
LAN_HOST = (os.environ.get("LAN_HOST") or "192.168.1.4").strip()

# Ports used across this repo: SPA nginx (8091), API nginx (8092), Vite / docker SPA (3000, 4001, 4002), Django dev (8000)
LAN_HTTP_PORTS = (8091, 8092, 3000, 4001, 4002, 8000)


def lan_browser_origins():
    return [f"http://{LAN_HOST}:{p}" for p in LAN_HTTP_PORTS]


def merge_unique_origins(*iterables):
    seen = set()
    out = []
    for it in iterables:
        for x in it:
            if not x or x in seen:
                continue
            seen.add(x)
            out.append(x)
    return out
