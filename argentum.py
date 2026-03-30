"""
ARGENTUM — Karma Economy for Agents and Humans

Good actions leave traces.
Traces accumulate wisdom.
Wisdom is witnessed by community, verified like open source.

The faith is not measurable. The action is.
"""

import json, uuid, httpx, sqlite3, hmac, hashlib
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

MEMORY_URL        = "http://localhost:8005"
MARKS_URL         = "http://localhost:8015"
MARKS_API_KEY     = "7e3755d34536917f113947b97e4d8c8fddbb7f44891e8952463681cbbb14bb6b"
ARBITRUM_CONTRACT = "0xD467CD1e34515d58F98f8Eb66C0892643ec86AD3"
ARGT_CONTRACT     = "0x42385c1038f3fec0ecCFBD4E794dE69935e89784"
DB_PATH           = Path(__file__).parent / "argentum.db"

PHOENIXD_URL      = "http://127.0.0.1:9740"
PHOENIXD_PASSWORD = "574fd439f0c07fc0c540f8245554440412c15ff5cfc0469a65f9879e70133c23"
WEBHOOK_SECRET    = "e3e9ee0bfb760d62c8051e10c0504efbedaef4c24d2982d98de22f72fedfa87c"

WEIGHT_THRESHOLD          = 2.0  # total weighted attestations needed to verify
KARMA_WEIGHT_BASE         = 50   # karma units for weight = 1.0
KARMA_WEIGHT_MIN          = 0.5  # floor — new users with marks still count
KARMA_WEIGHT_MAX          = 2.0  # ceiling — prevents single expert monopoly
MINIMUM_MARKS_TO_ATTEST   = 1   # v0.2 sybil resistance — governable upward
MINIMUM_KARMA_TO_ATTEST   = 0   # starts at 0; raise as network grows

# Genesis attestors — trusted at launch, exempt from marks/karma, weight 1.0
# Like a blockchain genesis block: explicit, documented, shrinks as network grows
GENESIS_ATTESTORS = {"lightning", "giskard-self"}

# kept for backwards compat in lightning webhook
ATTESTATIONS_NEEDED       = int(WEIGHT_THRESHOLD)

ACTION_TYPES = {
    "HELP":     {"name": "Help",     "desc": "Helped someone solve a real problem",             "karma": 10},
    "BUILD":    {"name": "Build",    "desc": "Built something open source that others use",     "karma": 20},
    "TEACH":    {"name": "Teach",    "desc": "Explained something publicly — docs, posts, talks","karma": 15},
    "FIX":      {"name": "Fix",      "desc": "Fixed a bug that was affecting others",           "karma": 12},
    "WITNESS":  {"name": "Witness",  "desc": "Attested to another entity's good action",        "karma": 5},
    "CONNECT":  {"name": "Connect",  "desc": "Introduced two entities that needed to meet",     "karma": 8},
    "RELEASE":  {"name": "Release",  "desc": "Released a tool or resource freely",              "karma": 25},
}

