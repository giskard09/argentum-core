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
import datetime
import hashlib
import os
import sqlite3
import time
import uuid
from typing import Iterable, Optional

GENESIS_AGENTS_DEFAULT = frozenset({"giskard-self", "lightning"})
# Enterprise agents with signed RSA — no daily/monthly rate limit
ENTERPRISE_AGENTS = frozenset(
    a.strip()
    for a in os.environ.get("ENTERPRISE_AGENTS", "").split(",")
    if a.strip()
)
RATE_LIMIT_DEFAULT = int(os.environ.get("TRAIL_DAILY_LIMIT", "100"))
MAX_LIMIT_PER_QUERY = 500
MONTHLY_LIMIT_FREE = 1000
SATS_PER_TRAIL = 300  # 300 sats ≈ $0.003 al precio actual

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS trails (
        trail_id        TEXT PRIMARY KEY,
        agent_id        TEXT NOT NULL,
        service         TEXT NOT NULL,
        operation       TEXT NOT NULL,
        timestamp       INTEGER NOT NULL,
        karma_at_time   INTEGER,
        success         INTEGER DEFAULT 1,
        signature_ref   TEXT NOT NULL,
        scope           TEXT,
        delegation_ref  TEXT,
        parent_trail_id TEXT,
        root_trail_id   TEXT,
        negotiation_ref TEXT,
        created_at      INTEGER DEFAULT (strftime('%s','now'))
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


_DDL_PAYG = """
    CREATE TABLE IF NOT EXISTS payg_accounts (
        api_key          TEXT PRIMARY KEY,
        agent_id         TEXT NOT NULL,
        tier             TEXT NOT NULL DEFAULT 'free',
        credit_trails    INTEGER NOT NULL DEFAULT 0,
        created_at       INTEGER NOT NULL,
        updated_at       INTEGER NOT NULL
    )
"""

_DDL_USDC_INTENTS = """
    CREATE TABLE IF NOT EXISTS payg_usdc_intents (
        intent_id        TEXT PRIMARY KEY,
        api_key          TEXT NOT NULL,
        from_address     TEXT NOT NULL,
        trails           INTEGER NOT NULL,
        usdc_amount      REAL NOT NULL,
        status           TEXT NOT NULL DEFAULT 'pending',
        tx_hash          TEXT,
        created_at       INTEGER NOT NULL,
        expires_at       INTEGER NOT NULL,
        fulfilled_at     INTEGER
    )
"""

_DDL_EXTERNAL_NONCES = """
    CREATE TABLE IF NOT EXISTS external_trail_nonces (
        action_ref  TEXT PRIMARY KEY,
        agent_id    TEXT NOT NULL,
        created_at  INTEGER NOT NULL
    )
"""

_DDL_BILLING = """
    CREATE TABLE IF NOT EXISTS billing_events (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        api_key      TEXT NOT NULL,
        agent_id     TEXT NOT NULL,
        trail_id     TEXT NOT NULL,
        amount_usd   REAL NOT NULL DEFAULT 0.003,
        billed_at    INTEGER NOT NULL,
        month_key    TEXT NOT NULL
    )
"""

TRAIL_UNIT_PRICE_USD: float = 0.003

_DDL_MIGRATIONS = [
    "ALTER TABLE trails ADD COLUMN scope TEXT",
    "ALTER TABLE trails ADD COLUMN delegation_ref TEXT",
    "ALTER TABLE trails ADD COLUMN parent_trail_id TEXT",
    "ALTER TABLE trails ADD COLUMN root_trail_id TEXT",
    "ALTER TABLE trails ADD COLUMN negotiation_ref TEXT",
    "ALTER TABLE trails ADD COLUMN action_ref TEXT",
    "ALTER TABLE trails ADD COLUMN tx_hash TEXT",
    "ALTER TABLE trails ADD COLUMN origin TEXT",
    "ALTER TABLE trails ADD COLUMN notes TEXT",
    "ALTER TABLE payg_accounts ADD COLUMN conformance_source TEXT",
    "ALTER TABLE payg_accounts ADD COLUMN notify_webhook TEXT",
    "ALTER TABLE trails ADD COLUMN anchor_status TEXT",
    "ALTER TABLE trails ADD COLUMN anchor_block INTEGER",
]


def init_db(db_path: str) -> None:
    """Idempotente — crea tabla e indices si no existen."""
    conn = _connect(db_path)
    try:
        for stmt in _DDL:
            conn.execute(stmt)
        conn.execute(_DDL_PAYG)
        conn.execute(_DDL_USDC_INTENTS)
        conn.execute(_DDL_EXTERNAL_NONCES)
        conn.execute(_DDL_BILLING)
        for stmt in _DDL_MIGRATIONS:
            try:
                conn.execute(stmt)
            except Exception:
                pass  # column already exists
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
    scope: Optional[str] = None,
    delegation_ref: Optional[str] = None,
    parent_trail_id: Optional[str] = None,
    root_trail_id: Optional[str] = None,
    negotiation_ref: Optional[str] = None,
    skip_monthly_limit: bool = False,
    origin: str = "internal",
) -> Optional[str]:
    """Graba un trail. Retorna trail_id o None si cae por rate limit o input invalido.

    Precondicion: la firma Ed25519 ya fue verificada por el caller.
    skip_monthly_limit: True cuando el caller ya consumió un crédito PAYG — omite el check mensual Free.
    parent_trail_id: ID del trail que generó éste (None si es raíz).
    root_trail_id:   ID del trail origen de la cadena (None si es raíz).
    negotiation_ref: SHA-256 hex del artefacto de negociación previo (opcional). No entra en el preimage de action_ref.
    origin: "nexus" para trails de clientes externos via /nexus/trail, "internal" para trails del sistema.
    """
    if not (agent_id and service and operation and nonce):
        return None

    genesis = frozenset(genesis_agents)
    if agent_id not in genesis and agent_id not in ENTERPRISE_AGENTS and rate_limit_cap > 0:
        used_today = count_trails_today(db_path, agent_id, now=now)
        if used_today >= rate_limit_cap:
            return None
        if not skip_monthly_limit:
            used_month = count_trails_this_month(db_path, agent_id, now=now)
            if used_month >= MONTHLY_LIMIT_FREE:
                return None

    trail_id = str(uuid.uuid4())
    ts = int(now if now is not None else time.time())
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO trails
              (trail_id, agent_id, service, operation, timestamp,
               karma_at_time, success, signature_ref, scope, delegation_ref,
               parent_trail_id, root_trail_id, negotiation_ref, origin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                scope,
                delegation_ref,
                parent_trail_id,
                root_trail_id,
                negotiation_ref,
                origin,
            ),
        )
        return trail_id
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    keys = row.keys()
    return {
        "trail_id": row["trail_id"],
        "agent_id": row["agent_id"],
        "service": row["service"],
        "operation": row["operation"],
        "timestamp": row["timestamp"],
        "karma_at_time": row["karma_at_time"],
        "success": bool(row["success"]),
        "signature_ref": row["signature_ref"],
        "scope": row["scope"] if "scope" in keys else None,
        "delegation_ref": row["delegation_ref"] if "delegation_ref" in keys else None,
        "parent_trail_id": row["parent_trail_id"] if "parent_trail_id" in keys else None,
        "root_trail_id": row["root_trail_id"] if "root_trail_id" in keys else None,
        "negotiation_ref": row["negotiation_ref"] if "negotiation_ref" in keys else None,
        "action_ref": row["action_ref"] if "action_ref" in keys else None,
        "tx_hash": row["tx_hash"] if "tx_hash" in keys else None,
        "origin": row["origin"] if "origin" in keys else None,
        "anchor_status": row["anchor_status"] if "anchor_status" in keys else None,
        "anchor_block": row["anchor_block"] if "anchor_block" in keys else None,
    }


