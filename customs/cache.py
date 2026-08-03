"""
Convergent: Content-Addressable Conversion Cache (Checksum Skip)
- Fast blake2b fingerprinting (partial for large files)
- SQLite persistence at ~/.convergent_cache.sqlite
- Validates via src mtime/size + hash + output existence
"""

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

CACHE_DB_PATH = Path.home() / ".convergent_cache.sqlite"
# Also support legacy .db name -> migrate / check both
CACHE_DB_ALT = Path.home() / ".convergent_cache.db"

PARTIAL_THRESHOLD = 10 * 1024 * 1024  # 10 MB – above this, hash head+tail
HEAD_TAIL_SIZE = 1 * 1024 * 1024  # 1 MB

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    key TEXT PRIMARY KEY,
    src_path TEXT,
    src_hash TEXT,
    src_mtime REAL,
    src_size INTEGER,
    out_path TEXT,
    out_mtime REAL,
    params_hash TEXT,
    created_at REAL
);
CREATE INDEX IF NOT EXISTS idx_src_path ON entries(src_path);
"""


def _blake2b_hex(data: bytes, digest_size: int = 16) -> str:
    return hashlib.blake2b(data, digest_size=digest_size).hexdigest()


def _params_to_string(params: Dict) -> str:
    # Stable canonical representation
    # Ensure keys sorted and values normalized
    normalized = {}
    for k, v in sorted(params.items()):
        if v is None:
            normalized[k] = ""
        else:
            normalized[k] = str(v)
    return "|".join(f"{k}={normalized[k]}" for k in sorted(normalized.keys()))


def get_params_hash(params: Dict) -> str:
    s = _params_to_string(params)
    return _blake2b_hex(s.encode("utf-8"), digest_size=16)


def get_file_fingerprint(path: Path) -> Tuple[str, float, int]:
    """
    Returns (hash, mtime, size) for a file.
    - For small files (< threshold): hash full file
    - For large files: hash first 1MB + last 1MB + size str
    Uses blake2b fast, digest_size 16 (128-bit) for speed.
    """
    try:
        stat = path.stat()
        mtime = stat.st_mtime
        size = stat.st_size
    except Exception:
        return "", 0.0, 0

    try:
        h = hashlib.blake2b(digest_size=16)
        if size <= PARTIAL_THRESHOLD:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
        else:
            with open(path, "rb") as f:
                head = f.read(HEAD_TAIL_SIZE)
                h.update(head)
                # tail
                try:
                    f.seek(max(0, size - HEAD_TAIL_SIZE))
                    tail = f.read(HEAD_TAIL_SIZE)
                    h.update(tail)
                except Exception:
                    pass
            # Include size to differentiate files with same head/tail
            h.update(str(size).encode("utf-8"))
        return h.hexdigest(), mtime, size
    except Exception:
        # If hashing fails (permission, etc.), fallback to mtime+size hash
        fallback = f"{mtime}:{size}".encode("utf-8")
        return _blake2b_hex(fallback, digest_size=16), mtime, size


def make_cache_key(src_path: Path, params: Dict) -> str:
    """
    Deterministic cache key from absolute source path + params.
    This enables per-path caching; content hash is stored as value for mutation detection.
    """
    try:
        resolved = str(src_path.resolve())
    except Exception:
        resolved = str(src_path)
    params_str = _params_to_string(params)
    composite = f"{resolved}|{params_str}"
    return _blake2b_hex(composite.encode("utf-8"), digest_size=16)


def make_content_key(src_hash: str, params: Dict) -> str:
    """Optional content-addressable key for dedup across paths (not primary)."""
    params_h = get_params_hash(params)
    return _blake2b_hex(f"{src_hash}|{params_h}".encode("utf-8"), digest_size=16)


class CacheManager:
    def __init__(self, db_path: Path = CACHE_DB_PATH):
        self.db_path = db_path
        # Support migration from alt path if main doesn't exist
        if not db_path.exists() and CACHE_DB_ALT.exists():
            try:
                # Use alt as db_path for backward compat
                self.db_path = CACHE_DB_ALT
            except Exception:
                pass
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self):
        try:
            self.conn.commit()
            self.conn.close()
        except Exception:
            pass

    def _get_entry(self, key: str) -> Optional[Dict]:
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT key, src_path, src_hash, src_mtime, src_size, out_path, out_mtime, params_hash, created_at FROM entries WHERE key=?", (key,))
            row = cur.fetchone()
            if row:
                return {
                    "key": row[0],
                    "src_path": row[1],
                    "src_hash": row[2],
                    "src_mtime": row[3],
                    "src_size": row[4],
                    "out_path": row[5],
                    "out_mtime": row[6],
                    "params_hash": row[7],
                    "created_at": row[8],
                }
        except Exception:
            pass
        return None

    def is_cached_valid(self, src_path: Path, out_path: Path, params: Dict) -> Tuple[bool, str]:
        """
        Checks if cache entry is valid.
        Returns (is_valid, reason_or_hash_preview)
        - Valid if: entry exists, src mtime/size matches (or hash matches), and out_path exists.
        - For speed: if mtime and size match DB, skip recomputing hash.
        """
        key = make_cache_key(src_path, params)
        entry = self._get_entry(key)
        if not entry:
            return False, "miss"

        # Check output existence (file or dir for PDF->images)
        try:
            if not out_path.exists():
                return False, "output missing"
        except Exception:
            return False, "output missing"

        try:
            cur_stat = src_path.stat()
            cur_mtime = cur_stat.st_mtime
            cur_size = cur_stat.st_size
        except Exception:
            return False, "src stat failed"

        # Fast path: if mtime and size identical to cached, assume valid (no need to re-hash)
        # This makes 10k-file scans very fast (stat only)
        if entry["src_mtime"] is not None and entry["src_size"] is not None:
            if abs(entry["src_mtime"] - cur_mtime) < 0.001 and entry["src_size"] == cur_size:
                # Also check out_mtime is newer than src? optional
                try:
                    out_mtime = out_path.stat().st_mtime
                    # If output is newer than source cached time, valid
                    # (We don't enforce strict out_mtime match, just existence)
                    if out_mtime >= entry["out_mtime"] or entry["out_mtime"] is not None:
                        hash_preview = entry["src_hash"][:8] if entry["src_hash"] else "...."
                        return True, f"blake2b:{hash_preview}..."
                except Exception:
                    pass
                # Still valid even if out_mtime check skipped
                hash_preview = entry["src_hash"][:8] if entry["src_hash"] else "...."
                return True, f"blake2b:{hash_preview}..."

        # Slow path: compute current file hash (partial for large)
        cur_hash, _, _ = get_file_fingerprint(src_path)
        if not cur_hash:
            return False, "hash fail"

        if cur_hash == entry["src_hash"]:
            hash_preview = cur_hash[:8]
            return True, f"blake2b:{hash_preview}..."

        return False, "hash mismatch"

    def save(self, src_path: Path, out_path: Path, params: Dict):
        """Upsert cache entry after successful conversion."""
        try:
            src_hash, src_mtime, src_size = get_file_fingerprint(src_path)
            if not src_hash:
                return
            try:
                out_mtime = out_path.stat().st_mtime
            except Exception:
                out_mtime = time.time()

            key = make_cache_key(src_path, params)
            params_hash = get_params_hash(params)
            now = time.time()
            try:
                resolved_src = str(src_path.resolve())
            except Exception:
                resolved_src = str(src_path)
            try:
                resolved_out = str(out_path.resolve())
            except Exception:
                resolved_out = str(out_path)

            self.conn.execute(
                """
                INSERT OR REPLACE INTO entries
                (key, src_path, src_hash, src_mtime, src_size, out_path, out_mtime, params_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (key, resolved_src, src_hash, src_mtime, src_size, resolved_out, out_mtime, params_hash, now),
            )
            self.conn.commit()
        except Exception:
            # Cache failures should never break conversion
            pass

    def clear(self):
        try:
            self.conn.execute("DELETE FROM entries;")
            self.conn.commit()
        except Exception:
            pass

    def stats(self) -> Dict:
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT COUNT(*) FROM entries;")
            count = cur.fetchone()[0]
            return {"count": count, "db_path": str(self.db_path)}
        except Exception:
            return {"count": 0, "db_path": str(self.db_path)}


def clear_cache(db_path: Path = CACHE_DB_PATH):
    """Utility to delete DB files."""
    removed = []
    for p in [CACHE_DB_PATH, CACHE_DB_ALT, db_path]:
        try:
            if p.exists():
                p.unlink()
                removed.append(str(p))
        except Exception:
            pass
    # Also clear WAL files
    for p in [CACHE_DB_PATH, CACHE_DB_ALT]:
        for suffix in ["-wal", "-shm"]:
            wal = Path(str(p) + suffix)
            try:
                if wal.exists():
                    wal.unlink()
            except Exception:
                pass
    return removed