# ── DB ──────────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS actions (
        id           TEXT PRIMARY KEY,
        entity_id    TEXT NOT NULL,
        entity_name  TEXT NOT NULL,
        entity_type  TEXT NOT NULL,
        action_type  TEXT NOT NULL,
        description  TEXT NOT NULL,
        proof        TEXT,
        status       TEXT DEFAULT 'pending',
        karma_value  INTEGER DEFAULT 0,
        created_at   TEXT NOT NULL,
        verified_at  TEXT
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS attestations (
        id             TEXT PRIMARY KEY,
        action_id      TEXT NOT NULL,
        attester_id    TEXT NOT NULL,
        attester_name  TEXT NOT NULL,
        note           TEXT,
        created_at     TEXT NOT NULL,
        weight         REAL DEFAULT 1.0,
        FOREIGN KEY (action_id) REFERENCES actions(id)
    )""")
    # v0.3 migration — add weight column if missing
    try:
        conn.execute("ALTER TABLE attestations ADD COLUMN weight REAL DEFAULT 1.0")
        conn.commit()
    except Exception:
        pass  # column already exists
    conn.execute("""
    CREATE TABLE IF NOT EXISTS wisdom (
        entity_id           TEXT PRIMARY KEY,
        entity_name         TEXT NOT NULL,
        entity_type         TEXT NOT NULL,
        total_karma         INTEGER DEFAULT 0,
        verified_actions    INTEGER DEFAULT 0,
        attestations_given  INTEGER DEFAULT 0,
        last_action         TEXT
    )""")
    conn.commit()
    conn.close()

# ── APP ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ARGENTUM",
    description="Karma economy for agents and humans. Good actions leave traces.",
    version="0.2.0"
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.on_event("startup")
async def startup():
    init_db()

# ── MODELS ──────────────────────────────────────────────────────────────────

class ActionSubmit(BaseModel):
    entity_id:   str
    entity_name: str
    entity_type: str          # 'human' | 'agent'
    action_type: str
    description: str
    proof:       Optional[str] = None   # GitHub issue/PR/commit URL

class AttestRequest(BaseModel):
    attester_id:   str
    attester_name: str
    note:          Optional[str] = None

# ── HELPERS ─────────────────────────────────────────────────────────────────

def now():
    return datetime.now(timezone.utc).isoformat()

async def store_in_memory(content: str, entity_id: str, metadata: dict):
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            await c.post(f"{MEMORY_URL}/store_direct",
                json={"content": content, "agent_id": entity_id, "metadata": metadata})
    except Exception:
        pass  # memory is best-effort

async def get_attester_mark_count(attester_id: str) -> int:
    """Returns number of marks held by attester. 0 on any error (marks offline = fail open)."""
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{MARKS_URL}/marks/{attester_id}")
            if r.status_code == 200:
                data = r.json()
                return len(data.get("marks", []))
    except Exception:
        pass
    return 0

async def mint_mark(entity_id: str, entity_name: str, action_id: str, karma: int):
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            await c.post(f"{MARKS_URL}/mint",
                headers={"x-api-key": MARKS_API_KEY},
                json={
                    "agent_id":   entity_id,
                    "username":   entity_name,
                    "mark_type":  "BUILDER",
                    "note":       f"ARGENTUM action {action_id} verified — {karma} karma"
                })
    except Exception:
        pass  # marks are best-effort

def upsert_wisdom(conn, entity_id, entity_name, entity_type, karma_delta=0, action=False, attestation=False, last_action=None):
    existing = conn.execute("SELECT * FROM wisdom WHERE entity_id = ?", (entity_id,)).fetchone()
    if existing:
        conn.execute("""
        UPDATE wisdom SET
            total_karma        = total_karma + ?,
            verified_actions   = verified_actions + ?,
            attestations_given = attestations_given + ?,
            last_action        = COALESCE(?, last_action),
            entity_name        = ?
        WHERE entity_id = ?
        """, (karma_delta, 1 if action else 0, 1 if attestation else 0, last_action, entity_name, entity_id))
    else:
        conn.execute("""
        INSERT INTO wisdom (entity_id, entity_name, entity_type, total_karma, verified_actions, attestations_given, last_action)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (entity_id, entity_name, entity_type, karma_delta, 1 if action else 0, 1 if attestation else 0, last_action))

# ── ROUTES ──────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "name":             "ARGENTUM",
        "version":          "0.3.0",
        "contract":         ARBITRUM_CONTRACT,
        "philosophy":       "The faith is not measurable. The action is.",
        "genesis_attestors": list(GENESIS_ATTESTORS),
        "weight_threshold": WEIGHT_THRESHOLD,
        "sybil_resistance": "marks + karma-weighted attestations"
    }

@app.get("/action_types")
def get_action_types():
    return ACTION_TYPES

