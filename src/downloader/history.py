import sqlite3
import os
from datetime import datetime


class DownloadHistory:
    """Stores download records in a local SQLite database."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.expanduser("~"), ".media_downloader", "history.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT,
                    format_type TEXT NOT NULL,
                    codec TEXT,
                    quality TEXT,
                    output_path TEXT,
                    success INTEGER NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON downloads(created_at DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_url
                ON downloads(url)
            """)

    def add(self, url, format_type, success, title=None, codec=None, quality=None, output_path=None, error=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO downloads
                   (url, title, format_type, codec, quality, output_path, success, error, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    url,
                    title,
                    format_type,
                    codec,
                    quality,
                    output_path,
                    1 if success else 0,
                    error,
                    datetime.now().isoformat(),
                ),
            )

    def get_recent(self, limit=50):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM downloads ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def search(self, query, limit=50):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """SELECT * FROM downloads
                   WHERE url LIKE ? OR title LIKE ?
                   ORDER BY created_at DESC LIMIT ?""",
                (f"%{query}%", f"%{query}%", limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """SELECT
                       COUNT(*) as total,
                       SUM(success) as successful,
                       COUNT(*) - SUM(success) as failed,
                       SUM(CASE WHEN format_type = 'video' THEN 1 ELSE 0 END) as video_count,
                       SUM(CASE WHEN format_type = 'audio' THEN 1 ELSE 0 END) as audio_count
                   FROM downloads"""
            )
            row = cursor.fetchone()
            if row:
                return {
                    "total": row[0],
                    "successful": row[1],
                    "failed": row[2],
                    "video_count": row[3],
                    "audio_count": row[4],
                }
            return {"total": 0, "successful": 0, "failed": 0, "video_count": 0, "audio_count": 0}

    def clear(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM downloads")
