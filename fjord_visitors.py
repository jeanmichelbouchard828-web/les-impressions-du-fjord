"""Privacy-preserving visitor totals and online estimates for Fjord.

The only public metrics are aggregate counts. No IP address, user agent,
visitor token or hash is returned. Render preview reads the Railway counts
without connecting to its production database.
"""
import hashlib
import json
import os
import re
import threading
import time
import urllib.request

ACTIVE_MINUTES = 5
SOURCE_URL = "https://site-web-production-dd54.up.railway.app/api/public/visitors"
_STATS_CACHE = {"updated": 0.0, "data": None}
_CACHE_LOCK = threading.Lock()


def initialize(db):
    """Additive schema change: preserve every historic unique visitor."""
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS site_visitors (
            visitor_hash TEXT PRIMARY KEY,
            first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
        c.execute("""ALTER TABLE site_visitors
                     ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ""")
        c.execute("""CREATE INDEX IF NOT EXISTS site_visitors_last_seen_idx
                     ON site_visitors(last_seen)""")


def observe(db, token):
    """Update one existing or new browser anonymously, at most once/45 s."""
    if not isinstance(token, str) or re.fullmatch(r"[a-f0-9]{32}", token) is None:
        return False
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    with db() as c:
        c.execute("""INSERT INTO site_visitors(visitor_hash,last_seen)
                     VALUES (%s, NOW())
                     ON CONFLICT(visitor_hash) DO UPDATE SET last_seen=NOW()
                     WHERE site_visitors.last_seen IS NULL
                       OR site_visitors.last_seen < NOW()-INTERVAL '45 seconds'""",
                  (digest,))
    return True


def local_stats(db):
    """Count unique browsers and those observed in the past five minutes."""
    with db() as c:
        row = c.execute("""SELECT COUNT(*)::bigint AS total,
                 COUNT(*) FILTER (WHERE last_seen >= NOW()-INTERVAL '5 minutes')
                  ::bigint AS online
                 FROM site_visitors""").fetchone()
    return {"total": int(row["total"]), "online": int(row["online"]),
            "window_minutes": ACTIVE_MINUTES}


def _validate_stats(data):
    if not isinstance(data, dict):
        return None
    a = data.get("total")
    b = data.get("online")
    if (type(a) is not int or type(b) is not int
            or not 0 <= b <= a <= 1000000000
            or data.get("window_minutes") != ACTIVE_MINUTES):
        return None
    return {"total": a, "online": b, "window_minutes": ACTIVE_MINUTES}


def remote_stats():
    """Only aggregate stats; never accept a user-supplied source URL."""
    now = time.monotonic()
    with _CACHE_LOCK:
        if now - _STATS_CACHE["updated"] < 25:
            return _STATS_CACHE["data"]
        req = urllib.request.Request(
            SOURCE_URL, headers={"Accept": "application/json",
                                 "User-Agent": "Fjord-Render-Stats/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=4) as response:
                if response.status != 200:
                    raise ValueError("Source unavailable")
                data = json.loads(response.read(1025))
            safe = _validate_stats(data)
        except (OSError, ValueError, TypeError):
            safe = None
        _STATS_CACHE.update(updated=now, data=safe)
        return safe


def site_stats(db):
    if os.environ.get("FJORD_PREVIEW_MODE") == "1":
        return remote_stats()
    return local_stats(db)
