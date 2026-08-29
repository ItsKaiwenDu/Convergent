import os
import sys
import time
import tempfile
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from customs.cache import (
    CacheManager,
    get_file_fingerprint,
    get_params_hash,
    make_cache_key,
    make_content_key,
    clear_cache,
    PARTIAL_THRESHOLD,
    HEAD_TAIL_SIZE,
)


class TestCache(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)
        self.db_path = self.dir_path / "test_cache.sqlite"
        self.cache_mgr = CacheManager(db_path=self.db_path, ttl_days=30.0)

    def tearDown(self):
        self.cache_mgr.close()
        self.temp_dir.cleanup()

    def test_params_hash_deterministic(self):
        params1 = {"target": "PNG", "fps": 30, "bitrate": "192k", "strip_metadata": True}
        params2 = {"strip_metadata": True, "bitrate": "192k", "fps": 30, "target": "PNG"}
        params3 = {"target": "PNG", "fps": 30, "bitrate": "192k", "strip_metadata": True, "none_val": None}
        
        h1 = get_params_hash(params1)
        h2 = get_params_hash(params2)
        self.assertEqual(h1, h2)
        self.assertIsInstance(h1, str)
        self.assertEqual(len(h1), 32)  # 16 bytes = 32 hex chars

    def test_make_cache_key(self):
        src_path = self.dir_path / "sample.jpg"
        params = {"target": "PNG"}
        key1 = make_cache_key(src_path, params)
        key2 = make_cache_key(src_path, params)
        self.assertEqual(key1, key2)
        self.assertEqual(len(key1), 32)

    def test_make_content_key(self):
        params = {"target": "PNG"}
        c_key = make_content_key("abcd1234efgh5678", params)
        self.assertEqual(len(c_key), 32)

    def test_fingerprint_small_file(self):
        small_file = self.dir_path / "small.txt"
        content = b"Hello, Convergent Cache!"
        small_file.write_bytes(content)

        file_hash, mtime, size = get_file_fingerprint(small_file)
        self.assertEqual(size, len(content))
        self.assertGreater(mtime, 0)
        self.assertIsInstance(file_hash, str)
        self.assertEqual(len(file_hash), 32)

    def test_fingerprint_large_file(self):
        # Create a file slightly larger than PARTIAL_THRESHOLD (10MB)
        large_file = self.dir_path / "large.bin"
        file_size = PARTIAL_THRESHOLD + 1024 * 1024  # 11MB
        with open(large_file, "wb") as f:
            f.write(b"A" * HEAD_TAIL_SIZE)
            f.seek(file_size - 100)
            f.write(b"Z" * 100)

        file_hash, mtime, size = get_file_fingerprint(large_file)
        self.assertEqual(size, file_size)
        self.assertGreater(mtime, 0)
        self.assertEqual(len(file_hash), 32)

    def test_cache_hit_and_miss_lifecycle(self):
        src = self.dir_path / "photo.jpg"
        src.write_bytes(b"image binary data")
        out = self.dir_path / "photo.png"
        out.write_bytes(b"png binary data")
        params = {"target": "PNG", "strip_metadata": False}

        # 1. Miss when not cached
        is_valid, reason = self.cache_mgr.is_cached_valid(src, out, params)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "miss")

        # 2. Record success (save)
        self.cache_mgr.save(src, out, params)

        # 3. Hit when cached and files unmodified
        is_valid, reason = self.cache_mgr.is_cached_valid(src, out, params)
        self.assertTrue(is_valid)
        self.assertTrue(reason.startswith("blake2b:"))

        # 4. Miss when output file deleted
        out.unlink()
        is_valid, reason = self.cache_mgr.is_cached_valid(src, out, params)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "output missing")

        # Recreate output
        out.write_bytes(b"png binary data")

        # 5. Miss when source file content mutated (mtime changes)
        time.sleep(0.01)
        src.write_bytes(b"mutated binary data")
        is_valid, reason = self.cache_mgr.is_cached_valid(src, out, params)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "hash mismatch")

    def test_cache_ttl_expiration(self):
        # Create cache manager with very short TTL
        ttl_mgr = CacheManager(db_path=self.db_path, ttl_days=1.0 / 86400.0)  # 1 second TTL
        src = self.dir_path / "doc.md"
        src.write_bytes(b"# Test Markdown")
        out = self.dir_path / "doc.pdf"
        out.write_bytes(b"%PDF-1.4")
        params = {"target": "PDF"}

        ttl_mgr.save(src, out, params)
        is_valid, _ = ttl_mgr.is_cached_valid(src, out, params)
        self.assertTrue(is_valid)

        # Manually backdate entry timestamps in DB to simulate expiration
        cur = ttl_mgr.conn.cursor()
        cur.execute("UPDATE entries SET last_accessed_at = last_accessed_at - 100, created_at = created_at - 100")
        ttl_mgr.conn.commit()

        is_valid, reason = ttl_mgr.is_cached_valid(src, out, params)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "expired")
        ttl_mgr.close()

    def test_cache_stats_and_prune(self):
        src1 = self.dir_path / "a.jpg"
        src1.write_bytes(b"a")
        out1 = self.dir_path / "a.png"
        out1.write_bytes(b"a_out")
        
        src2 = self.dir_path / "b.jpg"
        src2.write_bytes(b"b")
        out2 = self.dir_path / "b.png"
        out2.write_bytes(b"b_out")

        self.cache_mgr.save(src1, out1, {"target": "PNG"})
        self.cache_mgr.save(src2, out2, {"target": "PNG"})

        stats = self.cache_mgr.stats()
        self.assertEqual(stats["count"], 2)
        self.assertGreater(stats["size_bytes"], 0)
        self.assertIn("oldest_entry", stats)
        self.assertIn("newest_entry", stats)

        # Backdate src1 entry to be older than 35 days
        cur = self.cache_mgr.conn.cursor()
        old_time = time.time() - (35 * 86400)
        cur.execute("UPDATE entries SET last_accessed_at = ?, created_at = ? WHERE src_path = ?", (old_time, old_time, str(src1.resolve())))
        self.cache_mgr.conn.commit()

        # Prune entries older than 30 days
        deleted = self.cache_mgr.prune()
        self.assertEqual(deleted, 1)
        self.assertEqual(self.cache_mgr.stats()["count"], 1)

    def test_clear_cache(self):
        dummy_db = self.dir_path / "custom_cache.sqlite"
        dummy_db.write_bytes(b"dummy")
        self.assertTrue(dummy_db.exists())
        
        removed = clear_cache(db_path=dummy_db)
        self.assertIn(str(dummy_db), removed)
        self.assertFalse(dummy_db.exists())


if __name__ == "__main__":
    unittest.main()
