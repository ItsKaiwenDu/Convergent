"""
Convergent: Content-Addressable Conversion Cache (Checksum Skip)
- Fast blake2b fingerprinting (partial for large files)
- SQLite persistence at ~/.convergent_cache.sqlite
- Validates via src mtime/size + hash + output existence + params
- Automatic Time-To-Live (TTL) expiration & LRU pruning
"""

import hashlib
import json
import os
import sqlite3
import time
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple

CACHE_DB_PATH = Path.home() / ".convergent_cache.sqlite"
# Also support legacy .db name -> migrate / check both
CACHE_DB_ALT = Path.home() / ".convergent_cache.db"

DEFAULT_TTL_DAYS = 30.0  # Default cache expiration (30 days)
MAX_CACHE_ENTRIES = 50000  # Cap cache entries to prevent unbounded growth

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
    out_size INTEGER,
    params_hash TEXT,
    created_at REAL,
    last_accessed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_src_path ON entries(src_path);
CREATE INDEX IF NOT EXISTS idx_last_accessed ON entries(last_accessed_at);
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
    def __init__(self, db_path: Path = CACHE_DB_PATH, ttl_days: Optional[float] = None):
        self.db_path = db_path
        # Support migration from alt path if main doesn't exist
        if not db_path.exists() and CACHE_DB_ALT.exists():
            try:
                # Use alt as db_path for backward compat
                self.db_path = CACHE_DB_ALT
            except Exception:
                pass

        if ttl_days is None:
            env_ttl = os.environ.get("CONVERGENT_CACHE_TTL_DAYS")
            if env_ttl:
                try:
                    self.ttl_days = float(env_ttl)
                except ValueError:
                    self.ttl_days = DEFAULT_TTL_DAYS
            else:
                self.ttl_days = DEFAULT_TTL_DAYS
        else:
            self.ttl_days = float(ttl_days)

        try:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.execute("PRAGMA journal_mode=WAL;")
        except (sqlite3.OperationalError, PermissionError):
            self.db_path = Path(tempfile.gettempdir()) / ".convergent_cache.sqlite"
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.executescript(_SCHEMA)

        # Migration: Add out_size column if upgrading from older schema
        try:
            self.conn.execute("ALTER TABLE entries ADD COLUMN out_size INTEGER;")
            self.conn.commit()
        except Exception:
            pass

        # Migration: Add last_accessed_at column if upgrading from older schema
        try:
            self.conn.execute("ALTER TABLE entries ADD COLUMN last_accessed_at REAL;")
            self.conn.commit()
        except Exception:
            pass

        self.conn.commit()

        # Opportunistic prune on startup (clean up expired & keep size bounded)
        try:
            self.prune()
        except Exception:
            pass

    def close(self):
        try:
            self.conn.commit()
            self.conn.close()
        except Exception:
            pass

    def delete_entry(self, key: str):
        """Removes a single cache record."""
        try:
            self.conn.execute("DELETE FROM entries WHERE key=?", (key,))
            self.conn.commit()
        except Exception:
            pass

    def _get_entry(self, key: str) -> Optional[Dict]:
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT key, src_path, src_hash, src_mtime, src_size, out_path, out_mtime, out_size, params_hash, created_at, last_accessed_at FROM entries WHERE key=?",
                (key,),
            )
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
                    "out_size": row[7],
                    "params_hash": row[8],
                    "created_at": row[9],
                    "last_accessed_at": row[10] if len(row) > 10 and row[10] is not None else row[9],
                }
        except Exception:
            pass
        return None

    def is_cached_valid(self, src_path: Path, out_path: Path, params: Dict) -> Tuple[bool, str]:
        """
        Checks if cache entry is valid.
        Returns (is_valid, reason_or_hash_preview)
        - Valid if: entry exists, not expired by TTL, src mtime/size matches (or hash matches), and out_path exists.
        - Updates last_accessed_at timestamp on valid cache hit.
        """
        key = make_cache_key(src_path, params)
        entry = self._get_entry(key)
        if not entry:
            return False, "miss"

        # Check TTL expiration (if ttl_days > 0)
        if self.ttl_days > 0:
            access_time = entry.get("last_accessed_at") or entry.get("created_at") or 0.0
            if time.time() - access_time > self.ttl_days * 86400:
                self.delete_entry(key)
                return False, "expired"

        # Check output existence (file or dir for PDF->images)
        try:
            if not out_path.exists():
                return False, "output missing"
        except Exception:
            return False, "output missing"

        # Check output file/dir size and content integrity
        try:
            if out_path.is_file():
                cur_out_stat = out_path.stat()
                if cur_out_stat.st_size == 0:
                    return False, "output empty"
                if entry.get("out_size") is not None and entry["out_size"] > 0:
                    if cur_out_stat.st_size != entry["out_size"]:
                        return False, "output size mismatch"
            elif out_path.is_dir():
                dir_items = list(out_path.iterdir())
                if not dir_items:
                    return False, "output empty dir"
                if entry.get("out_size") is not None and entry["out_size"] > 0:
                    if len(dir_items) != entry["out_size"]:
                        return False, "output item count mismatch"
        except Exception:
            return False, "output stat failed"

        try:
            cur_stat = src_path.stat()
            cur_mtime = cur_stat.st_mtime
            cur_size = cur_stat.st_size
        except Exception:
            return False, "src stat failed"

        # Fast path: if mtime and size identical to cached, assume valid (no need to re-hash)
        if entry["src_mtime"] is not None and entry["src_size"] is not None:
            if abs(entry["src_mtime"] - cur_mtime) < 0.001 and entry["src_size"] == cur_size:
                self._touch_access(key)
                hash_preview = entry["src_hash"][:8] if entry["src_hash"] else "...."
                return True, f"blake2b:{hash_preview}..."

        # Slow path: compute current file hash (partial for large)
        cur_hash, _, _ = get_file_fingerprint(src_path)
        if not cur_hash:
            return False, "hash fail"

        if cur_hash == entry["src_hash"]:
            self._touch_access(key)
            hash_preview = cur_hash[:8]
            return True, f"blake2b:{hash_preview}..."

        return False, "hash mismatch"

    def _touch_access(self, key: str):
        """Update last_accessed_at on cache hit."""
        try:
            now = time.time()
            self.conn.execute("UPDATE entries SET last_accessed_at = ? WHERE key = ?", (now, key))
            self.conn.commit()
        except Exception:
            pass

    def update_output_path(self, old_out_path: Path, new_out_path: Path):
        """Updates the recorded output path and stats for entries when output is renamed or relocated."""
        try:
            old_str = str(old_out_path.resolve())
            new_str = str(new_out_path.resolve())
            new_mtime = time.time()
            new_size = None
            if new_out_path.exists():
                stat = new_out_path.stat()
                new_mtime = stat.st_mtime
                if new_out_path.is_file():
                    new_size = stat.st_size
                elif new_out_path.is_dir():
                    new_size = len(list(new_out_path.iterdir()))

            self.conn.execute(
                "UPDATE entries SET out_path = ?, out_mtime = ?, out_size = ? WHERE out_path = ?",
                (new_str, new_mtime, new_size, old_str),
            )
            self.conn.commit()
        except Exception:
            pass

    def save(self, src_path: Path, out_path: Path, params: Dict):
        """Upsert cache entry after successful conversion."""
        try:
            src_hash, src_mtime, src_size = get_file_fingerprint(src_path)
            if not src_hash:
                return
            try:
                out_stat = out_path.stat()
                out_mtime = out_stat.st_mtime
                if out_path.is_file():
                    out_size = out_stat.st_size
                elif out_path.is_dir():
                    out_size = len(list(out_path.iterdir()))
                else:
                    out_size = None
            except Exception:
                out_mtime = time.time()
                out_size = None

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
                (key, src_path, src_hash, src_mtime, src_size, out_path, out_mtime, out_size, params_hash, created_at, last_accessed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (key, resolved_src, src_hash, src_mtime, src_size, resolved_out, out_mtime, out_size, params_hash, now, now),
            )
            self.conn.commit()
        except Exception:
            # Cache failures should never break conversion
            pass

    def prune(self, ttl_days: Optional[float] = None, max_entries: int = MAX_CACHE_ENTRIES) -> int:
        """
        Prunes expired cache entries and caps total entries via LRU.
        Returns number of deleted records.
        """
        deleted = 0
        effective_ttl = self.ttl_days if ttl_days is None else float(ttl_days)
        try:
            if effective_ttl > 0:
                cutoff = time.time() - (effective_ttl * 86400)
                cur = self.conn.cursor()
                cur.execute(
                    "DELETE FROM entries WHERE COALESCE(last_accessed_at, created_at) < ?",
                    (cutoff,),
                )
                deleted += cur.rowcount
                self.conn.commit()

            if max_entries > 0:
                cur = self.conn.cursor()
                cur.execute("SELECT COUNT(*) FROM entries;")
                total = cur.fetchone()[0]
                if total > max_entries:
                    excess = total - max_entries
                    cur.execute(
                        """
                        DELETE FROM entries WHERE key IN (
                            SELECT key FROM entries ORDER BY COALESCE(last_accessed_at, created_at) ASC LIMIT ?
                        )
                        """,
                        (excess,),
                    )
                    deleted += cur.rowcount
                    self.conn.commit()
        except Exception:
            pass
        return deleted

    def clear(self):
        try:
            self.conn.execute("DELETE FROM entries;")
            self.conn.commit()
        except Exception:
            pass

    def stats(self) -> Dict:
        """Returns statistics on cache database, TTL, and records."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT COUNT(*), MIN(COALESCE(last_accessed_at, created_at)), MAX(COALESCE(last_accessed_at, created_at)) FROM entries;"
            )
            row = cur.fetchone()
            count = row[0] if row else 0
            oldest_ts = row[1] if row and row[1] else None
            newest_ts = row[2] if row and row[2] else None

            size_bytes = 0
            try:
                if self.db_path.exists():
                    size_bytes = self.db_path.stat().st_size
            except Exception:
                pass

            def _format_size(b: int) -> str:
                if b < 1024:
                    return f"{b} B"
                elif b < 1024 * 1024:
                    return f"{b / 1024:.1f} KB"
                else:
                    return f"{b / (1024 * 1024):.2f} MB"

            def _format_ts(ts: Optional[float]) -> str:
                if not ts:
                    return "none"
                return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

            return {
                "count": count,
                "db_path": str(self.db_path),
                "size_bytes": size_bytes,
                "size_formatted": _format_size(size_bytes),
                "ttl_days": self.ttl_days if self.ttl_days > 0 else "disabled",
                "oldest_entry": _format_ts(oldest_ts),
                "newest_entry": _format_ts(newest_ts),
            }
        except Exception:
            return {"count": 0, "db_path": str(self.db_path), "ttl_days": self.ttl_days}


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