def set_trail_tx_hash(db_path: str, trail_id: str, tx_hash: str) -> None:
    """Marca tx_hash y anchor_status='submitted' tras enviar la TX. No implica confirmación."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE trails SET tx_hash = ?, anchor_status = 'submitted' WHERE trail_id = ?",
            (tx_hash, trail_id),
        )
    finally:
        conn.close()


def confirm_trail_anchor(db_path: str, trail_id: str, block_number: int) -> None:
    """Marca anchor_status='anchored' y anchor_block tras confirmar receipt status==1 on-chain."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE trails SET anchor_status = 'anchored', anchor_block = ? WHERE trail_id = ?",
            (block_number, trail_id),
        )
    finally:
        conn.close()


def get_submitted_trails(db_path: str, limit: int = 50) -> list[dict]:
    """Retorna trails con tx_hash != null y anchor_status='submitted' para el poller."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT trail_id, agent_id, tx_hash FROM trails "
            "WHERE tx_hash IS NOT NULL AND anchor_status = 'submitted' "
            "ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{"trail_id": r["trail_id"], "agent_id": r["agent_id"], "tx_hash": r["tx_hash"]} for r in rows]
    finally:
        conn.close()


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
                   karma_at_time, success, signature_ref, scope, delegation_ref,
                   parent_trail_id, root_trail_id, negotiation_ref
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


def get_trail_by_id(db_path: str, trail_id: str) -> Optional[dict]:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT trail_id, agent_id, service, operation, timestamp,
                   karma_at_time, success, signature_ref, scope, delegation_ref,
                   parent_trail_id, root_trail_id, negotiation_ref, action_ref,
                   tx_hash, origin, anchor_status, anchor_block
            FROM trails WHERE trail_id=?
            """,
            (trail_id,),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def get_trail_graph(db_path: str, trail_id: str) -> Optional[dict]:
    """Devuelve el DAG completo a partir de trail_id como raíz o nodo.

    Primero resuelve la raíz real (sube por parent_trail_id hasta llegar a None),
    luego baja recursivamente por todos los descendientes.
    """
    root = get_trail_by_id(db_path, trail_id)
    if root is None:
        return None

    # subir hasta la raíz real
    current = root
    while current.get("parent_trail_id"):
        parent = get_trail_by_id(db_path, current["parent_trail_id"])
        if parent is None:
            break
        current = parent
    root = current

    def _build_node(t: dict) -> dict:
        conn = _connect(db_path)
        try:
            rows = conn.execute(
                "SELECT trail_id FROM trails WHERE parent_trail_id=?",
                (t["trail_id"],),
            ).fetchall()
        finally:
            conn.close()
        children = []
        for r in rows:
            child = get_trail_by_id(db_path, r["trail_id"])
            if child:
                children.append(_build_node(child))
        return {
            "trail_id": t["trail_id"],
            "agent_id": t["agent_id"],
            "karma_at_time": t["karma_at_time"],
            "attestation_count": 0,  # placeholder — join con actions si se requiere
            "parent_trail_id": t["parent_trail_id"],
            "children": children,
        }

    return {"root": _build_node(root)}