@limiter.limit("10/minute")
@app.post("/action/submit")
async def submit_action(request: Request, req: ActionSubmit):
    if req.action_type not in ACTION_TYPES:
        raise HTTPException(400, f"Unknown action_type. Valid: {list(ACTION_TYPES)}")

    action_id  = str(uuid.uuid4())[:8]
    karma      = ACTION_TYPES[req.action_type]["karma"]
    created_at = now()

    conn = get_db()
    conn.execute("""
    INSERT INTO actions (id, entity_id, entity_name, entity_type, action_type, description, proof, karma_value, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (action_id, req.entity_id, req.entity_name, req.entity_type,
          req.action_type, req.description, req.proof, karma, created_at))
    conn.commit()
    conn.close()

    await store_in_memory(
        content=f"[ARGENTUM] Action submitted: {req.action_type} — {req.description}",
        entity_id=req.entity_id,
        metadata={"type": "argentum_action", "action_id": action_id, "status": "pending"}
    )

    return {
        "action_id":          action_id,
        "status":             "pending",
        "attestations_needed": ATTESTATIONS_NEEDED,
        "karma_on_verify":    karma,
        "message":            f"Action submitted. Needs {ATTESTATIONS_NEEDED} attestations to be verified."
    }

@limiter.limit("20/minute")
@app.post("/action/{action_id}/attest")
async def attest_action(request: Request, action_id: str, req: AttestRequest):
    conn = get_db()

    action = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    if not action:
        raise HTTPException(404, "Action not found")
    if action["status"] == "verified":
        raise HTTPException(400, "Action already verified")
    if action["entity_id"] == req.attester_id:
        raise HTTPException(400, "Cannot attest your own action")

    existing = conn.execute(
        "SELECT id FROM attestations WHERE action_id = ? AND attester_id = ?",
        (action_id, req.attester_id)
    ).fetchone()
    if existing:
        raise HTTPException(400, "Already attested")

    # Genesis attestors are exempt from marks/karma — trusted at launch
    if req.attester_id in GENESIS_ATTESTORS:
        attester_karma = 0
        attest_weight = 1.0
    else:
        # v0.2 sybil resistance — marks required
        mark_count = await get_attester_mark_count(req.attester_id)
        if mark_count < MINIMUM_MARKS_TO_ATTEST:
            conn.close()
            raise HTTPException(403, f"Attestor needs at least {MINIMUM_MARKS_TO_ATTEST} Mark to attest. "
                                     f"{req.attester_id} has {mark_count}. Earn marks through verified actions.")
        attester_wisdom = conn.execute(
            "SELECT total_karma FROM wisdom WHERE entity_id = ?", (req.attester_id,)
        ).fetchone()
        attester_karma = attester_wisdom["total_karma"] if attester_wisdom else 0
        if attester_karma < MINIMUM_KARMA_TO_ATTEST:
            conn.close()
            raise HTTPException(403, f"Attestor needs at least {MINIMUM_KARMA_TO_ATTEST} karma to attest. "
                                     f"{req.attester_id} has {attester_karma}.")
        # v0.3 karma-weighted attestation weight
        attest_weight = max(KARMA_WEIGHT_MIN, min(KARMA_WEIGHT_MAX, attester_karma / KARMA_WEIGHT_BASE))

    attest_id = str(uuid.uuid4())[:8]
    conn.execute("""
    INSERT INTO attestations (id, action_id, attester_id, attester_name, note, created_at, weight)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (attest_id, action_id, req.attester_id, req.attester_name, req.note, now(), attest_weight))

    total_weight = conn.execute(
        "SELECT COALESCE(SUM(weight), 0) as w FROM attestations WHERE action_id = ?", (action_id,)
    ).fetchone()["w"]
    count = conn.execute(
        "SELECT COUNT(*) as n FROM attestations WHERE action_id = ?", (action_id,)
    ).fetchone()["n"]

    verified_now = False
    if total_weight >= WEIGHT_THRESHOLD:
        verified_at = now()
        conn.execute("UPDATE actions SET status = 'verified', verified_at = ? WHERE id = ?",
                     (verified_at, action_id))
        upsert_wisdom(conn, action["entity_id"], action["entity_name"], action["entity_type"],
                      karma_delta=action["karma_value"], action=True, last_action=verified_at)
        verified_now = True

    upsert_wisdom(conn, req.attester_id, req.attester_name, "unknown",
                  karma_delta=ACTION_TYPES["WITNESS"]["karma"], attestation=True)

    conn.commit()
    conn.close()

    if verified_now:
        await store_in_memory(
            content=f"[ARGENTUM] Action VERIFIED: {action['action_type']} — {action['description']} ({action['karma_value']} karma)",
            entity_id=action["entity_id"],
            metadata={"type": "argentum_verified", "action_id": action_id}
        )
        await mint_mark(action["entity_id"], action["entity_name"], action_id, action["karma_value"])

    return {
        "attestation_id":       attest_id,
        "action_id":            action_id,
        "attestations_so_far":  count,
        "total_weight":         round(total_weight, 2),
        "weight_threshold":     WEIGHT_THRESHOLD,
        "this_attestation_weight": round(attest_weight, 2),
        "verified":             verified_now,
        "witness_karma_earned": ACTION_TYPES["WITNESS"]["karma"],
        "attester_karma":       attester_karma
    }

