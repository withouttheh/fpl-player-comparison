"""
tests/test_cache.py — Unit tests for cache.TTLCache.

Tests cover:
  - Basic get/set/delete
  - TTL expiry (using a fake clock, not real sleeps)
  - Thread safety (concurrent reads and writes)
  - clear() resets state
  - Singleton module import behaviour

Why no real sleeps?
    A test that sleeps is slow and fragile. If the machine is under load, a
    sleep(1) may wake after 1.5 seconds, making the test timing-sensitive.
    We patch time.monotonic() with a fake clock we control, advancing it
    manually. Tests run in microseconds instead of seconds.
"""

import threading
import unittest
from unittest.mock import patch

from cache import TTLCache
from cache import cache as module_cache


class TestTTLCacheBasic(unittest.TestCase):
    """Basic get/set/delete behaviour."""

    def setUp(self):
        self.cache = TTLCache()

    def test_set_then_get_returns_value(self):
        self.cache.set("key", "value", ttl=60)
        self.assertEqual(self.cache.get("key"), "value")

    def test_get_missing_key_returns_none(self):
        self.assertIsNone(self.cache.get("nonexistent"))

    def test_set_overwrites_existing_key(self):
        self.cache.set("key", "first", ttl=60)
        self.cache.set("key", "second", ttl=60)
        self.assertEqual(self.cache.get("key"), "second")

    def test_delete_removes_key(self):
        self.cache.set("key", "value", ttl=60)
        self.cache.delete("key")
        self.assertIsNone(self.cache.get("key"))

    def test_delete_nonexistent_key_does_not_raise(self):
        # delete() on a missing key must be a no-op, not raise KeyError.
        try:
            self.cache.delete("ghost")
        except Exception as exc:
            self.fail(f"delete() raised unexpectedly: {exc}")

    def test_clear_removes_all_entries(self):
        self.cache.set("a", 1, ttl=60)
        self.cache.set("b", 2, ttl=60)
        self.cache.clear()
        self.assertIsNone(self.cache.get("a"))
        self.assertIsNone(self.cache.get("b"))
        self.assertEqual(len(self.cache), 0)

    def test_len_reflects_entry_count(self):
        self.assertEqual(len(self.cache), 0)
        self.cache.set("x", 1, ttl=60)
        self.assertEqual(len(self.cache), 1)
        self.cache.set("y", 2, ttl=60)
        self.assertEqual(len(self.cache), 2)

    def test_cached_value_can_be_any_type(self):
        """The cache must store arbitrary Python objects, not just strings."""
        import pandas as pd

        df = pd.DataFrame({"a": [1, 2, 3]})
        self.cache.set("df", df, ttl=60)
        result = self.cache.get("df")
        self.assertIsNotNone(result)
        self.assertEqual(list(result["a"]), [1, 2, 3])


class TestTTLCacheExpiry(unittest.TestCase):
    """TTL expiry using a fake monotonic clock."""

    def setUp(self):
        self.cache = TTLCache()
        # We will control time.monotonic() manually.
        self._fake_time = 1000.0

    def _fake_monotonic(self):
        return self._fake_time

    def test_entry_is_valid_before_ttl_expires(self):
        with patch("cache.time.monotonic", self._fake_monotonic):
            self.cache.set("key", "value", ttl=10)
            # Advance time by 9 seconds (still within TTL).
            self._fake_time += 9
            self.assertEqual(self.cache.get("key"), "value")

    def test_entry_is_gone_after_ttl_expires(self):
        with patch("cache.time.monotonic", self._fake_monotonic):
            self.cache.set("key", "value", ttl=10)
            # Advance time by 11 seconds (past TTL).
            self._fake_time += 11
            self.assertIsNone(self.cache.get("key"))

    def test_expired_entry_is_removed_from_store(self):
        """After a TTL miss, the entry must be evicted so len() reflects reality."""
        with patch("cache.time.monotonic", self._fake_monotonic):
            self.cache.set("key", "value", ttl=10)
            self._fake_time += 11
            self.cache.get("key")  # triggers eviction
            self.assertEqual(len(self.cache), 0)

    def test_exact_expiry_boundary_is_expired(self):
        """An entry at exactly its expiry timestamp is treated as expired.

        time.monotonic() > expiry means equality is expired. This prevents
        returning a value at the exact moment it should be considered stale.
        """
        with patch("cache.time.monotonic", self._fake_monotonic):
            self.cache.set("key", "value", ttl=10)
            # Advance to exactly the expiry timestamp.
            self._fake_time += 10
            self.assertIsNone(self.cache.get("key"))

    def test_different_keys_can_have_different_ttls(self):
        with patch("cache.time.monotonic", self._fake_monotonic):
            self.cache.set("short", "a", ttl=5)
            self.cache.set("long", "b", ttl=60)

            self._fake_time += 6
            self.assertIsNone(self.cache.get("short"))  # expired
            self.assertEqual(self.cache.get("long"), "b")  # still valid


class TestTTLCacheThreadSafety(unittest.TestCase):
    """Concurrent reads and writes must not corrupt the cache or raise exceptions."""

    def test_concurrent_writes_do_not_corrupt_data(self):
        """Multiple threads writing different keys simultaneously must all succeed."""
        cache = TTLCache()
        errors: list[Exception] = []

        def writer(key, value):
            try:
                for _ in range(100):
                    cache.set(key, value, ttl=60)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(f"k{i}", i)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Thread errors: {errors}")
        # Each key should have its own value.
        for i in range(10):
            self.assertEqual(cache.get(f"k{i}"), i)

    def test_concurrent_reads_and_writes_do_not_raise(self):
        """Simultaneous reads and writes to the same key must not raise."""
        cache = TTLCache()
        cache.set("shared", 0, ttl=60)
        errors: list[Exception] = []

        def reader():
            try:
                for _ in range(200):
                    cache.get("shared")
            except Exception as exc:
                errors.append(exc)

        def writer():
            try:
                for i in range(200):
                    cache.set("shared", i, ttl=60)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=reader) for _ in range(5)] + [
            threading.Thread(target=writer) for _ in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Thread errors: {errors}")


class TestTTLCacheModuleSingleton(unittest.TestCase):
    """The module-level `cache` instance is shared across imports."""

    def test_module_cache_is_ttl_cache_instance(self):
        self.assertIsInstance(module_cache, TTLCache)

    def test_module_cache_is_same_object_on_reimport(self):
        """Python caches module imports — reimporting returns the same object."""
        import importlib

        import cache as cache_module

        cache_module_reimported = importlib.import_module("cache")
        self.assertIs(cache_module.cache, cache_module_reimported.cache)

    def tearDown(self):
        # Reset the module singleton so other test files start clean.
        module_cache.clear()


if __name__ == "__main__":
    unittest.main()
