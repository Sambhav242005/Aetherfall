from __future__ import annotations

import json
import sqlite3

import numpy as np


class VectorStore:
    def __init__(self, conn: sqlite3.Connection, dim: int) -> None:
        self._conn = conn
        self._dim = dim

    def add(self, entry_id: str, vector: list[float]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO bible_vectors (entry_id, dim, vector) VALUES (?, ?, ?)",
            (entry_id, self._dim, json.dumps(vector)),
        )
        self._conn.commit()

    def query(self, vector: list[float], k: int = 5) -> list[tuple[str, float]]:
        rows = self._conn.execute("SELECT entry_id, vector FROM bible_vectors").fetchall()
        if not rows:
            return []
        q = np.asarray(vector, dtype=float)
        qn = np.linalg.norm(q) or 1.0
        scored: list[tuple[str, float]] = []
        for row in rows:
            v = np.asarray(json.loads(row["vector"]), dtype=float)
            vn = np.linalg.norm(v) or 1.0
            scored.append((row["entry_id"], float(np.dot(q, v) / (qn * vn))))
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:k]