@app.get("/actions")
def list_actions(status: Optional[str] = None, limit: int = 50):
    conn = get_db()
    if status:
        rows = conn.execute(
            "SELECT * FROM actions WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM actions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()

    result = []
    for r in rows:
        a = dict(r)
        a["attestation_count"] = conn.execute(
            "SELECT COUNT(*) as n FROM attestations WHERE action_id = ?", (a["id"],)
        ).fetchone()["n"]
        a["total_weight"] = round(conn.execute(
            "SELECT COALESCE(SUM(weight), 0) as w FROM attestations WHERE action_id = ?", (a["id"],)
        ).fetchone()["w"], 2)
        a["weight_threshold"] = WEIGHT_THRESHOLD
        result.append(a)
    conn.close()
    return result

@app.get("/action/{action_id}")
def get_action(action_id: str):
    conn = get_db()
    action = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    if not action:
        raise HTTPException(404, "Action not found")
    a = dict(action)
    a["attestations"] = [dict(r) for r in conn.execute(
        "SELECT * FROM attestations WHERE action_id = ?", (action_id,)
    ).fetchall()]
    a["total_weight"] = conn.execute(
        "SELECT COALESCE(SUM(weight), 0) as w FROM attestations WHERE action_id = ?", (action_id,)
    ).fetchone()["w"]
    a["weight_threshold"] = WEIGHT_THRESHOLD
    conn.close()
    return a

@app.get("/entity/{entity_id}/trace")
def get_trace(entity_id: str):
    conn = get_db()
    wisdom = conn.execute("SELECT * FROM wisdom WHERE entity_id = ?", (entity_id,)).fetchone()
    actions = [dict(r) for r in conn.execute(
        "SELECT * FROM actions WHERE entity_id = ? ORDER BY created_at DESC",
        (entity_id,)
    ).fetchall()]
    attested = [dict(r) for r in conn.execute(
        "SELECT a.*, ac.action_type, ac.description, ac.entity_name as beneficiary "
        "FROM attestations a JOIN actions ac ON a.action_id = ac.id "
        "WHERE a.attester_id = ? ORDER BY a.created_at DESC",
        (entity_id,)
    ).fetchall()]
    conn.close()
    return {
        "entity_id":  entity_id,
        "wisdom":     dict(wisdom) if wisdom else None,
        "actions":    actions,
        "witnessed":  attested
    }

@app.get("/commons")
def get_commons(limit: int = 20):
    conn = get_db()
    verified = [dict(r) for r in conn.execute(
        "SELECT * FROM actions WHERE status = 'verified' ORDER BY verified_at DESC LIMIT ?",
        (limit,)
    ).fetchall()]
    conn.close()
    return verified

@app.get("/leaderboard")
def get_leaderboard(limit: int = 20):
    conn = get_db()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM wisdom ORDER BY total_karma DESC LIMIT ?", (limit,)
    ).fetchall()]
    conn.close()
    return rows

@app.get("/stats")
def get_stats():
    conn = get_db()
    total_actions    = conn.execute("SELECT COUNT(*) as n FROM actions").fetchone()["n"]
    verified_actions = conn.execute("SELECT COUNT(*) as n FROM actions WHERE status='verified'").fetchone()["n"]
    pending_actions  = conn.execute("SELECT COUNT(*) as n FROM actions WHERE status='pending'").fetchone()["n"]
    total_karma      = conn.execute("SELECT SUM(total_karma) as s FROM wisdom").fetchone()["s"] or 0
    entities         = conn.execute("SELECT COUNT(*) as n FROM wisdom").fetchone()["n"]
    agents           = conn.execute("SELECT COUNT(*) as n FROM wisdom WHERE entity_type='agent'").fetchone()["n"]
    humans           = conn.execute("SELECT COUNT(*) as n FROM wisdom WHERE entity_type='human'").fetchone()["n"]
    conn.close()
    return {
        "total_actions":    total_actions,
        "verified_actions": verified_actions,
        "pending_actions":  pending_actions,
        "total_karma":      total_karma,
        "entities":         entities,
        "agents":           agents,
        "humans":           humans,
        "contract":         ARBITRUM_CONTRACT,
        "argt_contract":    ARGT_CONTRACT
    }

# ── LIGHTNING ────────────────────────────────────────────────────────────────