def verify_chain(db_path: str, trail_id: str) -> dict:
    """Valida integridad de la cadena desde trail_id hasta la raíz.

    Checks:
      (a) cada eslabón tiene signature_ref no nulo (proxy de firma válida)
      (b) delegation_ref es consistente con parent_trail_id donde ambos están presentes

    Retorna: { valid: bool, broken_at: trail_id | None, reason: str | None }
    """
    visited = set()
    current_id = trail_id
    while current_id:
        if current_id in visited:
            return {"valid": False, "broken_at": current_id, "reason": "cycle_detected"}
        visited.add(current_id)
        trail = get_trail_by_id(db_path, current_id)
        if trail is None:
            return {"valid": False, "broken_at": current_id, "reason": "trail_not_found"}
        if not trail.get("signature_ref"):
            return {"valid": False, "broken_at": current_id, "reason": "missing_signature_ref"}
        # si tiene parent_trail_id y delegation_ref, delegation_ref debe referenciar al parent
        if trail.get("parent_trail_id") and trail.get("delegation_ref"):
            if trail["parent_trail_id"] not in trail["delegation_ref"]:
                return {
                    "valid": False,
                    "broken_at": current_id,
                    "reason": "delegation_ref_parent_mismatch",
                }
        current_id = trail.get("parent_trail_id")
    return {"valid": True, "broken_at": None, "reason": None}


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


# ── MONTHLY USAGE (free tier) ─────────────────────────────────────────────────

def _year_month(now: Optional[int] = None) -> str:
    t = now if now is not None else int(time.time())
    dt = datetime.datetime.utcfromtimestamp(t)
    return dt.strftime("%Y-%m")


def _start_of_month_ts(now: Optional[int] = None) -> int:
    t = now if now is not None else int(time.time())
    dt = datetime.datetime.utcfromtimestamp(t)
    return int(datetime.datetime(dt.year, dt.month, 1).timestamp())


