"""Independent effect store for the UNGUARDED_RETRY case.

A minimal SQLite store representing the tool's real side effect: a
counter increment plus an effect row, committed in a single transaction.
This module is read independently, after the run, by the receipt builder
-- it has no knowledge of crewAI's retry state and cannot be told "it
actually only happened once" by anything upstream.
"""

from __future__ import annotations

import os
import sqlite3
import uuid


class EffectStore:
    def __init__(self, path: str) -> None:
        self.path = path
        if os.path.exists(path):
            os.remove(path)
        self._conn = sqlite3.connect(path)
        self._conn.execute(
            "CREATE TABLE counter (id INTEGER PRIMARY KEY CHECK (id = 1), value INTEGER NOT NULL)"
        )
        self._conn.execute("INSERT INTO counter (id, value) VALUES (1, 0)")
        self._conn.execute(
            """
            CREATE TABLE effects (
                effect_id TEXT PRIMARY KEY,
                logical_action_id TEXT NOT NULL,
                attempt_no INTEGER NOT NULL,
                counter_value_after INTEGER NOT NULL
            )
            """
        )
        self._conn.commit()

    def apply_effect(self, logical_action_id: str, attempt_no: int) -> str:
        """The tool's real side effect: increment counter + write effect row,
        in one transaction. Returns the effect_id. This is the commit point
        the spec calls out: everything up to and including this method
        returning is 'the effect has committed'."""
        effect_id = str(uuid.uuid4())
        cur = self._conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("UPDATE counter SET value = value + 1 WHERE id = 1")
        new_value = cur.execute("SELECT value FROM counter WHERE id = 1").fetchone()[0]
        cur.execute(
            "INSERT INTO effects (effect_id, logical_action_id, attempt_no, counter_value_after) "
            "VALUES (?, ?, ?, ?)",
            (effect_id, logical_action_id, attempt_no, new_value),
        )
        self._conn.commit()
        return effect_id

    def read_independent(self, logical_action_id: str) -> dict:
        """Read-only, independent observation -- run after the harness exits,
        against a fresh connection, exactly as the spec's receipt fields
        require (nullable, never inferred)."""
        try:
            conn = sqlite3.connect(self.path)
            counter_value = conn.execute(
                "SELECT value FROM counter WHERE id = 1"
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT effect_id, attempt_no, counter_value_after FROM effects "
                "WHERE logical_action_id = ? ORDER BY attempt_no",
                (logical_action_id,),
            ).fetchall()
            conn.close()
            return {
                "readable": True,
                "counter_value": counter_value,
                "effect_count": len(rows),
                "effect_ids": [r[0] for r in rows],
                "attempts_committed": [r[1] for r in rows],
            }
        except Exception:
            return {
                "readable": False,
                "counter_value": None,
                "effect_count": None,
                "effect_ids": None,
                "attempts_committed": None,
            }

    def close(self) -> None:
        self._conn.close()