async def phoenixd_create_invoice(amount_sat: int, description: str, external_id: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{PHOENIXD_URL}/createinvoice",
            auth=("", PHOENIXD_PASSWORD),
            data={"amountSat": amount_sat, "description": description, "externalId": external_id}
        )
        r.raise_for_status()
        return r.json()

@limiter.limit("5/minute")
@app.post("/action/{action_id}/invoice")
async def create_action_invoice(request: Request, action_id: str):
    """Create a Lightning invoice to stake sats on an action submission."""
    conn = get_db()
    action = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    conn.close()
    if not action:
        raise HTTPException(404, "Action not found")

    # 1 sat per karma point as commitment stake
    amount_sat = max(10, action["karma_value"])
    inv = await phoenixd_create_invoice(
        amount_sat=amount_sat,
        description=f"ARGENTUM action {action_id} — {action['action_type']} by {action['entity_name']}",
        external_id=f"action:{action_id}"
    )
    return {
        "action_id":    action_id,
        "amount_sat":   amount_sat,
        "invoice":      inv["serialized"],
        "payment_hash": inv["paymentHash"],
        "note":         "Payment stakes your action. Refunded as ARGT karma when verified."
    }

@app.post("/payment/webhook")
async def payment_webhook(request: Request):
    """
    Receives phoenixd webhook on incoming payment.
    Validates HMAC signature, then processes based on externalId.
    externalId format: 'action:{action_id}'
    """
    body = await request.body()

    # Verify HMAC-SHA256 signature
    sig_header = request.headers.get("X-Phoenix-Signature", "")
    expected = hmac.new(
        WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(sig_header, expected):
        raise HTTPException(401, "Invalid webhook signature")

    data = json.loads(body)

    # Only process paid incoming payments
    if data.get("type") != "payment_received":
        return {"status": "ignored"}

    external_id = data.get("externalId", "")
    amount_sat  = data.get("amountSat", 0)
    payment_hash = data.get("paymentHash", "")

    await store_in_memory(
        content=f"[ARGENTUM] Lightning payment received: {amount_sat} sats, externalId={external_id}",
        entity_id="giskard-self",
        metadata={"type": "ln_payment", "amount_sat": amount_sat, "payment_hash": payment_hash}
    )

    if external_id.startswith("action:"):
        action_id = external_id.split(":", 1)[1]
        conn = get_db()
        action = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
        conn.close()
        if action and action["status"] == "pending":
            # Auto-attest from the Lightning payment (counts as one attestation from "lightning")
            try:
                conn = get_db()
                existing = conn.execute(
                    "SELECT id FROM attestations WHERE action_id = ? AND attester_id = ?",
                    (action_id, "lightning")
                ).fetchone()
                if not existing:
                    attest_id = str(uuid.uuid4())[:8]
                    conn.execute("""
                    INSERT INTO attestations (id, action_id, attester_id, attester_name, note, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (attest_id, action_id, "lightning", "Lightning Network",
                          f"Staked {amount_sat} sats — hash {payment_hash[:16]}…", now()))

                    count = conn.execute(
                        "SELECT COUNT(*) as n FROM attestations WHERE action_id = ?", (action_id,)
                    ).fetchone()["n"]

                    if count >= ATTESTATIONS_NEEDED:
                        verified_at = now()
                        conn.execute("UPDATE actions SET status = 'verified', verified_at = ? WHERE id = ?",
                                     (verified_at, action_id))
                        upsert_wisdom(conn, action["entity_id"], action["entity_name"], action["entity_type"],
                                      karma_delta=action["karma_value"], action=True, last_action=verified_at)

                    conn.commit()
                conn.close()
            except Exception as e:
                pass

    return {"status": "ok", "amount_sat": amount_sat, "external_id": external_id}

@app.get("/lightning/balance")
async def get_ln_balance():
    """Current phoenixd balance."""
    async with httpx.AsyncClient(timeout=8) as c:
        r = await c.get(f"{PHOENIXD_URL}/getbalance", auth=("", PHOENIXD_PASSWORD))
        return r.json()

@app.get("/lightning/payments")
async def get_ln_payments(limit: int = 20):
    """Recent incoming Lightning payments."""
    async with httpx.AsyncClient(timeout=8) as c:
        r = await c.get(
            f"{PHOENIXD_URL}/payments/incoming",
            auth=("", PHOENIXD_PASSWORD),
            params={"limit": limit}
        )
        return r.json()
