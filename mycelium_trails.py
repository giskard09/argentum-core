"""
mycelium_trails — rastros firmados de uso de servicios Mycelium.

Cada trail registra el HECHO de que un agente uso un servicio (agent_id,
service, operation, timestamp) despues de una firma Ed25519 valida. Nunca
registra payload ni contenido — solo metadata.

Disenio:
  - Persistencia distribuida (cada server sqlite propio)
  - Funciones puras sobre db_path; sin estado global
  - Rate limit default 100 trails/agent/dia; genesis exentos
  - Lectura publica (no hay funciones de borrado expuestas)

Ver ~/Downloads/CODIGO - MYCELIUM TRAILS.txt para diseno completo.
"""
import hashlib
import sqlite3
import time
import uuid
from typing import Iterable, Optional

GENESIS_AGENTS_DEFAULT = frozenset({"giskard-self", "lightning"})
RATE_LIMIT_DEFAULT = 100
MAX_LIMIT_PER_QUERY = 500

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS trails (
        trail_id       TEXT PRIMARY KEY,
        agent_id       TEXT NOT NULL,
        service        TEXT NOT NULL,
        operation      TEXT NOT NULL,
        timestamp      INTEGER NOT NULL,
        karma_at_time  INTEGER,
        success        INTEGER DEFAULT 1,
        signature_ref  TEXT NOT NULL,
        created_at     INTEGER DEFAULT (strftime('%s','now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_trails_agent ON trails(agent_id, timestamp DESC)",
    "CREATE INDEX IF NOT EXISTS idx_trails_service_time ON trails(service, timestamp DESC)",
]


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(db_path: str) -> None:
    """Idempotente — crea tabla e indices si no existen."""
    conn = _connect(db_path)
    try:
        for stmt in _DDL:
            conn.execute(stmt)
    finally:
        conn.close()


def _sig_ref(nonce: str) -> str:
    return hashlib.sha256(nonce.encode("utf-8")).hexdigest()


def _start_of_day_ts(now: Optional[int] = None) -> int:
    t = now if now is not None else int(time.time())
    return t - (t % 86400)


def count_trails_today(
    db_path: str,
    agent_id: str,
    now: Optional[int] = None,
) -> int:
    start = _start_of_day_ts(now)
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM trails WHERE agent_id=? AND timestamp>=?",
            (agent_id, start),
        ).fetchone()
        return int(row["n"]) if row else 0
    finally:
        conn.close()


def record_trail(
    db_path: str,
    agent_id: str,
    service: str,
    operation: str,
    nonce: str,
    karma_at_time: Optional[int] = None,
    success: bool = True,
    rate_limit_cap: int = RATE_LIMIT_DEFAULT,
    genesis_agents: Iterable[str] = GENESIS_AGENTS_DEFAULT,
    now: Optional[int] = None,
) -> Optional[str]:
    """Graba un trail. Retorna trail_id o None si cae por rate limit o input invalido.

    Precondicion: la firma Ed25519 ya fue verificada por el caller.
    """
    if not (agent_id and service and operation and nonce):
        return None

    genesis = frozenset(genesis_agents)
    if agent_id not in genesis and rate_limit_cap > 0:
        used = count_trails_today(db_path, agent_id, now=now)
        if used >= rate_limit_cap:
            return None

    trail_id = str(uuid.uuid4())
    ts = int(now if now is not None else time.time())
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO trails
              (trail_id, agent_id, service, operation, timestamp,
               karma_at_time, success, signature_ref)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trail_id,
                agent_id,
                service,
                operation,
                ts,
                karma_at_time,
                1 if success else 0,
                _sig_ref(nonce),
            ),
        )
        return trail_id
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "trail_id": row["trail_id"],
        "agent_id": row["agent_id"],
        "service": row["service"],
        "operation": row["operation"],
        "timestamp": row["timestamp"],
        "karma_at_time": row["karma_at_time"],
        "success": bool(row["success"]),
        "signature_ref": row["signature_ref"],
    }


def list_trails_by_agent(
    db_path: str,
    agent_id: str,
    limit: int = 50,
) -> list:
    limit = max(1, min(int(limit), MAX_LIMIT_PER_QUERY))
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT trail_id, agent_id, service, operation, timestamp,
                   karma_at_time, success, signature_ref
            FROM trails
            WHERE agent_id=?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (agent_id, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def list_trails_by_service(
    db_path: str,
    service: Optional[str] = None,
    since_ts: int = 0,
    limit: int = 200,
) -> list:
    limit = max(1, min(int(limit), MAX_LIMIT_PER_QUERY))
    conn = _connect(db_path)
    try:
        if service:
            rows = conn.execute(
                """
                SELECT trail_id, agent_id, service, operation, timestamp,
                       karma_at_time, success, signature_ref
                FROM trails
                WHERE service=? AND timestamp>=?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (service, int(since_ts), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT trail_id, agent_id, service, operation, timestamp,
                       karma_at_time, success, signature_ref
                FROM trails
                WHERE timestamp>=?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (int(since_ts), limit),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()
