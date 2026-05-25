"""
cache.py — Thread-safe in-memory TTL cache.

The FPL API is a public endpoint with no authentication. We should be a
considerate consumer: don't fetch the same data repeatedly when it hasn't
changed. This cache stores responses in memory and returns cached copies
until the TTL (time-to-live) expires, at which point the next request
fetches fresh data.

Why a custom cache and not functools.lru_cache?
    lru_cache evicts entries based on how recently they were used, not on
    time. FPL data changes on a schedule (player stats update once per
    gameweek, fixture lists change occasionally). We need time-based
    expiry, which lru_cache doesn't support.

Why not a third-party library (cachetools, dogpile.cache)?
    This project intentionally uses only the Python standard library.
    A TTL cache with thread safety is ~60 lines. There is no reason to add
    a dependency for something this self-contained.

Why in-memory and not a file or Redis?
    The cache only needs to survive as long as the server process. A restart
    clearing the cache is acceptable — the first request after restart pays
    the FPL API cost, then subsequent requests are served from cache. For a
    multi-process deployment (multiple server workers), a shared external
    cache like Redis would be required. That is a future concern.

Thread safety:
    The server handles requests concurrently in threads. Two threads could
    simultaneously read an expired entry and both miss the cache, each
    making a separate FPL API call for the same data. This is called a
    cache stampede. We prevent it by holding a lock while checking and
    setting entries, so only one thread fetches fresh data for a given key
    at a time.
"""

import threading
import time
from typing import Any


class TTLCache:
    """Thread-safe key/value cache where every entry has a time-to-live.

    Entries are stored as (value, expiry_timestamp) pairs. On every get(),
    we check whether the entry has expired. Expired entries are removed
    lazily (on first access after expiry) rather than by a background
    sweeper thread, which keeps this class simple and dependency-free.

    Example
    -------
        cache = TTLCache()
        cache.set("bootstrap", dataframe, ttl=3600)

        value = cache.get("bootstrap")
        # Returns the dataframe if set within the last hour, else None.
    """

    def __init__(self) -> None:
        # Maps cache key → (stored value, expiry as a monotonic timestamp).
        self._store: dict[str, tuple[Any, float]] = {}

        # Why RLock (re-entrant lock) and not a plain Lock?
        #   A plain Lock raises a deadlock if the same thread tries to acquire
        #   it twice (e.g. if get() internally called set()). RLock allows a
        #   thread that already holds the lock to acquire it again. This makes
        #   the class safer to extend without subtle deadlock bugs.
        self._lock = threading.RLock()

    def get(self, key: str) -> Any | None:
        """Return the cached value for key, or None if absent or expired.

        Why check expiry on read rather than on a timer?
            A background timer thread adds complexity — it needs its own
            lifecycle, error handling, and shutdown logic. Lazy expiry on read
            is simpler and correct. The only downside is that expired entries
            occupy memory until they are accessed. Given that our entries are
            DataFrames (kilobytes, not gigabytes) this is a non-issue.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None

            value, expiry = entry

            if time.monotonic() >= expiry:
                # Entry exists but has expired. >= means the value is stale
                # at exactly the expiry instant — no window where a value
                # is returned after its TTL has elapsed. Remove it and signal
                # a miss so the caller fetches fresh data.
                del self._store[key]
                return None

            return value

    def set(self, key: str, value: Any, ttl: float) -> None:
        """Store value under key, expiring ttl seconds from now.

        Parameters
        ----------
        key:
            Cache key. Convention: use descriptive strings like
            "bootstrap_static" or "history:42" (player ID 42).
        value:
            The value to cache. Typically a pandas DataFrame or a dict.
        ttl:
            Seconds until expiry. Common values used in this project:
              - 3600  (1 hour)  — bootstrap-static, fixtures
              -  300  (5 mins)  — per-player gameweek history
              - 86400 (1 day)   — past-season history

        Why time.monotonic() and not time.time()?
            time.time() reads the system (wall) clock, which can jump
            backwards when NTP adjusts the system time or when daylight
            saving time ends. A backwards jump would make entries appear to
            expire in the far future, effectively caching them indefinitely.
            time.monotonic() is guaranteed to only ever increase — it measures
            elapsed time since an arbitrary fixed point (usually system boot)
            and is unaffected by clock adjustments.
        """
        expiry = time.monotonic() + ttl
        with self._lock:
            self._store[key] = (value, expiry)

    def delete(self, key: str) -> None:
        """Explicitly remove a key. Useful when data is known to be stale."""
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Remove all entries. Used in tests to reset state between cases."""
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        """Return the number of entries currently in the cache (including expired)."""
        with self._lock:
            return len(self._store)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

# Why a module-level instance and not a class attribute or passed as a parameter?
#
#   Python imports a module exactly once per process — subsequent imports
#   return the already-imported module object from sys.modules. This means
#   every file that does `from cache import cache` gets a reference to the
#   same TTLCache instance. All request threads share the same cache
#   automatically, with no dependency injection or global state management
#   required.
#
#   The alternative — passing the cache as a constructor argument to every
#   handler — is more testable (you can inject a fresh cache per test) but
#   adds parameter plumbing through several layers. We get testability a
#   different way: TTLCache.clear() lets tests reset the singleton between
#   cases without needing to inject a separate instance.
cache = TTLCache()