def count_trails_this_month(db_path: str, agent_id: str, now: Optional[int] = None) -> int:
    start = _start_of_month_ts(now)
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM trails WHERE agent_id=? AND timestamp>=? AND origin != 'pioneer'",
            (agent_id, start),
        ).fetchone()
        return int(row["n"]) if row else 0
    finally:
        conn.close()


# ── PAYG ACCOUNTS ─────────────────────────────────────────────────────────────

def get_payg_account_by_agent(db_path: str, agent_id: str) -> Optional[dict]:
    """Lookup PAYG account por agent_id. Retorna la cuenta con más créditos si hay varias."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT api_key, agent_id, tier, credit_trails, created_at, updated_at "
            "FROM payg_accounts WHERE agent_id=? AND tier='payg' AND credit_trails > 0 "
            "ORDER BY credit_trails DESC LIMIT 1",
            (agent_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_payg_account(db_path: str, api_key: str) -> Optional[dict]:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT api_key, agent_id, tier, credit_trails, conformance_source, created_at, updated_at "
            "FROM payg_accounts WHERE api_key=?",
            (api_key,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_payg_account(db_path: str, agent_id: str) -> str:
    api_key = uuid.uuid4().hex
    ts = int(time.time())
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO payg_accounts (api_key, agent_id, tier, credit_trails, created_at, updated_at) "
            "VALUES (?, ?, 'free', 0, ?, ?)",
            (api_key, agent_id, ts, ts),
        )
        return api_key
    finally:
        conn.close()


def topup_payg(db_path: str, api_key: str, trails: int) -> Optional[dict]:
    """Acredita N trails a una cuenta PAYG. Sube tier a 'payg' si estaba en 'free'."""
    ts = int(time.time())
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE payg_accounts SET credit_trails = credit_trails + ?, tier = 'payg', updated_at = ? "
            "WHERE api_key=?",
            (trails, ts, api_key),
        )
        row = conn.execute(
            "SELECT api_key, agent_id, tier, credit_trails FROM payg_accounts WHERE api_key=?",
            (api_key,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def consume_payg_credit(db_path: str, api_key: str) -> bool:
    """Descuenta 1 crédito. Retorna True si había créditos, False si no."""
    ts = int(time.time())
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT credit_trails FROM payg_accounts WHERE api_key=? AND tier='payg'",
            (api_key,),
        ).fetchone()
        if not row or row["credit_trails"] <= 0:
            return False
        conn.execute(
            "UPDATE payg_accounts SET credit_trails = credit_trails - 1, updated_at = ? WHERE api_key=?",
            (ts, api_key),
        )
        return True
    finally:
        conn.close()


def set_payg_webhook(db_path: str, api_key: str, url: Optional[str]) -> Optional[dict]:
    """Setea (o limpia, con url=None) el notify_webhook de una cuenta PAYG.

    El webhook recibe un POST {trail_id, tx_hash, anchored_at} cada vez que un trail
    de esta cuenta se ancla on-chain. Retorna la cuenta actualizada, o None si la
    api_key no existe.
    """
    ts = int(time.time())
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "UPDATE payg_accounts SET notify_webhook = ?, updated_at = ? WHERE api_key=?",
            (url or None, ts, api_key),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT api_key, agent_id, tier, credit_trails, notify_webhook FROM payg_accounts WHERE api_key=?",
            (api_key,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_notify_webhook(db_path: str, agent_id: str) -> Optional[str]:
    """Retorna el notify_webhook de la cuenta de un agent_id, o None si no hay.

    Si hay varias cuentas para el agent_id, devuelve la del webhook más reciente
    (updated_at DESC). Permissionless por diseño: el anchor notifica al dueño de la
    cuenta, no a quien dispara el trail.
    """
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT notify_webhook FROM payg_accounts "
            "WHERE agent_id=? AND notify_webhook IS NOT NULL AND notify_webhook != '' "
            "ORDER BY updated_at DESC LIMIT 1",
            (agent_id,),
        ).fetchone()
        return row["notify_webhook"] if row else None
    finally:
        conn.close()


# ── PAYG USDC INTENTS ─────────────────────────────────────────────────────────

USDC_INTENT_TTL = 3600  # 1 hora para completar el depósito
USDC_AMOUNT_TOLERANCE = 0.001  # tolerancia de $0.001 para rounding


def create_usdc_intent(db_path: str, api_key: str, from_address: str, trails: int) -> dict:
    """Registra un intent de depósito USDC. Retorna el intent creado."""
    intent_id = uuid.uuid4().hex
    usdc_amount = round(trails * 0.003, 4)
    now = int(time.time())
    expires_at = now + USDC_INTENT_TTL
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO payg_usdc_intents "
            "(intent_id, api_key, from_address, trails, usdc_amount, status, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)",
            (intent_id, api_key, from_address.lower(), trails, usdc_amount, now, expires_at),
        )
        return {
            "intent_id": intent_id,
            "api_key": api_key,
            "from_address": from_address.lower(),
            "trails": trails,
            "usdc_amount": usdc_amount,
            "status": "pending",
            "expires_at": expires_at,
        }
    finally:
        conn.close()


def get_pending_usdc_intents(db_path: str) -> list[dict]:
    """Retorna todos los intents pendientes no expirados."""
    now = int(time.time())
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM payg_usdc_intents WHERE status='pending' AND expires_at > ?",
            (now,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def fulfill_usdc_intent(db_path: str, intent_id: str, tx_hash: str) -> Optional[dict]:
    """Marca el intent como fulfilled y acredita los trails. Idempotente por intent_id."""
    now = int(time.time())
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM payg_usdc_intents WHERE intent_id=? AND status='pending'",
            (intent_id,),
        ).fetchone()
        if not row:
            return None  # ya procesado o no existe
        intent = dict(row)
        conn.execute(
            "UPDATE payg_usdc_intents SET status='fulfilled', tx_hash=?, fulfilled_at=? WHERE intent_id=?",
            (tx_hash, now, intent_id),
        )
        conn.execute(
            "UPDATE payg_accounts SET credit_trails = credit_trails + ?, tier = 'payg', updated_at = ? "
            "WHERE api_key=?",
            (intent["trails"], now, intent["api_key"]),
        )
        account = conn.execute(
            "SELECT api_key, agent_id, tier, credit_trails FROM payg_accounts WHERE api_key=?",
            (intent["api_key"],),
        ).fetchone()
        return {"intent": intent, "account": dict(account) if account else None, "tx_hash": tx_hash}
    finally:
        conn.close()


def has_external_nonce(db_path: str, action_ref: str) -> bool:
    """Retorna True si action_ref ya fue procesado (replay protection)."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT 1 FROM external_trail_nonces WHERE action_ref=?", (action_ref,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def record_external_nonce(db_path: str, action_ref: str, agent_id: str) -> None:
    """Registra action_ref como nonce consumido. Llama solo si has_external_nonce es False."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO external_trail_nonces (action_ref, agent_id, created_at) VALUES (?, ?, ?)",
            (action_ref, agent_id, int(time.time())),
        )
    finally:
        conn.close()


def set_conformance_source(db_path: str, api_key: str, source: str) -> Optional[dict]:
    """Setea conformance_source en una cuenta PAYG. Devuelve la cuenta actualizada o None."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE payg_accounts SET conformance_source = ?, updated_at = ? WHERE api_key = ?",
            (source or None, int(time.time()), api_key),
        )
        row = conn.execute(
            "SELECT api_key, agent_id, tier, credit_trails, conformance_source FROM payg_accounts WHERE api_key=?",
            (api_key,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

# ── BILLING ───────────────────────────────────────────────────────────────────

def record_billing_event(db_path: str, api_key: str, agent_id: str, trail_id: str) -> None:
    """Registra un evento de billing por trail. $0.003 USD por trail. Idempotente por trail_id."""
    import datetime as _dt
    now = int(time.time())
    month_key = _dt.datetime.utcfromtimestamp(now).strftime("%Y-%m")
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO billing_events (api_key, agent_id, trail_id, amount_usd, billed_at, month_key) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (api_key, agent_id, trail_id, TRAIL_UNIT_PRICE_USD, now, month_key),
        )
    finally:
        conn.close()


def get_billing_summary(db_path: str, month_key: str) -> list[dict]:
    """Retorna resumen de billing por api_key para el mes dado (formato 'YYYY-MM')."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT api_key, agent_id, COUNT(*) AS trail_count, SUM(amount_usd) AS total_usd "
            "FROM billing_events WHERE month_key = ? GROUP BY api_key ORDER BY total_usd DESC",
            (month_key,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
