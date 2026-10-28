import json
import sqlite3
import time
from pathlib import Path


class MovieCache:
    def __init__(self, path: Path, enabled: bool = True):
        self.path = path
        self.enabled = enabled
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("CREATE TABLE IF NOT EXISTS movies (url TEXT PRIMARY KEY, fetched REAL NOT NULL, payload TEXT NOT NULL)")

    def get(self, url: str) -> dict | None:
        if not self.enabled:
            return None
        row = self.connection.execute("SELECT fetched, payload FROM movies WHERE url = ?", (url,)).fetchone()
        if not row or time.time() - row[0] > 7 * 86400:
            return None
        try:
            return json.loads(row[1])
        except ValueError:
            return None

    def put(self, url: str, value: dict):
        if self.enabled:
            self.connection.execute("INSERT OR REPLACE INTO movies VALUES (?, ?, ?)", (url, time.time(), json.dumps(value, ensure_ascii=False)))
            self.connection.commit()

    def close(self):
        self.connection.close()
