"""
proxy_rotator.py -- Shared thread-safe proxy rotator with auto-refresh.

Loads validated proxies from a proxy_pool.json (produced by proxy_pool.py),
prioritises authenticated (webshare) proxies, rotates round-robin, and
automatically refreshes the pool when it runs low.

Library usage:
    from utils.networking.proxy_rotator import ProxyRotator

    rotator = ProxyRotator(pool_path="/path/to/proxy_pool.json")
    proxy = rotator.next()
    proxies_dict = ProxyRotator.to_requests(proxy)
    rotator.mark_success(proxy)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class ProxyRotator:
    """Thread-safe round-robin proxy rotator with auto-refresh.

    Features:
        - Loads validated HTTP/HTTPS proxies from proxy_pool.json
        - Prioritises authenticated (webshare) proxies
        - Round-robin rotation
        - Per-proxy success/failure tracking
        - Automatic removal after MAX_FAILURES consecutive failures
        - Auto-refresh when pool drops to <= MIN_POOL_SIZE
        - Cooldown between refresh attempts (REFRESH_COOLDOWN seconds)
        - Thread-safe via threading.Lock (cheap no-op for single-threaded callers)
    """

    MAX_FAILURES = 3
    MIN_POOL_SIZE = 5
    REFRESH_COOLDOWN = 300  # seconds

    def __init__(self, pool_path: str | Path, auth_only: bool = False) -> None:
        self._lock = threading.Lock()
        self._pool_path = Path(pool_path)
        self._auth_only = auth_only
        self._proxies: List[Dict[str, Any]] = []
        self._index: int = 0
        self._stats: Dict[str, Dict[str, int]] = {}  # key -> {successes, failures}
        self._last_refresh: float = 0.0
        self._refresh_in_progress: bool = False
        self._load()

    # ── Loading ──────────────────────────────────────────────────

    def _load(self) -> None:
        """Load proxies from disk. Caller must hold self._lock or be __init__."""
        if not self._pool_path.exists():
            log.warning("Proxy pool not found at %s", self._pool_path)
            return

        try:
            data = json.loads(self._pool_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            log.error("Failed to load proxy pool: %s", e)
            return

        raw = data.get("proxies", [])

        # Keep only valid HTTP/HTTPS proxies
        valid = [
            p for p in raw
            if p.get("valid") and p.get("protocol", "").lower() in ("http", "https")
        ]

        # Split: authenticated first (sorted by response_ms), then free
        authenticated = sorted(
            [p for p in valid if p.get("username") and p.get("password")],
            key=lambda p: p.get("response_ms", 9999),
        )
        free = sorted(
            [p for p in valid if not (p.get("username") and p.get("password"))],
            key=lambda p: p.get("response_ms", 9999),
        )

        if self._auth_only:
            self._proxies = authenticated
        else:
            self._proxies = authenticated + free
        self._index = 0

        # Initialise stats for new proxies (preserve existing stats)
        for p in self._proxies:
            key = self._proxy_key(p)
            self._stats.setdefault(key, {"successes": 0, "failures": 0})

        if self._auth_only:
            log.info(
                "ProxyRotator loaded %d authenticated proxies (auth_only=True, %d free excluded)",
                len(authenticated), len(free),
            )
        else:
            log.info(
                "ProxyRotator loaded %d proxies (%d authenticated, %d free)",
                len(self._proxies), len(authenticated), len(free),
            )

    # ── Refresh ──────────────────────────────────────────────────

    def _maybe_refresh(self) -> bool:
        """Refresh the proxy pool if cooldown has elapsed.

        Releases the lock during I/O so other threads aren't blocked.
        Returns True if new proxies were loaded.
        """
        now = time.time()

        # Check cooldown and concurrency guard under lock
        with self._lock:
            if self._refresh_in_progress:
                return False
            if now - self._last_refresh < self.REFRESH_COOLDOWN:
                log.debug("Proxy refresh cooldown active, skipping")
                return False
            self._refresh_in_progress = True
            self._last_refresh = now
            before = len(self._proxies)

        # Do I/O outside the lock
        log.info("Proxy pool low (%d remaining), refreshing...", before)
        try:
            from .proxy_pool import (
                fetch_all_sources,
                deduplicate,
                validate_proxies,
                save_pool,
            )

            raw = fetch_all_sources(max_workers=6)
            total_fetched = len(raw)
            proxies = deduplicate(raw)
            proxies = validate_proxies(proxies, workers=20, timeout=5)
            save_pool(proxies, total_fetched, pool_path=self._pool_path)
        except Exception as e:
            log.warning("Proxy refresh failed: %s", e)
            with self._lock:
                self._refresh_in_progress = False
            return False

        # Reload under lock
        with self._lock:
            self._load()
            self._refresh_in_progress = False
            log.info("Refresh complete: %d -> %d proxies", before, len(self._proxies))
            return len(self._proxies) > before

    # ── Public API ───────────────────────────────────────────────

    @staticmethod
    def _proxy_key(proxy: Dict[str, Any]) -> str:
        """Unique string key for a proxy dict."""
        return f"{proxy.get('host')}:{proxy.get('port')}"

    def next(self) -> Optional[Dict[str, Any]]:
        """Return the next proxy dict (round-robin), or None if pool is empty.

        Triggers auto-refresh when pool drops to <= MIN_POOL_SIZE.
        """
        with self._lock:
            if self._proxies:
                need_refresh = len(self._proxies) <= self.MIN_POOL_SIZE
                proxy = self._proxies[self._index % len(self._proxies)]
                self._index = (self._index + 1) % len(self._proxies)
                if not need_refresh:
                    return proxy
                # Release lock, refresh, then return the proxy we already picked
            else:
                need_refresh = True
                proxy = None

        # Attempt refresh outside lock
        if need_refresh:
            self._maybe_refresh()

        if proxy is not None:
            return proxy

        # Pool was empty — check if refresh populated it
        with self._lock:
            if not self._proxies:
                return None
            proxy = self._proxies[self._index % len(self._proxies)]
            self._index = (self._index + 1) % len(self._proxies)
            return proxy

    def mark_success(self, proxy: Optional[Dict[str, Any]]) -> None:
        """Record a successful request through this proxy."""
        if proxy is None:
            return
        key = self._proxy_key(proxy)
        with self._lock:
            self._stats.setdefault(key, {"successes": 0, "failures": 0})
            self._stats[key]["successes"] += 1
            # Reset failure count on success (proxy proved it works)
            self._stats[key]["failures"] = 0

    def mark_failed(self, proxy: Optional[Dict[str, Any]]) -> None:
        """Record a failed request. Removes proxy after MAX_FAILURES."""
        if proxy is None:
            return
        key = self._proxy_key(proxy)
        need_refresh = False
        with self._lock:
            self._stats.setdefault(key, {"successes": 0, "failures": 0})
            self._stats[key]["failures"] += 1
            fail_count = self._stats[key]["failures"]

            if fail_count >= self.MAX_FAILURES:
                # Remove the proxy
                self._proxies = [
                    p for p in self._proxies if self._proxy_key(p) != key
                ]
                if self._proxies:
                    self._index = self._index % len(self._proxies)
                else:
                    self._index = 0
                log.warning(
                    "Proxy %s removed after %d failures (%d proxies remaining)",
                    key, fail_count, len(self._proxies),
                )
                if len(self._proxies) <= self.MIN_POOL_SIZE:
                    need_refresh = True
            else:
                # Move to end of list so it's tried last
                moved = [p for p in self._proxies if self._proxy_key(p) == key]
                rest = [p for p in self._proxies if self._proxy_key(p) != key]
                self._proxies = rest + moved
                if self._proxies:
                    self._index = self._index % len(self._proxies)
                log.debug(
                    "Proxy %s failed (%d/%d), moved to end of pool",
                    key, fail_count, self.MAX_FAILURES,
                )

        if need_refresh:
            self._maybe_refresh()

    def available(self) -> int:
        """Number of proxies still in the pool."""
        with self._lock:
            return len(self._proxies)

    def __len__(self) -> int:
        with self._lock:
            return len(self._proxies)

    @staticmethod
    def to_requests(proxy: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        """Convert a proxy dict to requests library format.

        Returns {"http": "http://user:pass@host:port", "https": "..."} or None.
        """
        if proxy is None:
            return None
        host = proxy.get("host", "")
        port = proxy.get("port", "")
        protocol = proxy.get("protocol", "http").lower()
        username = proxy.get("username")
        password = proxy.get("password")

        if username and password:
            proxy_url = f"{protocol}://{username}:{password}@{host}:{port}"
        else:
            proxy_url = f"{protocol}://{host}:{port}"

        return {"http": proxy_url, "https": proxy_url}

    @staticmethod
    def to_playwright(proxy: Dict[str, Any]) -> Dict[str, str]:
        """Convert a proxy dict to Playwright proxy options.

        Returns {"server": "http://host:port", "username": ..., "password": ...}.
        """
        opts: Dict[str, str] = {
            "server": f"{proxy.get('protocol', 'http')}://{proxy['host']}:{proxy['port']}"
        }
        if proxy.get("username"):
            opts["username"] = proxy["username"]
        if proxy.get("password"):
            opts["password"] = proxy.get("password", "")
        return opts

    def log_stats(self, logger: Optional[logging.Logger] = None) -> None:
        """Log per-proxy success/failure summary."""
        logger = logger or log
        logger.info("── Proxy usage stats ──")
        with self._lock:
            if not self._stats:
                logger.info("  (no proxies used)")
                return
            for key, s in sorted(self._stats.items()):
                logger.info(
                    "  %-21s  successes=%d  failures=%d",
                    key, s["successes"], s["failures"],
                )
            logger.info("  Pool remaining: %d proxies", len(self._proxies))
