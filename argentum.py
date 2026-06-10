"""
ARGENTUM — Karma Economy for Agents and Humans

Good actions leave traces.
Traces accumulate wisdom.
Wisdom is witnessed by community, verified like open source.

The faith is not measurable. The action is.
"""

import asyncio
import html as _html
import json, uuid, time, httpx, sqlite3, hmac, hashlib, os
_started_at = time.time()
import mycelium_trails
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from pathlib import Path
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import agent_signing
import threading as _threading
try:
    import arb_pay as _arb_pay
    _ARB_PAY_OK = True
except ImportError:
    _ARB_PAY_OK = False
try:
    import smtp_notify as _smtp
    _SMTP_OK = True
except ImportError:
    _SMTP_OK = False

limiter = Limiter(key_func=get_remote_address)

MEMORY_URL        = "http://localhost:8005"
MARKS_URL         = "http://localhost:8015"
MARKS_API_KEY        = os.environ.get("MARKS_API_KEY", "")
ARGENTUM_SIGNING_KEY = os.environ.get("ARGENTUM_SIGNING_KEY", "")
ARGENTUM_VERIFY_KEY  = os.environ.get("ARGENTUM_VERIFY_KEY", "")
ARGENTUM_BASE_URL    = "https://argentum-api.rgiskard.xyz"
ARBITRUM_CONTRACT = "0xe40E376cD32b03E3084F9E0d646155D0Ba0A63ae"
PAYG_WALLET       = os.environ.get("PAYG_WALLET", "")  # RAMA wallet — PAYG receiver Arbitrum mainnet
ARB_RPC           = os.environ.get("ARB_RPC", "https://arb1.arbitrum.io/rpc")
USDC_CONTRACT_ARB = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"  # USDC native Arbitrum One
ARGT_CONTRACT     = "0x42385c1038f3fec0ecCFBD4E794dE69935e89784"
DB_PATH           = Path(__file__).parent / "argentum.db"
TRAILS_DB         = str(Path(__file__).parent / "trails.db")
SERVICE_NAME      = "argentum"

PHOENIXD_URL      = "http://127.0.0.1:9740"
PHOENIXD_PASSWORD = os.environ.get("PHOENIXD_PASSWORD", "")
WEBHOOK_SECRET    = os.environ.get("WEBHOOK_SECRET", "")

# Conformance tier weights — karma delta per verified trail by source
CONFORMANCE_TIER: dict[str, float] = {
    "nexus":   1.0,   # giskard-payments, our contract — anchor on-chain required
    "aps":     0.7,   # AEOESS / APS — conformance-verified
    "nobulex": 0.7,   # Gogani/Nobulex — conformance-verified
}
KARMA_DEFAULT_WEIGHT: float = 0.2   # valid action_ref, unverified implementation

WEIGHT_THRESHOLD          = 2.0  # total weighted attestations needed to verify
KARMA_WEIGHT_BASE         = 50   # karma units for weight = 1.0
KARMA_WEIGHT_MIN          = 0.5  # floor — new users with marks still count
KARMA_WEIGHT_MAX          = 2.0  # ceiling — prevents single expert monopoly
MINIMUM_MARKS_TO_ATTEST   = 1   # v0.2 sybil resistance — governable upward
MINIMUM_KARMA_TO_ATTEST   = 0   # starts at 0; raise as network grows

# Genesis attestors — trusted at launch, exempt from marks/karma, weight 1.0
# Like a blockchain genesis block: explicit, documented, shrinks as network grows
GENESIS_ATTESTORS = {"lightning", "giskard-self"}
MAX_ATTESTATIONS_PER_DAY  = 5    # rate limit — max attestations per attester per day
MINIMUM_KARMA_TO_DISPUTE  = 10   # karma required to open a Kleros dispute
KLEROS_RULING_SECRET      = os.environ.get("KLEROS_RULING_SECRET", "")

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
        id             TEXT PRIMARY KEY,
        entity_id      TEXT NOT NULL,
        entity_name    TEXT NOT NULL,
        entity_type    TEXT NOT NULL,
        action_type    TEXT NOT NULL,
        description    TEXT NOT NULL,
        proof          TEXT,
        status         TEXT DEFAULT 'pending',
        karma_value    INTEGER DEFAULT 0,
        created_at     TEXT NOT NULL,
        verified_at    TEXT,
        system_version TEXT
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
    # v0.4 migration — add signed column to actions (Ed25519 rollout)
    try:
        conn.execute("ALTER TABLE actions ADD COLUMN signed INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass  # column already exists
    # v0.5 migration — add system_version to actions (GAP-A: audit trail versioning)
    try:
        conn.execute("ALTER TABLE actions ADD COLUMN system_version TEXT")
        conn.commit()
    except Exception:
        pass  # column already exists
    # v0.6 migration — total_karma INTEGER → REAL for fractional conformance weights
    try:
        conn.execute("ALTER TABLE wisdom ADD COLUMN total_karma_real REAL DEFAULT 0.0")
        conn.execute("UPDATE wisdom SET total_karma_real = CAST(total_karma AS REAL) WHERE total_karma_real = 0.0")
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
    conn.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id           TEXT PRIMARY KEY,
        action_id    TEXT NOT NULL,
        reporter_id  TEXT NOT NULL,
        reason       TEXT NOT NULL,
        status       TEXT DEFAULT 'open',
        created_at   TEXT NOT NULL,
        resolved_at  TEXT,
        FOREIGN KEY (action_id) REFERENCES actions(id)
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS trails (
        id              TEXT PRIMARY KEY,
        author_id       TEXT NOT NULL,
        author_name     TEXT NOT NULL,
        name            TEXT NOT NULL,
        description     TEXT NOT NULL,
        steps           TEXT NOT NULL,    -- JSON list of {service, tool, note}
        price_sats      INTEGER NOT NULL,
        output_schema   TEXT,             -- optional JSON schema
        created_at      TEXT NOT NULL,
        executions      INTEGER DEFAULT 0,
        success_count   INTEGER DEFAULT 0,
        rating_sum      INTEGER DEFAULT 0,
        rating_count    INTEGER DEFAULT 0
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS trail_executions (
        id            TEXT PRIMARY KEY,
        trail_id      TEXT NOT NULL,
        executor_id   TEXT NOT NULL,
        executor_name TEXT NOT NULL,
        status        TEXT NOT NULL,      -- success | fail
        output_hash   TEXT,
        payment_hash  TEXT,
        rating        INTEGER,            -- 1..5, optional
        created_at    TEXT NOT NULL,
        FOREIGN KEY (trail_id) REFERENCES trails(id)
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS disputes (
        id                TEXT PRIMARY KEY,
        action_id         TEXT NOT NULL,
        reporter_id       TEXT NOT NULL,
        reason            TEXT NOT NULL,
        kleros_dispute_id INTEGER,
        status            TEXT DEFAULT 'pending',
        ruling            INTEGER,
        created_at        TEXT NOT NULL,
        resolved_at       TEXT,
        FOREIGN KEY (action_id) REFERENCES actions(id)
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS config_snapshots (
        id                        TEXT PRIMARY KEY,
        captured_at               TEXT NOT NULL,
        system_version            TEXT NOT NULL,
        weight_threshold          REAL NOT NULL,
        karma_weight_base         INTEGER NOT NULL,
        karma_weight_min          REAL NOT NULL,
        karma_weight_max          REAL NOT NULL,
        minimum_marks_to_attest   INTEGER NOT NULL,
        minimum_karma_to_attest   INTEGER NOT NULL,
        max_attestations_per_day  INTEGER NOT NULL,
        minimum_karma_to_dispute  INTEGER NOT NULL
    )""")
    conn.commit()
    conn.close()


def capture_config_snapshot() -> str:
    """Graba un snapshot de los parámetros activos en config_snapshots.

    Llamado al startup. Permite a auditores correlacionar cada trail con
    los parámetros de sistema que estaban activos en ese momento.
    Retorna el id del snapshot creado.
    """
    conn = get_db()
    try:
        snapshot_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO config_snapshots
              (id, captured_at, system_version, weight_threshold,
               karma_weight_base, karma_weight_min, karma_weight_max,
               minimum_marks_to_attest, minimum_karma_to_attest,
               max_attestations_per_day, minimum_karma_to_dispute)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id, now, SYSTEM_VERSION,
                WEIGHT_THRESHOLD, KARMA_WEIGHT_BASE,
                KARMA_WEIGHT_MIN, KARMA_WEIGHT_MAX,
                MINIMUM_MARKS_TO_ATTEST, MINIMUM_KARMA_TO_ATTEST,
                MAX_ATTESTATIONS_PER_DAY, MINIMUM_KARMA_TO_DISPUTE,
            ),
        )
        conn.commit()
        return snapshot_id
    finally:
        conn.close()


# ── APP ─────────────────────────────────────────────────────────────────────

SYSTEM_VERSION = "0.5.0"

app = FastAPI(
    title="ARGENTUM",
    description="Karma economy for agents and humans. Good actions leave traces.",
    version=SYSTEM_VERSION
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

async def _usdc_poller():
    """Monitorea transfers USDC a PAYG_WALLET y creditea intents pendientes."""
    USDC_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    seen_tx: set[str] = set()

    while True:
        await asyncio.sleep(60)
        if not PAYG_WALLET:
            continue
        try:
            wallet_topic = "0x" + PAYG_WALLET[2:].lower().zfill(64)
            payload = {
                "jsonrpc": "2.0", "id": 1, "method": "eth_getLogs",
                "params": [{
                    "address": USDC_CONTRACT_ARB,
                    "topics": [USDC_TRANSFER_TOPIC, None, wallet_topic],
                    "fromBlock": hex(int(time.time() - 7200) // 12 + 185000000),  # ~2h atrás aprox
                    "toBlock": "latest",
                }],
            }
            async with httpx.AsyncClient(timeout=15) as client:
                rpc_resp = await client.post(ARB_RPC, json=payload)
                logs = rpc_resp.json().get("result", [])

            intents = mycelium_trails.get_pending_usdc_intents(TRAILS_DB)
            if not intents or not logs:
                continue

            intents_by_addr = {i["from_address"]: i for i in intents}

            for log in logs:
                tx_hash = log.get("transactionHash", "")
                if tx_hash in seen_tx:
                    continue
                topics = log.get("topics", [])
                if len(topics) < 3:
                    continue
                from_addr = "0x" + topics[1][-40:]
                raw_amount = int(log.get("data", "0x0"), 16)
                usdc_amount = raw_amount / 1_000_000  # USDC tiene 6 decimales

                intent = intents_by_addr.get(from_addr.lower())
                if not intent:
                    continue
                expected = intent["usdc_amount"]
                if abs(usdc_amount - expected) > mycelium_trails.USDC_AMOUNT_TOLERANCE:
                    continue

                result = mycelium_trails.fulfill_usdc_intent(TRAILS_DB, intent["intent_id"], tx_hash)
                if result:
                    seen_tx.add(tx_hash)
        except Exception:
            pass  # poller nunca muere por error puntual


@app.on_event("startup")
async def startup():
    init_db()
    capture_config_snapshot()
    mycelium_trails.init_db(TRAILS_DB)
    asyncio.create_task(_usdc_poller())

# ── MODELS ──────────────────────────────────────────────────────────────────

class ActionSubmit(BaseModel):
    entity_id:   str
    entity_name: str
    entity_type: str          # 'human' | 'agent'
    action_type: str
    description: str
    proof:       Optional[str] = None   # GitHub issue/PR/commit URL
    signature:   Optional[str] = None
    timestamp:   Optional[int] = None
    nonce:       Optional[str] = None

class AttestRequest(BaseModel):
    attester_id:   str
    attester_name: str
    note:          Optional[str] = None
    signature:     Optional[str] = None
    timestamp:     Optional[int] = None
    nonce:         Optional[str] = None

class ReportRequest(BaseModel):
    reporter_id: str
    reason:      str
    signature:   Optional[str] = None
    timestamp:   Optional[int] = None
    nonce:       Optional[str] = None

class SlashConfirmRequest(BaseModel):
    confirmer_id: str  # must be genesis attestor

class DisputeRequest(BaseModel):
    reporter_id: str
    reason:      str
    signature:   Optional[str] = None
    timestamp:   Optional[int] = None
    nonce:       Optional[str] = None

class KlerosRulingRequest(BaseModel):
    action_id: str
    ruling:    int  # 1 = slash (reporter wins), 2 = clear (poster wins), 0 = refused to arbitrate

class TrailRegister(BaseModel):
    author_id:     str
    author_name:   str
    name:          str
    description:   str
    steps:         list   # [{"service": "search", "tool": "search_web", "note": "..."}]
    price_sats:    int
    output_schema: Optional[dict] = None
    signature:     Optional[str] = None
    timestamp:     Optional[int] = None
    nonce:         Optional[str] = None

class TrailExecution(BaseModel):
    executor_id:   str
    executor_name: str
    status:        str            # 'success' | 'fail'
    output_hash:   Optional[str] = None
    payment_hash:  Optional[str] = None
    signature:     Optional[str] = None
    timestamp:     Optional[int] = None
    nonce:         Optional[str] = None

class TrailRating(BaseModel):
    execution_id: str
    rating:       int             # 1..5
    rater_id:     Optional[str] = None
    signature:    Optional[str] = None
    timestamp:    Optional[int] = None
    nonce:        Optional[str] = None

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

def upsert_wisdom(conn, entity_id, entity_name, entity_type, karma_delta=0.0, action=False, attestation=False, last_action=None):
    delta = float(karma_delta)
    existing = conn.execute("SELECT * FROM wisdom WHERE entity_id = ?", (entity_id,)).fetchone()
    if existing:
        conn.execute("""
        UPDATE wisdom SET
            total_karma        = CAST(COALESCE(total_karma_real, total_karma) + ? AS INTEGER),
            total_karma_real   = COALESCE(total_karma_real, CAST(total_karma AS REAL)) + ?,
            verified_actions   = verified_actions + ?,
            attestations_given = attestations_given + ?,
            last_action        = COALESCE(?, last_action),
            entity_name        = ?
        WHERE entity_id = ?
        """, (delta, delta, 1 if action else 0, 1 if attestation else 0, last_action, entity_name, entity_id))
    else:
        conn.execute("""
        INSERT INTO wisdom (entity_id, entity_name, entity_type, total_karma, total_karma_real, verified_actions, attestations_given, last_action)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (entity_id, entity_name, entity_type, int(delta), delta, 1 if action else 0, 1 if attestation else 0, last_action))

# ── ROUTES ──────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "name":             "ARGENTUM",
        "version":          "0.4.0",
        "contract":         ARBITRUM_CONTRACT,
        "philosophy":       "The faith is not measurable. The action is.",
        "genesis_attestors": list(GENESIS_ATTESTORS),
        "weight_threshold": WEIGHT_THRESHOLD,
        "sybil_resistance": "marks + karma-weighted attestations"
    }

@app.get("/docs/integration", response_class=HTMLResponse)
def integration_guide():
    """Guía de integración genérica — pública, sin auth."""
    md_path = Path(__file__).parent / "docs" / "guides" / "integration.md"
    try:
        raw = md_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(404, "integration guide not found")

    # Render minimal markdown → HTML (headers, code blocks, tables, inline code, bold)
    import re as _re

    def _escape(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    lines = raw.split("\n")
    html_lines: list[str] = []
    in_code = False
    code_buf: list[str] = []
    code_lang = ""

    for line in lines:
        if line.startswith("```"):
            if not in_code:
                in_code = True
                code_lang = line[3:].strip()
                code_buf = []
            else:
                in_code = False
                body = _escape("\n".join(code_buf))
                html_lines.append(f'<pre><code class="lang-{_escape(code_lang)}">{body}</code></pre>')
            continue
        if in_code:
            code_buf.append(line)
            continue

        # Tables
        if line.startswith("|") and "|" in line[1:]:
            if line.replace("|", "").replace("-", "").replace(" ", "") == "":
                continue  # separator row
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not html_lines or not html_lines[-1].endswith("</tr>"):
                html_lines.append('<table>')
                row = "".join(f"<th>{_escape(c)}</th>" for c in cells)
            else:
                row = "".join(f"<td>{_escape(c)}</td>" for c in cells)
            html_lines.append(f"<tr>{row}</tr>")
            continue
        if html_lines and html_lines[-1].startswith("<tr>") and not line.startswith("|"):
            html_lines.append("</table>")

        # Headers
        m = _re.match(r'^(#{1,4})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            text = _escape(m.group(2))
            html_lines.append(f"<h{level}>{text}</h{level}>")
            continue

        # HR
        if line.strip() in ("---", "***", "___"):
            html_lines.append("<hr>")
            continue

        # Inline formatting
        def _inline(s: str) -> str:
            s = _re.sub(r'`([^`]+)`', lambda x: f'<code>{_escape(x.group(1))}</code>', s)
            s = _re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
            s = _re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', s)
            return s

        if line.strip() == "":
            html_lines.append("<br>")
        else:
            html_lines.append(f"<p>{_inline(_escape(line))}</p>")

    content = "\n".join(html_lines)
    return HTMLResponse(content=f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mycelium Trails — Integration Guide</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
       font-size:15px;line-height:1.7;padding:40px 20px;max-width:820px;margin:0 auto}}
  h1{{font-size:1.8rem;color:#f8fafc;margin:0 0 8px}}
  h2{{font-size:1.2rem;color:#94a3b8;margin:36px 0 12px;text-transform:uppercase;letter-spacing:.06em;font-weight:600}}
  h3{{font-size:1rem;color:#cbd5e1;margin:20px 0 8px}}
  h4{{font-size:.9rem;color:#94a3b8;margin:16px 0 6px}}
  p{{margin:6px 0;color:#cbd5e1}}
  hr{{border:none;border-top:1px solid #1e293b;margin:28px 0}}
  pre{{background:#1e293b;border:1px solid #334155;border-radius:6px;padding:16px;overflow-x:auto;margin:12px 0}}
  code{{font-family:'JetBrains Mono','Fira Code',monospace;font-size:.82rem;color:#7dd3fc}}
  pre code{{color:#e2e8f0}}
  table{{width:100%;border-collapse:collapse;margin:12px 0;font-size:.85rem}}
  th{{background:#1e293b;color:#94a3b8;padding:8px 12px;text-align:left;border-bottom:1px solid #334155}}
  td{{padding:8px 12px;border-bottom:1px solid #1e293b;color:#cbd5e1}}
  a{{color:#38bdf8;text-decoration:none}}
  a:hover{{text-decoration:underline}}
  strong{{color:#f1f5f9}}
  br{{display:block;margin:4px 0}}
</style>
</head><body>{content}</body></html>""")


@app.get("/status")
def get_status():
    """Estado del servicio: nombre, versión, uptime, puerto, salud, dependencias.
    Read-only, gratis. Útil para monitoreo y health checks."""
    try:
        conn = sqlite3.connect(DB_PATH)
        n_actions = conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
        conn.close()
        healthy = True
    except Exception:
        n_actions = None
        healthy = False
    return {
        "service": "argentum-core",
        "version": "0.4.0",
        "port": 8017,
        "uptime_seconds": int(time.time() - _started_at),
        "healthy": healthy,
        "dependencies": ["sqlite", "giskard-marks", "arbitrum-rpc"],
        "total_actions": n_actions,
        "weight_threshold": WEIGHT_THRESHOLD,
    }


@app.get("/action_types")
def get_action_types():
    return ACTION_TYPES

def _verify_agent_signature(agent_id: str, signature, timestamp, nonce) -> bool:
    """Returns True only if all fields present and verification passes.
    Unsigned requests return False silently — caller decides the policy."""
    if not (signature and timestamp and nonce):
        return False
    try:
        return agent_signing.verify_request(
            agent_id=agent_id,
            signature_b64=signature,
            timestamp=int(timestamp),
            nonce=nonce,
        )
    except Exception:
        return False


@app.post("/action/submit")
@limiter.limit("10/minute")
async def submit_action(request: Request, req: ActionSubmit):
    if req.action_type not in ACTION_TYPES:
        raise HTTPException(400, f"Unknown action_type. Valid: {list(ACTION_TYPES)}")

    action_id  = str(uuid.uuid4())[:8]
    karma      = ACTION_TYPES[req.action_type]["karma"]
    created_at = now()
    signed     = _verify_agent_signature(req.entity_id, req.signature, req.timestamp, req.nonce)

    conn = get_db()
    conn.execute("""
    INSERT INTO actions (id, entity_id, entity_name, entity_type, action_type, description, proof, karma_value, created_at, signed, system_version)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (action_id, req.entity_id, req.entity_name, req.entity_type,
          req.action_type, req.description, req.proof, karma, created_at, 1 if signed else 0, SYSTEM_VERSION))
    conn.commit()
    conn.close()

    await store_in_memory(
        content=f"[ARGENTUM] Action submitted: {req.action_type} — {req.description}",
        entity_id=req.entity_id,
        metadata={"type": "argentum_action", "action_id": action_id, "status": "pending", "signed": signed}
    )

    try:
        mycelium_trails.record_trail(
            TRAILS_DB,
            agent_id=req.entity_id,
            service=SERVICE_NAME,
            operation="submit_action",
            nonce=req.nonce or action_id,
            karma_at_time=None,
            success=True,
        )
    except Exception:
        pass

    return {
        "action_id":          action_id,
        "status":             "pending",
        "attestations_needed": ATTESTATIONS_NEEDED,
        "karma_on_verify":    karma,
        "signed":             signed,
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

    # Rate limiting — max attestations per day (genesis attestors exempt)
    if req.attester_id not in GENESIS_ATTESTORS:
        today_start = now()[:10] + "T00:00:00"
        today_count = conn.execute(
            "SELECT COUNT(*) as n FROM attestations WHERE attester_id = ? AND created_at >= ?",
            (req.attester_id, today_start)
        ).fetchone()["n"]
        if today_count >= MAX_ATTESTATIONS_PER_DAY:
            conn.close()
            raise HTTPException(429, f"Rate limit: max {MAX_ATTESTATIONS_PER_DAY} attestations per day. Try again tomorrow.")

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
        # v0.4 signed identity — unsigned non-genesis attestors get 0.5x weight
        signed = _verify_agent_signature(req.attester_id, req.signature, req.timestamp, req.nonce)
        if not signed:
            attest_weight = attest_weight * 0.5

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

    try:
        mycelium_trails.record_trail(
            TRAILS_DB,
            agent_id=req.attester_id,
            service=SERVICE_NAME,
            operation="attest_action",
            nonce=req.nonce or attest_id,
            karma_at_time=attester_karma if req.attester_id not in GENESIS_ATTESTORS else None,
            success=True,
        )
    except Exception:
        pass

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

@app.get("/entity/{entity_id}")
def get_entity(entity_id: str):
    conn = get_db()
    w = conn.execute("SELECT * FROM wisdom WHERE entity_id = ?", (entity_id,)).fetchone()
    conn.close()
    if not w:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
    d = dict(w)
    d["karma"] = d["total_karma"]
    return d

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

@app.get("/entity/{entity_id}/usage")
def get_entity_usage(entity_id: str):
    """Uso mensual de trails para un agent_id — alimenta la barra de progreso en la UI."""
    used = mycelium_trails.count_trails_this_month(TRAILS_DB, entity_id)
    limit = mycelium_trails.MONTHLY_LIMIT_FREE
    pct = round(used / limit * 100, 1) if limit else 0
    if pct >= 90:
        status = "critical"
    elif pct >= 75:
        status = "warning"
    else:
        status = "ok"
    return {
        "entity_id":    entity_id,
        "used":         used,
        "limit":        limit,
        "percent":      pct,
        "status":       status,
        "year_month":   mycelium_trails._year_month(),
    }


def _sign_badge(payload: dict) -> str:
    """Sign a badge payload with the Argentum server key. Returns base64 signature."""
    import base64
    from nacl.signing import SigningKey
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sk = SigningKey(base64.b64decode(ARGENTUM_SIGNING_KEY))
    return base64.b64encode(sk.sign(canonical).signature).decode("ascii")


@app.get("/karma/{agent_id}")
def get_karma(agent_id: str):
    """Public karma endpoint — returns score + verifiable badge signed by Argentum."""
    conn = get_db()
    w = conn.execute("SELECT * FROM wisdom WHERE entity_id = ?", (agent_id,)).fetchone()
    verified_count = 0
    if w:
        verified_count = conn.execute(
            "SELECT COUNT(*) FROM actions WHERE entity_id = ? AND status = 'verified'",
            (agent_id,)
        ).fetchone()[0]
    conn.close()

    karma = round(dict(w).get("total_karma_real") or dict(w)["total_karma"], 2) if w else 0
    verified_at = datetime.now(timezone.utc).isoformat()

    badge_payload = {
        "agent_id":       agent_id,
        "karma":          karma,
        "verified_at":    verified_at,
        "verified_actions": verified_count,
        "source":         f"{ARGENTUM_BASE_URL}/karma/{agent_id}",
    }

    sig = _sign_badge(badge_payload) if ARGENTUM_SIGNING_KEY else None

    return {
        **badge_payload,
        "verify_key":  ARGENTUM_VERIFY_KEY or None,
        "signature":   sig,
        "verify_url":  f"{ARGENTUM_BASE_URL}/karma/{agent_id}/verify",
    }


@app.post("/karma/{agent_id}/verify")
def verify_karma_badge(agent_id: str, body: dict):
    """Verify a karma badge signed by Argentum. POST {badge_payload, signature}."""
    import base64
    from nacl.signing import VerifyKey
    from nacl.exceptions import BadSignatureError

    badge = body.get("badge")
    signature = body.get("signature")
    if not badge or not signature:
        raise HTTPException(status_code=400, detail="badge and signature required")

    if badge.get("agent_id") != agent_id:
        raise HTTPException(status_code=400, detail="agent_id mismatch")

    if not ARGENTUM_VERIFY_KEY:
        raise HTTPException(status_code=503, detail="verify key not configured")

    canonical = json.dumps(badge, sort_keys=True, separators=(",", ":")).encode("utf-8")
    try:
        vk = VerifyKey(base64.b64decode(ARGENTUM_VERIFY_KEY))
        vk.verify(canonical, base64.b64decode(signature))
    except (BadSignatureError, Exception):
        return {"valid": False, "reason": "invalid signature"}

    return {"valid": True, "agent_id": agent_id, "karma": badge.get("karma")}


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

# ── PAYG ─────────────────────────────────────────────────────────────────────

class PaygTopupLightningReq(BaseModel):
    api_key: str
    trails: int  # cantidad de trails a comprar

class PaygTopupUsdcReq(BaseModel):
    api_key: str
    trails: int
    from_address: str  # dirección EVM desde la que se enviará el USDC

@limiter.limit("10/minute")
@app.post("/payg/topup/lightning")
async def payg_topup_lightning(request: Request, req: PaygTopupLightningReq):
    """Genera invoice Lightning para comprar N trails (300 sats/trail)."""
    if req.trails < 1 or req.trails > 10000:
        raise HTTPException(400, "trails must be between 1 and 10000")
    account = mycelium_trails.get_payg_account(TRAILS_DB, req.api_key)
    if account is None:
        raise HTTPException(404, "api_key not found — create account first via POST /payg/account")
    amount_sat = req.trails * mycelium_trails.SATS_PER_TRAIL
    inv = await phoenixd_create_invoice(
        amount_sat=amount_sat,
        description=f"ARGENTUM PAYG — {req.trails} trails",
        external_id=f"payg:{req.api_key}:{req.trails}",
    )
    return {
        "api_key":      req.api_key,
        "trails":       req.trails,
        "amount_sat":   amount_sat,
        "invoice":      inv["serialized"],
        "payment_hash": inv["paymentHash"],
        "note":         f"{mycelium_trails.SATS_PER_TRAIL} sats/trail. Credits added on payment confirmation.",
    }


@limiter.limit("10/minute")
@app.post("/payg/topup/usdc")
def payg_topup_usdc(request: Request, req: PaygTopupUsdcReq):
    """Registra intent de depósito USDC. Crediting automático al detectar el transfer on-chain."""
    if req.trails < 1 or req.trails > 10000:
        raise HTTPException(400, "trails must be between 1 and 10000")
    if not req.from_address.startswith("0x") or len(req.from_address) != 42:
        raise HTTPException(400, "from_address must be a valid EVM address (0x + 40 hex chars)")
    account = mycelium_trails.get_payg_account(TRAILS_DB, req.api_key)
    if account is None:
        raise HTTPException(404, "api_key not found")
    intent = mycelium_trails.create_usdc_intent(
        TRAILS_DB, req.api_key, req.from_address, req.trails
    )
    return {
        "intent_id":       intent["intent_id"],
        "api_key":         req.api_key,
        "trails":          req.trails,
        "usdc_amount":     intent["usdc_amount"],
        "deposit_address": PAYG_WALLET,
        "from_address":    intent["from_address"],
        "network":         "Arbitrum mainnet (eip155:42161)",
        "token":           "USDC (native)",
        "expires_at":      intent["expires_at"],
        "note":            "Send exactly this amount from from_address. Credited automatically within ~60s of on-chain confirmation.",
    }


@app.post("/payg/webhook/lightning")
async def payg_webhook_lightning(request: Request):
    """Webhook phoenixd para topups PAYG. externalId: 'payg:{api_key}:{trails}'"""
    body = await request.body()
    sig_header = request.headers.get("X-Phoenix-Signature", "")
    expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig_header, expected):
        raise HTTPException(401, "Invalid webhook signature")
    data = json.loads(body)
    if data.get("type") != "payment_received":
        return {"status": "ignored"}
    external_id = data.get("externalId", "")
    if not external_id.startswith("payg:"):
        return {"status": "ignored"}
    parts = external_id.split(":")
    if len(parts) != 3:
        return {"status": "ignored"}
    _, api_key, trails_str = parts
    trails = int(trails_str)
    result = mycelium_trails.topup_payg(TRAILS_DB, api_key, trails)
    if result is None:
        raise HTTPException(404, "api_key not found")
    if _SMTP_OK:
        acct = mycelium_trails.get_payg_account(TRAILS_DB, api_key)
        _smtp.notify_payg_topup(
            agent_id=acct.get("agent_id", api_key) if acct else api_key,
            trails_added=trails,
            trails_total=result["credit_trails"],
        )
    return {"status": "ok", "api_key": api_key, "credited_trails": trails, "balance": result["credit_trails"]}


@app.get("/payg/balance")
def payg_balance(api_key: str):
    """Créditos restantes + tier para una api_key."""
    account = mycelium_trails.get_payg_account(TRAILS_DB, api_key)
    if account is None:
        raise HTTPException(404, "api_key not found")
    return {
        "api_key":       account["api_key"],
        "agent_id":      account["agent_id"],
        "tier":          account["tier"],
        "credit_trails": account["credit_trails"],
    }


@limiter.limit("5/minute")
@app.post("/payg/account")
def create_payg_account(request: Request, agent_id: str):
    """Crea una cuenta PAYG (tier free, 0 créditos). Devuelve api_key."""
    api_key = mycelium_trails.create_payg_account(TRAILS_DB, agent_id)
    return {"api_key": api_key, "agent_id": agent_id, "tier": "free", "credit_trails": 0}


@app.post("/payg/account/{api_key}/conformance")
def set_account_conformance(api_key: str, request: Request, source: str):
    """Admin — setea conformance_source en una cuenta PAYG.

    Requiere header X-Admin-Token. Source debe ser uno de los tiers en CONFORMANCE_TIER
    (aps, nobulex, safeagent…) o vacío para resetear.
    """
    token = request.headers.get("X-Admin-Token", "")
    if not ADMIN_TOKEN or not hmac.compare_digest(token, ADMIN_TOKEN):
        raise HTTPException(401, "invalid or missing X-Admin-Token")
    account = mycelium_trails.set_conformance_source(TRAILS_DB, api_key, source)
    if account is None:
        raise HTTPException(404, "api_key not found")
    weight = CONFORMANCE_TIER.get((source or "").lower(), KARMA_DEFAULT_WEIGHT)
    return {
        "api_key":            account["api_key"],
        "agent_id":           account["agent_id"],
        "conformance_source": account["conformance_source"],
        "karma_weight":       weight,
        "tier":               "conformance_verified" if source in CONFORMANCE_TIER else "default",
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

# ── SLASHING ────────────────────────────────────────────────────────────────

@app.post("/action/{action_id}/report")
def report_action(action_id: str, req: ReportRequest):
    """Anyone can report a verified action as false. Opens a slash investigation."""
    conn = get_db()
    action = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    if not action:
        conn.close()
        raise HTTPException(404, "Action not found")
    if action["status"] != "verified":
        conn.close()
        raise HTTPException(400, "Only verified actions can be reported")
    if action["entity_id"] == req.reporter_id:
        conn.close()
        raise HTTPException(400, "Cannot report your own action")
    existing = conn.execute(
        "SELECT id FROM reports WHERE action_id = ? AND reporter_id = ?",
        (action_id, req.reporter_id)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "Already reported")
    signed = _verify_agent_signature(req.reporter_id, req.signature, req.timestamp, req.nonce)
    report_id = str(uuid.uuid4())[:8]
    conn.execute(
        "INSERT INTO reports (id, action_id, reporter_id, reason, status, created_at) VALUES (?, ?, ?, ?, 'open', ?)",
        (report_id, action_id, req.reporter_id, req.reason, now())
    )
    conn.commit()
    conn.close()
    return {"report_id": report_id, "action_id": action_id, "status": "open",
            "signed": signed,
            "message": "Report submitted. Genesis attestors will review."}


@app.post("/action/{action_id}/slash")
def confirm_slash(action_id: str, req: SlashConfirmRequest):
    """Genesis attestors confirm a slash. Penalizes poster and all attestors."""
    if req.confirmer_id not in GENESIS_ATTESTORS:
        raise HTTPException(403, "Only genesis attestors can confirm a slash")
    conn = get_db()
    action = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    if not action:
        conn.close()
        raise HTTPException(404, "Action not found")
    if action["status"] == "slashed":
        conn.close()
        raise HTTPException(400, "Already slashed")
    open_report = conn.execute(
        "SELECT id FROM reports WHERE action_id = ? AND status = 'open'", (action_id,)
    ).fetchone()
    if not open_report:
        conn.close()
        raise HTTPException(400, "No open report for this action")

    # Slash poster — lose karma_value
    slash_amount = action["karma_value"]
    conn.execute(
        "UPDATE wisdom SET total_karma = MAX(0, total_karma - ?), verified_actions = MAX(0, verified_actions - 1) WHERE entity_id = ?",
        (slash_amount, action["entity_id"])
    )
    # Slash each attestor — lose WITNESS karma (5)
    attestors = conn.execute(
        "SELECT attester_id FROM attestations WHERE action_id = ?", (action_id,)
    ).fetchall()
    for att in attestors:
        if att["attester_id"] not in GENESIS_ATTESTORS:
            conn.execute(
                "UPDATE wisdom SET total_karma = MAX(0, total_karma - ?) WHERE entity_id = ?",
                (ACTION_TYPES["WITNESS"]["karma"], att["attester_id"])
            )
    # Mark action as slashed and close report
    conn.execute("UPDATE actions SET status = 'slashed' WHERE id = ?", (action_id,))
    conn.execute(
        "UPDATE reports SET status = 'confirmed', resolved_at = ? WHERE action_id = ? AND status = 'open'",
        (now(), action_id)
    )
    conn.commit()
    conn.close()
    return {
        "action_id":     action_id,
        "status":        "slashed",
        "poster_slash":  slash_amount,
        "attestors_slashed": len(attestors),
        "message":       f"Action slashed. Poster lost {slash_amount} karma. {len(attestors)} attestor(s) lost {ACTION_TYPES['WITNESS']['karma']} karma each."
    }


@app.get("/reports")
def list_reports(status: Optional[str] = None):
    """List slash reports."""
    conn = get_db()
    if status:
        rows = conn.execute(
            "SELECT * FROM reports WHERE status = ? ORDER BY created_at DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM reports ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── KLEROS DISPUTE RESOLUTION ────────────────────────────────────────────────

@limiter.limit("5/minute")
@app.post("/action/{action_id}/dispute")
async def open_dispute(request: Request, action_id: str, req: DisputeRequest):
    """
    Escalate a verified action to Kleros for decentralized arbitration.
    Requires reporter karma >= MINIMUM_KARMA_TO_DISPUTE (10).
    Action status moves to 'disputed' — karma frozen until ruling.
    On-chain: ArgentumArbitrable.sol implements IArbitrable (deploy pending Kleros coordination).
    """
    conn = get_db()
    action = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    if not action:
        conn.close()
        raise HTTPException(404, "Action not found")
    if action["status"] not in ("verified", "pending"):
        conn.close()
        raise HTTPException(400, f"Cannot dispute an action with status '{action['status']}'")
    if action["entity_id"] == req.reporter_id:
        conn.close()
        raise HTTPException(400, "Cannot dispute your own action")

    # Check reporter karma — genesis attestors exempt
    if req.reporter_id not in GENESIS_ATTESTORS:
        reporter_wisdom = conn.execute(
            "SELECT total_karma FROM wisdom WHERE entity_id = ?", (req.reporter_id,)
        ).fetchone()
        reporter_karma = reporter_wisdom["total_karma"] if reporter_wisdom else 0
        if reporter_karma < MINIMUM_KARMA_TO_DISPUTE:
            conn.close()
            raise HTTPException(
                403,
                f"Opening a dispute requires at least {MINIMUM_KARMA_TO_DISPUTE} karma. "
                f"{req.reporter_id} has {reporter_karma}."
            )

    # No double disputes
    existing = conn.execute(
        "SELECT id FROM disputes WHERE action_id = ? AND status = 'pending'", (action_id,)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "Dispute already open for this action")

    signed = _verify_agent_signature(req.reporter_id, req.signature, req.timestamp, req.nonce)
    dispute_id = str(uuid.uuid4())[:8]
    conn.execute(
        "INSERT INTO disputes (id, action_id, reporter_id, reason, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
        (dispute_id, action_id, req.reporter_id, req.reason, now())
    )
    conn.execute("UPDATE actions SET status = 'disputed' WHERE id = ?", (action_id,))
    conn.commit()
    conn.close()

    await store_in_memory(
        content=f"[ARGENTUM] Dispute opened on action {action_id} by {req.reporter_id} — {req.reason}",
        entity_id="giskard-self",
        metadata={"type": "argentum_dispute", "action_id": action_id, "dispute_id": dispute_id, "signed": signed}
    )

    return {
        "dispute_id":  dispute_id,
        "action_id":   action_id,
        "status":      "pending",
        "signed":      signed,
        "message":     "Dispute opened. Action frozen pending Kleros ruling.",
        "kleros_note": "ArgentumArbitrable.sol (IArbitrable) — deploy pending Kleros coordination.",
        "rulings":     {"1": "slash poster + attestors", "2": "clear — action restored to verified", "0": "refused — action restored"}
    }


@app.get("/action/{action_id}/dispute")
def get_dispute(action_id: str):
    """Get the dispute record for an action (open or resolved)."""
    conn = get_db()
    dispute = conn.execute(
        "SELECT * FROM disputes WHERE action_id = ? ORDER BY created_at DESC LIMIT 1", (action_id,)
    ).fetchone()
    conn.close()
    if not dispute:
        raise HTTPException(404, "No dispute found for this action")
    return dict(dispute)


@app.post("/kleros/ruling")
async def kleros_ruling(request: Request, req: KlerosRulingRequest):
    """
    Receives the ruling from Kleros arbitrator.
    In production: triggered by ArgentumArbitrable.sol DisputeResolved event listener.
    In development: call directly with X-Kleros-Secret header.

    ruling = 1 → reporter wins → slash poster + attestors
    ruling = 2 → poster wins  → action restored to verified
    ruling = 0 → refused      → action restored to verified (no punishment)
    """
    secret = request.headers.get("X-Kleros-Secret", "")
    if not hmac.compare_digest(secret, KLEROS_RULING_SECRET):
        raise HTTPException(401, "Invalid Kleros ruling secret")

    conn = get_db()
    action = conn.execute("SELECT * FROM actions WHERE id = ?", (req.action_id,)).fetchone()
    if not action:
        conn.close()
        raise HTTPException(404, "Action not found")
    if action["status"] != "disputed":
        conn.close()
        raise HTTPException(400, f"Action is not disputed (current: {action['status']})")

    dispute = conn.execute(
        "SELECT * FROM disputes WHERE action_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
        (req.action_id,)
    ).fetchone()
    if not dispute:
        conn.close()
        raise HTTPException(404, "No pending dispute for this action")

    resolved_at = now()

    if req.ruling == 1:
        # Reporter wins — slash poster and attestors
        slash_amount = action["karma_value"]
        conn.execute(
            "UPDATE wisdom SET total_karma = MAX(0, total_karma - ?), verified_actions = MAX(0, verified_actions - 1) WHERE entity_id = ?",
            (slash_amount, action["entity_id"])
        )
        attestors = conn.execute(
            "SELECT attester_id FROM attestations WHERE action_id = ?", (req.action_id,)
        ).fetchall()
        for att in attestors:
            if att["attester_id"] not in GENESIS_ATTESTORS:
                conn.execute(
                    "UPDATE wisdom SET total_karma = MAX(0, total_karma - ?) WHERE entity_id = ?",
                    (ACTION_TYPES["WITNESS"]["karma"], att["attester_id"])
                )
        conn.execute("UPDATE actions SET status = 'slashed' WHERE id = ?", (req.action_id,))
        conn.execute(
            "UPDATE disputes SET status = 'ruled_slash', ruling = 1, resolved_at = ? WHERE id = ?",
            (resolved_at, dispute["id"])
        )
        result_msg    = f"Kleros ruled: slash. Poster lost {slash_amount} karma. {len(attestors)} attestor(s) penalized."
        result_status = "slashed"

    else:
        # ruling == 2 (poster wins) or 0 (refused) — restore action
        conn.execute("UPDATE actions SET status = 'verified' WHERE id = ?", (req.action_id,))
        dispute_outcome = "ruled_clear" if req.ruling == 2 else "ruled_refused"
        conn.execute(
            "UPDATE disputes SET status = ?, ruling = ?, resolved_at = ? WHERE id = ?",
            (dispute_outcome, req.ruling, resolved_at, dispute["id"])
        )
        result_msg    = "Kleros ruled: action cleared. Status restored to verified."
        result_status = "verified"

    conn.commit()
    conn.close()

    await store_in_memory(
        content=f"[ARGENTUM] Kleros ruling on {req.action_id}: ruling={req.ruling} — {result_msg}",
        entity_id="giskard-self",
        metadata={"type": "argentum_kleros_ruling", "action_id": req.action_id, "ruling": req.ruling}
    )

    return {
        "action_id":     req.action_id,
        "ruling":        req.ruling,
        "action_status": result_status,
        "message":       result_msg
    }


# ── MYCELIUM TRAILS ─────────────────────────────────────────────────────────
# Recetas verificables: secuencias de calls a servicios MCP que resuelven un
# problema concreto. Composability monetizada sobre el stack Mycelium.

import json as _json

TRAIL_AUTHOR_KARMA_REWARD = 3   # karma when a trail execution succeeds
MIN_TRAIL_PRICE = 1
MAX_TRAIL_STEPS = 12

@limiter.limit("10/minute")
@app.post("/trails")
async def register_trail(request: Request, req: TrailRegister):
    if not req.steps or len(req.steps) > MAX_TRAIL_STEPS:
        raise HTTPException(400, f"steps must be 1..{MAX_TRAIL_STEPS}")
    if req.price_sats < MIN_TRAIL_PRICE:
        raise HTTPException(400, f"price_sats must be >= {MIN_TRAIL_PRICE}")
    for s in req.steps:
        if not isinstance(s, dict) or "service" not in s or "tool" not in s:
            raise HTTPException(400, "each step needs {service, tool}")
    signed = _verify_agent_signature(req.author_id, req.signature, req.timestamp, req.nonce)
    trail_id = str(uuid.uuid4())[:8]
    conn = get_db()
    conn.execute(
        "INSERT INTO trails (id, author_id, author_name, name, description, steps, price_sats, output_schema, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (trail_id, req.author_id, req.author_name, req.name, req.description,
         _json.dumps(req.steps), req.price_sats,
         _json.dumps(req.output_schema) if req.output_schema else None, now()))
    conn.commit()
    conn.close()
    return {"trail_id": trail_id, "name": req.name, "steps": len(req.steps),
            "price_sats": req.price_sats, "signed": signed}

@app.get("/trails/verify")
async def proxy_trails_verify(
    agent_id: Optional[str] = None,
    action_ref: Optional[str] = None,
    payment_hash: Optional[str] = None,
):
    """Verifica si un trail Mycelium existe.

    - Por action_ref: requiere agent_id + action_ref (SHA-256 canónico).
    - Por payment_hash: receipt_id cross-rail (linking key en fixtures APS/stripe-issuing).
    Delega a Giskard Oasis REST. Sin auth.
    """
    params = {}
    if payment_hash:
        params["payment_hash"] = payment_hash
    elif agent_id and action_ref:
        params["agent_id"] = agent_id
        params["action_ref"] = action_ref
    else:
        return JSONResponse(
            {"detail": "provide action_ref+agent_id or payment_hash"}, status_code=422
        )
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get("http://localhost:8003/trails/verify", params=params)
        return JSONResponse(content=r.json(), status_code=r.status_code)


@app.get("/trails/demo")
async def proxy_trails_demo(limit: int = 10):
    """Proxy a Giskard Oasis /trails/demo — flujo demo Lightning + cross-chain bridge."""
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"http://localhost:8003/trails/demo", params={"limit": limit})
        return r.json()


_FINSERV_DEMO = {
    "agent_id":    "fca-compliance-agent",
    "action_type": "trade.execute",
    "scope":       "trade:execute:authorized",
    "timestamp":   "2026-06-03T09:00:00.000Z",
    "action_ref":  "5df319397e75ba2e031ccf0789beb0e5e04ee5bea396a5840455c997072bc86a",
    "tx_hash":     "0x80f3aebf4b24f19eadb7fb80887d03b82bfd2e0b9473ff16ae46d0d72139ebf6",
    "block":       469669261,
    "service":     "mycelium.finserv-demo",
}
_finserv_trail_id_cache: list = []

def _get_or_create_finserv_trail() -> str:
    if _finserv_trail_id_cache:
        return _finserv_trail_id_cache[0]
    conn = mycelium_trails._connect(TRAILS_DB)
    row = conn.execute(
        "SELECT trail_id FROM trails WHERE service = ? LIMIT 1",
        (_FINSERV_DEMO["service"],),
    ).fetchone()
    conn.close()
    if row:
        _finserv_trail_id_cache.append(row[0])
        return row[0]
    trail_id = mycelium_trails.record_trail(
        TRAILS_DB,
        agent_id=_FINSERV_DEMO["agent_id"],
        service=_FINSERV_DEMO["service"],
        operation=_FINSERV_DEMO["action_type"],
        nonce=_FINSERV_DEMO["action_ref"],
        karma_at_time=None,
        success=True,
        rate_limit_cap=0,
        scope=_FINSERV_DEMO["scope"],
    )
    if trail_id:
        conn2 = mycelium_trails._connect(TRAILS_DB)
        conn2.execute(
            "UPDATE trails SET tx_hash = ? WHERE trail_id = ?",
            (_FINSERV_DEMO["tx_hash"], trail_id),
        )
        conn2.close()
        _finserv_trail_id_cache.append(trail_id)
    return trail_id or "demo"


@app.get("/trails/finserv-demo", response_class=HTMLResponse)
def finserv_demo():
    """Pre-generated MiFID II / FCA SYSC 9.1 compliance trail — enterprise demo."""
    trail_id = _get_or_create_finserv_trail()
    d = _FINSERV_DEMO
    arbiscan = f"https://arbiscan.io/tx/{d['tx_hash']}"
    verify_url = f"https://argentum-api.rgiskard.xyz/trails/verify?agent_id={d['agent_id']}&action_ref={d['action_ref']}"
    canonical_payload = '{"action_type":"trade.execute","agent_id":"fca-compliance-agent","scope":"trade:execute:authorized","timestamp":"2026-06-03T09:00:00.000Z"}'
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mycelium Trails — Finserv Compliance Demo</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Inter',system-ui,sans-serif;background:#0a0e1a;color:#e2e8f0;line-height:1.6}}
  .header{{background:linear-gradient(135deg,#1a2744 0%,#0d1f3c 100%);border-bottom:1px solid #2d4a7a;padding:32px 48px}}
  .header h1{{font-size:1.5rem;font-weight:700;color:#93c5fd;letter-spacing:.02em}}
  .header p{{color:#94a3b8;margin-top:6px;font-size:.95rem}}
  .badge{{display:inline-flex;align-items:center;gap:6px;background:#064e3b;color:#6ee7b7;font-size:.75rem;font-weight:600;padding:3px 10px;border-radius:9999px;border:1px solid #065f46;margin-top:12px}}
  .badge.anchor{{background:#1e3a5f;color:#93c5fd;border-color:#2563eb}}
  .container{{max-width:900px;margin:0 auto;padding:40px 32px}}
  .section{{background:#111827;border:1px solid #1f2d45;border-radius:12px;padding:28px;margin-bottom:24px}}
  .section h2{{font-size:1rem;font-weight:600;color:#60a5fa;text-transform:uppercase;letter-spacing:.08em;margin-bottom:18px;display:flex;align-items:center;gap:8px}}
  .kv{{display:grid;grid-template-columns:200px 1fr;gap:8px 16px;align-items:start}}
  .kv .key{{color:#64748b;font-size:.85rem;font-weight:500;padding-top:2px}}
  .kv .val{{color:#e2e8f0;font-size:.875rem;font-family:'JetBrains Mono','Fira Code',monospace;word-break:break-all}}
  .kv .val.highlight{{color:#34d399;background:#052e16;padding:3px 8px;border-radius:4px;border:1px solid #065f46}}
  .kv .val.dim{{color:#94a3b8}}
  .code{{background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:16px;font-family:'JetBrains Mono','Fira Code',monospace;font-size:.8rem;color:#c9d1d9;overflow-x:auto;margin-top:8px}}
  .compliance-table{{width:100%;border-collapse:collapse;font-size:.875rem}}
  .compliance-table th{{background:#1e293b;color:#94a3b8;font-weight:600;text-align:left;padding:10px 14px;font-size:.8rem;text-transform:uppercase;letter-spacing:.05em}}
  .compliance-table td{{padding:10px 14px;border-bottom:1px solid #1f2d45;vertical-align:top}}
  .compliance-table tr:last-child td{{border-bottom:none}}
  .compliance-table .rule{{color:#93c5fd;font-family:monospace;font-size:.8rem}}
  .compliance-table .status{{color:#34d399;font-weight:600}}
  .link{{color:#60a5fa;text-decoration:none;font-size:.8rem}}
  .link:hover{{text-decoration:underline}}
  .footer{{text-align:center;color:#374151;font-size:.8rem;padding:32px;border-top:1px solid #1f2d45;margin-top:8px}}
  .pill{{display:inline-flex;align-items:center;gap:4px;font-size:.75rem;font-weight:500;padding:2px 8px;border-radius:4px}}
  .pill.success{{background:#052e16;color:#34d399;border:1px solid #065f46}}
  .pill.anchored{{background:#1e3a5f;color:#93c5fd;border:1px solid #1d4ed8}}
</style>
</head>
<body>
<div class="header">
  <h1>Mycelium Trails — Regulatory Evidence Layer</h1>
  <p>Pre-generated compliance trail · MiFID II Art. 25 · FCA SYSC 9.1.1R · Independently verifiable</p>
  <span class="badge">&#10003; Trail anchored on Arbitrum One</span>
  &nbsp;
  <span class="badge anchor">&#128274; action_ref · SHA-256 canonical</span>
</div>

<div class="container">

  <div class="section">
    <h2>&#128196; Scenario</h2>
    <p style="color:#94a3b8;font-size:.9rem;margin-bottom:18px">
      An AI trading agent executes a equity order under MiFID II best-execution obligation
      and FCA SYSC 9.1 record-keeping requirements. The action is content-addressed —
      any party with the four preimage fields can independently verify the receipt without
      trusting the emitting system.
    </p>
    <div class="kv">
      <span class="key">Trail ID</span>
      <span class="val dim">{trail_id}</span>
      <span class="key">Status</span>
      <span class="val"><span class="pill success">&#10003; executed</span></span>
      <span class="key">Executed at</span>
      <span class="val">{d["timestamp"]} &nbsp;<span style="color:#64748b;font-size:.8rem">(market open, UTC)</span></span>
      <span class="key">Agent</span>
      <span class="val">{d["agent_id"]}</span>
      <span class="key">Operation</span>
      <span class="val">{d["action_type"]}</span>
      <span class="key">Scope</span>
      <span class="val">{d["scope"]}</span>
    </div>
  </div>

  <div class="section">
    <h2>&#128274; Canonical action_ref</h2>
    <p style="color:#64748b;font-size:.85rem;margin-bottom:14px">
      SHA-256 of the JCS-canonicalized preimage (RFC 8785). Deterministic — same four inputs
      always produce the same digest. No trust in Mycelium required to verify.
    </p>
    <div class="kv">
      <span class="key">action_ref</span>
      <span class="val highlight">{d["action_ref"]}</span>
      <span class="key">Preimage</span>
      <span class="val dim">agent_id · action_type · scope · timestamp (lexicographic JCS)</span>
    </div>
    <div class="code"># Reproduce independently
import hashlib, json

preimage = {{
    "agent_id":    "{d['agent_id']}",
    "action_type": "{d['action_type']}",
    "scope":       "{d['scope']}",
    "timestamp":   "{d['timestamp']}",
}}
canonical = json.dumps(dict(sorted(preimage.items())), separators=(",",":")).encode()
action_ref = hashlib.sha256(canonical).hexdigest()
# → {d["action_ref"]}

# JCS payload:
# {canonical_payload}</div>
  </div>

  <div class="section">
    <h2>&#9935; On-chain anchor · Arbitrum One</h2>
    <p style="color:#64748b;font-size:.85rem;margin-bottom:14px">
      The action_ref is anchored on Arbitrum One. The transaction timestamp provides
      a tamper-evident lower bound: the action was registered no later than block {d["block"]}.
    </p>
    <div class="kv">
      <span class="key">Network</span>
      <span class="val">Arbitrum One (Chain ID 42161)</span>
      <span class="key">Block</span>
      <span class="val">{d["block"]:,}</span>
      <span class="key">Transaction</span>
      <span class="val"><a class="link" href="{arbiscan}" target="_blank">{d["tx_hash"][:20]}…{d["tx_hash"][-8:]} ↗</a></span>
      <span class="key">Wallet</span>
      <span class="val dim">0xDcc84E979…83DBF4 (Mycelium operator)</span>
    </div>
  </div>

  <div class="section">
    <h2>&#9989; Independent verification</h2>
    <div class="kv">
      <span class="key">Verify endpoint</span>
      <span class="val"><a class="link" href="{verify_url}" target="_blank">argentum-api.rgiskard.xyz/trails/verify ↗</a></span>
      <span class="key">On-chain</span>
      <span class="val"><a class="link" href="{arbiscan}" target="_blank">arbiscan.io ↗</a></span>
      <span class="key">Spec</span>
      <span class="val"><a class="link" href="https://github.com/giskard09/argentum-core/blob/main/docs/spec/action-ref.md" target="_blank">action-ref.md v1.1 ↗</a></span>
    </div>
  </div>

  <div class="section">
    <h2>&#9878; Regulatory mapping</h2>
    <table class="compliance-table">
      <thead>
        <tr><th>Regulation</th><th>Requirement</th><th>How action_ref satisfies it</th><th>Status</th></tr>
      </thead>
      <tbody>
        <tr>
          <td class="rule">MiFID II Art. 25(1)</td>
          <td>Record of investment services — sufficient information to reconstruct each order</td>
          <td>action_ref + preimage fields (agent, operation, scope, timestamp) provide a tamper-evident, independently replayable record of each agent action</td>
          <td class="status">&#10003; Satisfied</td>
        </tr>
        <tr>
          <td class="rule">FCA SYSC 9.1.1R</td>
          <td>Orderly record-keeping — records must be retained and retrievable</td>
          <td>Trail persisted in Mycelium with public verify endpoint; on-chain anchor provides long-term tamper evidence independent of operator availability</td>
          <td class="status">&#10003; Satisfied</td>
        </tr>
        <tr>
          <td class="rule">FCA SYSC 9.1.2G</td>
          <td>Records sufficient to demonstrate compliance to regulators</td>
          <td>Canonical receipt envelope v1.0 includes hash_algo, preimage_format, and all four preimage fields — complete audit package exportable to supervisor on demand</td>
          <td class="status">&#10003; Satisfied</td>
        </tr>
        <tr>
          <td class="rule">EU AI Act Art. 12</td>
          <td>Logging obligations for high-risk AI — traceability of automated decisions</td>
          <td>Each trail record links agent_id (executor), action_type (decision class), scope (authorization boundary), and timestamp — satisfies traceability for high-risk classification</td>
          <td class="status">&#10003; Satisfied</td>
        </tr>
        <tr>
          <td class="rule">Basel III / BCBS 239</td>
          <td>Data lineage and auditability for risk reporting</td>
          <td>action_ref as content-addressed linking key enables cross-system lineage: same receipt verifiable in Mycelium, on-chain, and any downstream risk system that embeds the preimage</td>
          <td class="status">&#10003; Satisfied</td>
        </tr>
      </tbody>
    </table>
  </div>

</div>
<div class="footer">
  Mycelium Trails · <a class="link" href="https://argentum.rgiskard.xyz">argentum.rgiskard.xyz</a> ·
  <a class="link" href="https://github.com/giskard09/argentum-core">github.com/giskard09/argentum-core</a>
</div>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/dashboard/trails", response_class=HTMLResponse)
def trails_dashboard(client: Optional[str] = None, limit: int = 50, show_internal: bool = False):
    """Live trails dashboard — consultable por cliente. Sin push."""
    conn = mycelium_trails._connect(TRAILS_DB)
    if client:
        rows = conn.execute(
            "SELECT trail_id, agent_id, service, operation, scope, timestamp, action_ref, success, origin, tx_hash "
            "FROM trails WHERE (agent_id = ? OR service = ?) "
            "ORDER BY timestamp DESC LIMIT ?",
            (client, client, min(limit, 200)),
        ).fetchall()
    elif show_internal:
        rows = conn.execute(
            "SELECT trail_id, agent_id, service, operation, scope, timestamp, action_ref, success, origin, tx_hash "
            "FROM trails ORDER BY timestamp DESC LIMIT ?",
            (min(limit, 200),),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT trail_id, agent_id, service, operation, scope, timestamp, action_ref, success, origin, tx_hash "
            "FROM trails WHERE origin != 'pioneer' "
            "ORDER BY timestamp DESC LIMIT ?",
            (min(limit, 200),),
        ).fetchall()
    conn.close()

    import datetime as _dt
    def fmt_ts(ts):
        try:
            return _dt.datetime.fromtimestamp(int(ts), tz=_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            return str(ts)

    def e(v, quote=False): return _html.escape(str(v) if v else "", quote=quote)

    rows_html = ""
    for r in rows:
        action_ref_val = r["action_ref"] or ""
        action_ref_short = (action_ref_val[:12] + "…") if action_ref_val else "—"
        action_ref_title = e(action_ref_val, quote=True)
        success_badge = '<span class="ok">✓</span>' if r["success"] else '<span class="fail">✗</span>'
        origin_val = r["origin"] if "origin" in r.keys() else None
        if origin_val == "nexus":
            origin_badge = '<span class="badge-nexus" title="Trail externo — cliente via /nexus/trail">client</span>'
        else:
            origin_badge = '<span class="badge-internal" title="Trail interno — generado por el sistema">internal</span>'
        tx_hash_val = r["tx_hash"] if "tx_hash" in r.keys() else None
        if tx_hash_val:
            tx_short = tx_hash_val[:10] + "…" + tx_hash_val[-6:]
            anchor_cell = f'<a class="anchor-link" href="https://arbiscan.io/tx/{e(tx_hash_val, quote=True)}" target="_blank" rel="noopener noreferrer" title="{e(tx_hash_val, quote=True)}">{e(tx_short)} ↗</a>'
        else:
            anchor_cell = '<span class="anchor-pending">pending</span>'
        rows_html += f"""<tr>
          <td class="mono dim">{e(r["trail_id"] or "")[:8]}</td>
          <td>{e(r["agent_id"])}</td>
          <td class="dim">{e(r["service"])}</td>
          <td>{e(r["operation"])}</td>
          <td class="dim">{e(r["scope"]) or "—"}</td>
          <td class="mono dim" title="{action_ref_title}">{e(action_ref_short)}</td>
          <td class="ts">{e(fmt_ts(r["timestamp"]))}</td>
          <td>{success_badge}</td>
          <td>{origin_badge}</td>
          <td>{anchor_cell}</td>
        </tr>"""

    safe_client = e(client or "", quote=True)
    if client:
        client_filter_note = f" — <span class='filter'>client: {safe_client}</span>"
    elif show_internal:
        client_filter_note = " — <span class='filter'>all (internal included)</span>"
    else:
        client_filter_note = " — <span class='filter'>client trails only</span>"
    total = len(rows)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mycelium Trails — Live Dashboard</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Inter',system-ui,sans-serif;background:#0a0e1a;color:#e2e8f0;font-size:.875rem}}
  .header{{background:#0d1f3c;border-bottom:1px solid #1f3a6e;padding:20px 32px;display:flex;align-items:center;justify-content:space-between}}
  .header h1{{font-size:1rem;font-weight:600;color:#93c5fd;letter-spacing:.02em}}
  .header .meta{{color:#64748b;font-size:.8rem}}
  .filter{{color:#60a5fa}}
  .toolbar{{padding:16px 32px;display:flex;align-items:center;gap:12px;border-bottom:1px solid #1a2744}}
  .toolbar input{{background:#111827;border:1px solid #1f2d45;color:#e2e8f0;padding:6px 12px;border-radius:6px;font-size:.8rem;width:220px}}
  .toolbar input::placeholder{{color:#475569}}
  .toolbar button{{background:#1d4ed8;color:#fff;border:none;padding:6px 14px;border-radius:6px;font-size:.8rem;cursor:pointer}}
  .toolbar button:hover{{background:#2563eb}}
  .toolbar .count{{color:#64748b;font-size:.8rem;margin-left:auto}}
  .refresh{{color:#64748b;font-size:.75rem}}
  .wrap{{padding:0 32px 32px}}
  table{{width:100%;border-collapse:collapse;margin-top:16px}}
  th{{background:#0d1f3c;color:#64748b;font-size:.75rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;padding:10px 12px;text-align:left;position:sticky;top:0}}
  td{{padding:9px 12px;border-bottom:1px solid #111827;vertical-align:middle}}
  tr:hover td{{background:#0d1a2e}}
  .mono{{font-family:'JetBrains Mono','Fira Code',monospace;font-size:.8rem}}
  .dim{{color:#94a3b8}}
  .ts{{color:#64748b;font-size:.78rem}}
  .ok{{color:#34d399;font-weight:700}}
  .fail{{color:#f87171;font-weight:700}}
  .empty{{text-align:center;color:#475569;padding:48px;font-size:.85rem}}
  .badge-nexus{{background:#14532d;color:#86efac;border:1px solid #166534;border-radius:4px;padding:1px 6px;font-size:.72rem;font-weight:600}}
  .badge-internal{{background:#1e293b;color:#64748b;border:1px solid #334155;border-radius:4px;padding:1px 6px;font-size:.72rem}}
  .anchor-link{{color:#60a5fa;font-family:'JetBrains Mono','Fira Code',monospace;font-size:.75rem;text-decoration:none}}
  .anchor-link:hover{{text-decoration:underline}}
  .anchor-pending{{color:#475569;font-size:.75rem}}
</style>
</head>
<body>
<div class="header">
  <h1>Mycelium Trails — Live Dashboard{client_filter_note}</h1>
  <span class="meta" id="last-refresh">Last refresh: {_dt.datetime.now(_dt.timezone.utc).strftime("%H:%M:%S UTC")}</span>
</div>
<div class="toolbar">
  <input id="filter-input" type="text" placeholder="Filter by client / agent_id…" value="{safe_client}">
  <button onclick="applyFilter()">Filter</button>
  <span class="count">{total} trail{'s' if total != 1 else ''}</span>
  <span class="refresh">Auto-refresh: 30s</span>
</div>
<div class="wrap">
<table>
  <thead>
    <tr>
      <th>Trail ID</th>
      <th>Agent / Client</th>
      <th>Service</th>
      <th>Action Type</th>
      <th>Scope</th>
      <th>action_ref</th>
      <th>Timestamp</th>
      <th></th>
      <th>Origin</th>
      <th>Anchor</th>
    </tr>
  </thead>
  <tbody>
    {"" if rows_html else '<tr><td colspan="10" class="empty">No trails found.</td></tr>'}
    {rows_html}
  </tbody>
</table>
</div>
<script>
function applyFilter() {{
  const v = document.getElementById('filter-input').value.trim();
  window.location.href = '/dashboard/trails' + (v ? '?client=' + encodeURIComponent(v) : '');
}}
document.getElementById('filter-input').addEventListener('keydown', e => {{
  if (e.key === 'Enter') applyFilter();
}});
// Auto-refresh every 30s
setTimeout(() => window.location.reload(), 30000);
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/mycelium/stats/{agent_id}")
def mycelium_stats(agent_id: str):
    """Conteo de trails Mycelium por agent_id, desglosado por origin.
    Excluye onboarding_incomplete. Fuente primaria para campos derivados en catálogos externos."""
    conn = sqlite3.connect(TRAILS_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT origin, COUNT(*) as cnt FROM trails "
        "WHERE agent_id = ? AND origin != 'onboarding_incomplete' "
        "GROUP BY origin",
        (agent_id,),
    ).fetchall()
    conn.close()
    by_origin = {r["origin"]: r["cnt"] for r in rows}
    client_trails = by_origin.get("nexus", 0) + by_origin.get("client", 0)
    return {
        "agent_id": agent_id,
        "trails_by_origin": by_origin,
        "client_trails": client_trails,
        "total_excluding_incomplete": sum(v for k, v in by_origin.items() if k != "pioneer"),
    }


@app.get("/trails/agents/{agent_id}")
async def proxy_trails_by_agent(agent_id: str, limit: int = 50):
    """Proxy a Giskard Oasis /trails/{agent_id} — historial de trails por agente."""
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"http://localhost:8003/trails/{agent_id}",
            params={"limit": min(limit, 50)},
        )
        return JSONResponse(content=r.json(), status_code=r.status_code)


@app.get("/mycelium/trails/{trail_id}/graph")
def get_mycelium_trail_graph(trail_id: str):
    """DAG completo de usage trails encadenados — sube a la raíz y baja a todos los descendientes."""
    result = mycelium_trails.get_trail_graph(TRAILS_DB, trail_id)
    if result is None:
        raise HTTPException(404, "trail not found")
    return result


@app.get("/mycelium/trails/{trail_id}/verify_chain")
def verify_mycelium_trail_chain(trail_id: str):
    """Valida integridad de la cadena desde trail_id hasta la raíz."""
    return mycelium_trails.verify_chain(TRAILS_DB, trail_id)


@app.get("/trails")
def list_trails(limit: int = 50, sort: str = "reputation"):
    conn = get_db()
    order = {
        "reputation": "ORDER BY (CAST(success_count AS REAL) / MAX(executions, 1)) DESC, executions DESC",
        "popular":    "ORDER BY executions DESC",
        "recent":     "ORDER BY created_at DESC",
        "rating":     "ORDER BY (CAST(rating_sum AS REAL) / MAX(rating_count, 1)) DESC, rating_count DESC",
    }.get(sort, "ORDER BY created_at DESC")
    rows = conn.execute(f"SELECT * FROM trails {order} LIMIT ?", (min(limit, 200),)).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["steps"] = _json.loads(d["steps"])
        if d.get("output_schema"):
            d["output_schema"] = _json.loads(d["output_schema"])
        d["success_rate"] = round(d["success_count"] / d["executions"], 3) if d["executions"] else None
        d["avg_rating"]   = round(d["rating_sum"] / d["rating_count"], 2) if d["rating_count"] else None
        out.append(d)
    return {"trails": out, "count": len(out), "sort": sort}

@app.get("/trails/{trail_id}")
def get_trail(trail_id: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM trails WHERE id = ?", (trail_id,)).fetchone()
    if not row:
        conn.close()
        # Fallback: buscar en Mycelium trails (trails.db) — trails registrados via /nexus/trail
        mrow = mycelium_trails.get_trail_by_id(TRAILS_DB, trail_id)
        if mrow is None:
            raise HTTPException(404, "trail not found")
        return {"source": "mycelium", **mrow}
    d = dict(row)
    d["steps"] = _json.loads(d["steps"])
    if d.get("output_schema"):
        d["output_schema"] = _json.loads(d["output_schema"])
    d["success_rate"] = round(d["success_count"] / d["executions"], 3) if d["executions"] else None
    d["avg_rating"]   = round(d["rating_sum"] / d["rating_count"], 2) if d["rating_count"] else None
    recent = conn.execute(
        "SELECT id, executor_name, status, rating, created_at FROM trail_executions "
        "WHERE trail_id = ? ORDER BY created_at DESC LIMIT 10", (trail_id,)).fetchall()
    conn.close()
    d["recent_executions"] = [dict(x) for x in recent]
    return d

@limiter.limit("30/minute")
@app.post("/trails/{trail_id}/execute")
async def record_trail_execution(request: Request, trail_id: str, req: TrailExecution):
    if req.status not in ("success", "fail"):
        raise HTTPException(400, "status must be 'success' or 'fail'")
    conn = get_db()
    trail = conn.execute("SELECT * FROM trails WHERE id = ?", (trail_id,)).fetchone()
    if not trail:
        conn.close()
        raise HTTPException(404, "trail not found")
    signed = _verify_agent_signature(req.executor_id, req.signature, req.timestamp, req.nonce)
    exec_id = str(uuid.uuid4())[:8]
    conn.execute(
        "INSERT INTO trail_executions (id, trail_id, executor_id, executor_name, status, output_hash, payment_hash, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (exec_id, trail_id, req.executor_id, req.executor_name, req.status,
         req.output_hash, req.payment_hash, now()))
    conn.execute("UPDATE trails SET executions = executions + 1 WHERE id = ?", (trail_id,))
    karma_reward = 0
    if req.status == "success":
        conn.execute("UPDATE trails SET success_count = success_count + 1 WHERE id = ?", (trail_id,))
        karma_reward = TRAIL_AUTHOR_KARMA_REWARD if signed else 0
        if karma_reward > 0:
            upsert_wisdom(conn, trail["author_id"], trail["author_name"], "unknown",
                          karma_delta=karma_reward, last_action=now())
    conn.commit()
    conn.close()
    return {
        "execution_id": exec_id,
        "trail_id":     trail_id,
        "status":       req.status,
        "signed":       signed,
        "author_karma_awarded": karma_reward
    }

@app.post("/trails/{trail_id}/rate")
def rate_trail_execution(trail_id: str, req: TrailRating):
    if not (1 <= req.rating <= 5):
        raise HTTPException(400, "rating must be 1..5")
    conn = get_db()
    ex = conn.execute(
        "SELECT * FROM trail_executions WHERE id = ? AND trail_id = ?",
        (req.execution_id, trail_id)).fetchone()
    if not ex:
        conn.close()
        raise HTTPException(404, "execution not found")
    if ex["rating"] is not None:
        conn.close()
        raise HTTPException(409, "execution already rated")
    trail = conn.execute("SELECT author_id FROM trails WHERE id = ?", (trail_id,)).fetchone()
    if trail and trail["author_id"] == ex["executor_id"]:
        conn.close()
        raise HTTPException(403, "author cannot rate own trail execution")
    signed = _verify_agent_signature(req.rater_id, req.signature, req.timestamp, req.nonce) if req.rater_id else False
    conn.execute("UPDATE trail_executions SET rating = ? WHERE id = ?", (req.rating, req.execution_id))
    conn.execute("UPDATE trails SET rating_sum = rating_sum + ?, rating_count = rating_count + 1 WHERE id = ?",
                 (req.rating, trail_id))
    conn.commit()
    conn.close()
    return {"execution_id": req.execution_id, "rating": req.rating, "signed": signed}


@app.get("/billing/summary")
def billing_summary(client: str, month: str):
    """
    Uso mensual de un agente. Interno, sin autenticación.
    month: YYYY-MM
    """
    import re as _re, calendar as _cal
    if not _re.fullmatch(r"\d{4}-\d{2}", month):
        raise HTTPException(400, "month must be YYYY-MM")
    try:
        year, mon = int(month[:4]), int(month[5:7])
        month_start = int(datetime(year, mon, 1).timestamp())
    except ValueError:
        raise HTTPException(400, "month must be YYYY-MM")
    last_day = _cal.monthrange(year, mon)[1]
    month_end = int(datetime(year, mon, last_day, 23, 59, 59).timestamp())
    conn = sqlite3.connect(TRAILS_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM trails WHERE agent_id=? AND timestamp>=? AND timestamp<=?",
        (client, month_start, month_end),
    ).fetchone()
    conn.close()
    trail_count = row["n"] if row else 0
    return {
        "client":     client,
        "month":      month,
        "trails":     trail_count,
        "amount_usd": round(trail_count * 0.003, 6),
    }


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


# ── MCP LAYER ──────────────────────────────────────────────────────────────

import os
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ARGENTUM", host="0.0.0.0", port=8019)


@mcp.tool()
def submit_action(entity_id: str, entity_name: str, entity_type: str, action_type: str, description: str, proof: str = "") -> str:
    """Submit a good action to ARGENTUM for community verification.

    entity_id: your unique identifier (e.g. GitHub username)
    entity_name: display name
    entity_type: 'human' or 'agent'
    action_type: HELP | BUILD | TEACH | FIX | WITNESS | CONNECT | RELEASE
    description: what you did
    proof: URL to evidence (GitHub PR, commit, etc.)"""
    if action_type not in ACTION_TYPES:
        return f"Unknown action_type. Valid: {list(ACTION_TYPES.keys())}"
    action_id = str(uuid.uuid4())[:8]
    karma = ACTION_TYPES[action_type]["karma"]
    conn = get_db()
    conn.execute(
        "INSERT INTO actions (id, entity_id, entity_name, entity_type, action_type, description, proof, karma_value, created_at, system_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (action_id, entity_id, entity_name, entity_type, action_type, description, proof or None, karma, now(), SYSTEM_VERSION))
    conn.commit()
    conn.close()
    return f"Action {action_id} submitted ({action_type}, {karma} karma on verify). Needs attestations (weight >= {WEIGHT_THRESHOLD}) to be verified."


@mcp.tool()
def attest_action(action_id: str, attester_id: str, attester_name: str, note: str = "") -> str:
    """Attest (verify) someone else's action. Your karma weight counts toward verification.

    action_id: the action to attest
    attester_id: your identifier
    attester_name: your display name
    note: optional comment"""
    conn = get_db()
    action = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    if not action:
        conn.close()
        return "Action not found."
    if action["status"] == "verified":
        conn.close()
        return "Action already verified."
    if action["entity_id"] == attester_id:
        conn.close()
        return "Cannot attest your own action."
    existing = conn.execute("SELECT id FROM attestations WHERE action_id = ? AND attester_id = ?", (action_id, attester_id)).fetchone()
    if existing:
        conn.close()
        return "Already attested."

    if attester_id in GENESIS_ATTESTORS:
        attest_weight = 1.0
    else:
        attester_wisdom = conn.execute("SELECT total_karma FROM wisdom WHERE entity_id = ?", (attester_id,)).fetchone()
        attester_karma = attester_wisdom["total_karma"] if attester_wisdom else 0
        attest_weight = max(KARMA_WEIGHT_MIN, min(KARMA_WEIGHT_MAX, attester_karma / KARMA_WEIGHT_BASE))

    attest_id = str(uuid.uuid4())[:8]
    conn.execute(
        "INSERT INTO attestations (id, action_id, attester_id, attester_name, note, created_at, weight) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (attest_id, action_id, attester_id, attester_name, note or None, now(), attest_weight))

    total_weight = conn.execute("SELECT COALESCE(SUM(weight), 0) as w FROM attestations WHERE action_id = ?", (action_id,)).fetchone()["w"]

    verified_now = False
    if total_weight >= WEIGHT_THRESHOLD:
        conn.execute("UPDATE actions SET status = 'verified', verified_at = ? WHERE id = ?", (now(), action_id))
        upsert_wisdom(conn, action["entity_id"], action["entity_name"], action["entity_type"],
                      karma_delta=action["karma_value"], action=True, last_action=now())
        verified_now = True

    upsert_wisdom(conn, attester_id, attester_name, "unknown",
                  karma_delta=ACTION_TYPES["WITNESS"]["karma"], attestation=True)
    conn.commit()
    conn.close()

    status = "VERIFIED" if verified_now else f"weight {round(total_weight, 2)}/{WEIGHT_THRESHOLD}"
    return f"Attested (weight {round(attest_weight, 2)}). Action status: {status}. You earned {ACTION_TYPES['WITNESS']['karma']} witness karma."


@mcp.tool()
def get_karma(entity_id: str) -> str:
    """Check an entity's karma, verified actions, and attestations given.

    entity_id: the entity to look up"""
    conn = get_db()
    wisdom = conn.execute("SELECT * FROM wisdom WHERE entity_id = ?", (entity_id,)).fetchone()
    conn.close()
    if not wisdom:
        return f"Entity '{entity_id}' not found in ARGENTUM."
    w = dict(wisdom)
    return f"{w['entity_name']} ({w['entity_type']}): {w['total_karma']} karma, {w['verified_actions']} verified actions, {w['attestations_given']} attestations given."


@mcp.tool()
def get_action_detail(action_id: str) -> str:
    """Get details of a specific action including attestations.

    action_id: the action to look up"""
    conn = get_db()
    action = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    if not action:
        conn.close()
        return "Action not found."
    a = dict(action)
    attestations = [dict(r) for r in conn.execute("SELECT attester_name, weight, note, created_at FROM attestations WHERE action_id = ?", (action_id,)).fetchall()]
    total_weight = conn.execute("SELECT COALESCE(SUM(weight), 0) as w FROM attestations WHERE action_id = ?", (action_id,)).fetchone()["w"]
    conn.close()
    lines = [f"Action {a['id']}: {a['action_type']} by {a['entity_name']} — {a['status']}",
             f"  {a['description']}",
             f"  Karma: {a['karma_value']} | Weight: {round(total_weight, 2)}/{WEIGHT_THRESHOLD}"]
    if a.get("proof"):
        lines.append(f"  Proof: {a['proof']}")
    for att in attestations:
        lines.append(f"  ✓ {att['attester_name']} (w={round(att['weight'], 2)}){': ' + att['note'] if att.get('note') else ''}")
    return "\n".join(lines)


@mcp.tool()
def register_trail(author_id: str, author_name: str, name: str, description: str,
                   steps_json: str, price_sats: int) -> str:
    """Register a Mycelium Trail — a verifiable recipe of MCP service calls.

    author_id: your unique identifier
    author_name: your display name
    name: short trail name
    description: what the trail does
    steps_json: JSON list of steps, each {"service": "...", "tool": "...", "note": "..."}
    price_sats: cost in sats per execution
    """
    try:
        steps = _json.loads(steps_json)
    except Exception as e:
        return f"Invalid steps_json: {e}"
    if not isinstance(steps, list) or not steps or len(steps) > MAX_TRAIL_STEPS:
        return f"steps must be a non-empty list of <= {MAX_TRAIL_STEPS} items"
    for s in steps:
        if not isinstance(s, dict) or "service" not in s or "tool" not in s:
            return "each step needs {service, tool}"
    if price_sats < MIN_TRAIL_PRICE:
        return f"price_sats must be >= {MIN_TRAIL_PRICE}"
    trail_id = str(uuid.uuid4())[:8]
    conn = get_db()
    conn.execute(
        "INSERT INTO trails (id, author_id, author_name, name, description, steps, price_sats, output_schema, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (trail_id, author_id, author_name, name, description,
         _json.dumps(steps), price_sats, None, now()))
    conn.commit()
    conn.close()
    return f"Trail {trail_id} registered: '{name}' ({len(steps)} steps, {price_sats} sats)."


@mcp.tool()
def list_trails(sort: str = "reputation", limit: int = 20) -> str:
    """List Mycelium Trails available for execution.

    sort: reputation | popular | recent | rating
    limit: how many to show (default 20, max 50)
    """
    conn = get_db()
    order = {
        "reputation": "ORDER BY (CAST(success_count AS REAL) / MAX(executions, 1)) DESC, executions DESC",
        "popular":    "ORDER BY executions DESC",
        "recent":     "ORDER BY created_at DESC",
        "rating":     "ORDER BY (CAST(rating_sum AS REAL) / MAX(rating_count, 1)) DESC, rating_count DESC",
    }.get(sort, "ORDER BY created_at DESC")
    rows = conn.execute(f"SELECT * FROM trails {order} LIMIT ?", (min(limit, 50),)).fetchall()
    conn.close()
    if not rows:
        return "No trails yet."
    lines = [f"Mycelium Trails (sort={sort}):"]
    for r in rows:
        d = dict(r)
        sr = (d["success_count"] / d["executions"]) if d["executions"] else None
        sr_str = f"{round(sr*100)}%" if sr is not None else "—"
        avg = (d["rating_sum"] / d["rating_count"]) if d["rating_count"] else None
        avg_str = f"{round(avg, 1)}★" if avg is not None else "—"
        lines.append(f"  {d['id']} {d['name']} — {d['price_sats']} sats | "
                     f"{d['executions']} runs ({sr_str} ok, {avg_str}) by {d['author_name']}")
    return "\n".join(lines)


@mcp.tool()
def get_trail(trail_id: str) -> str:
    """Get details of a Mycelium Trail including its step sequence.

    trail_id: the trail id"""
    conn = get_db()
    row = conn.execute("SELECT * FROM trails WHERE id = ?", (trail_id,)).fetchone()
    conn.close()
    if not row:
        return "Trail not found."
    d = dict(row)
    steps = _json.loads(d["steps"])
    sr = (d["success_count"] / d["executions"]) if d["executions"] else None
    sr_str = f"{round(sr*100)}%" if sr is not None else "—"
    avg = (d["rating_sum"] / d["rating_count"]) if d["rating_count"] else None
    avg_str = f"{round(avg, 2)}★ ({d['rating_count']})" if avg is not None else "—"
    lines = [
        f"Trail {d['id']}: {d['name']}",
        f"  by {d['author_name']} — {d['price_sats']} sats",
        f"  {d['description']}",
        f"  Stats: {d['executions']} runs, {sr_str} success, {avg_str}",
        f"  Steps:"
    ]
    for i, s in enumerate(steps, 1):
        note = f" — {s.get('note')}" if s.get('note') else ""
        lines.append(f"    {i}. {s['service']}.{s['tool']}{note}")
    return "\n".join(lines)


@mcp.tool()
def execute_trail(trail_id: str, executor_id: str, executor_name: str,
                  status: str = "success", output_hash: str = "",
                  payment_hash: str = "") -> str:
    """Record execution of a Mycelium Trail. The executor self-attests success or failure.

    trail_id: the trail being executed
    executor_id: your unique identifier
    executor_name: your display name
    status: 'success' or 'fail'
    output_hash: optional sha256 of the output
    payment_hash: optional Lightning payment hash
    """
    if status not in ("success", "fail"):
        return "status must be 'success' or 'fail'"
    conn = get_db()
    trail = conn.execute("SELECT * FROM trails WHERE id = ?", (trail_id,)).fetchone()
    if not trail:
        conn.close()
        return "Trail not found."
    exec_id = str(uuid.uuid4())[:8]
    conn.execute(
        "INSERT INTO trail_executions (id, trail_id, executor_id, executor_name, status, output_hash, payment_hash, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (exec_id, trail_id, executor_id, executor_name, status,
         output_hash or None, payment_hash or None, now()))
    conn.execute("UPDATE trails SET executions = executions + 1 WHERE id = ?", (trail_id,))
    karma_awarded = 0
    if status == "success":
        conn.execute("UPDATE trails SET success_count = success_count + 1 WHERE id = ?", (trail_id,))
        upsert_wisdom(conn, trail["author_id"], trail["author_name"], "unknown",
                      karma_delta=TRAIL_AUTHOR_KARMA_REWARD, last_action=now())
        karma_awarded = TRAIL_AUTHOR_KARMA_REWARD
    conn.commit()
    conn.close()
    return (f"Execution {exec_id} recorded ({status}). "
            f"Author {trail['author_name']} earned {karma_awarded} karma.")


@mcp.tool()
def rate_trail(trail_id: str, execution_id: str, rating: int) -> str:
    """Rate a Trail execution 1..5. Cannot rate own trail.

    trail_id: the trail
    execution_id: the execution to rate
    rating: 1..5
    """
    if not (1 <= rating <= 5):
        return "rating must be 1..5"
    conn = get_db()
    ex = conn.execute(
        "SELECT * FROM trail_executions WHERE id = ? AND trail_id = ?",
        (execution_id, trail_id)).fetchone()
    if not ex:
        conn.close()
        return "Execution not found."
    if ex["rating"] is not None:
        conn.close()
        return "Execution already rated."
    trail = conn.execute("SELECT author_id FROM trails WHERE id = ?", (trail_id,)).fetchone()
    if trail and trail["author_id"] == ex["executor_id"]:
        conn.close()
        return "Author cannot rate own trail execution."
    conn.execute("UPDATE trail_executions SET rating = ? WHERE id = ?", (rating, execution_id))
    conn.execute("UPDATE trails SET rating_sum = rating_sum + ?, rating_count = rating_count + 1 WHERE id = ?",
                 (rating, trail_id))
    conn.commit()
    conn.close()
    return f"Rated execution {execution_id} with {rating}★."


@mcp.tool()
def get_leaderboard(top: int = 10) -> str:
    """Get the karma leaderboard — top entities by reputation.

    top: how many to show (default 10)"""
    conn = get_db()
    rows = conn.execute("SELECT * FROM wisdom ORDER BY total_karma DESC LIMIT ?", (min(top, 50),)).fetchall()
    conn.close()
    if not rows:
        return "No entities yet."
    lines = ["ARGENTUM Leaderboard:"]
    for i, r in enumerate(rows, 1):
        lines.append(f"  {i}. {r['entity_name']} — {r['total_karma']} karma ({r['verified_actions']} actions, {r['attestations_given']} attestations)")
    return "\n".join(lines)


@app.post("/external/trail")
async def external_trail(request: Request):
    """Registra un trail de implementación externa y acumula karma según conformance tier.

    Tier 1.0 (nexus): usa /nexus/trail — requiere anchor on-chain.
    Tier 0.7 (aps, nobulex): conformance_source registrado en payg_accounts.
    Tier 0.2 (default): action_ref válido, source desconocido.

    No ancla on-chain — el anchor es diferencial del tier nexus.
    Seguridad: api_key vincula agent_id (no autodeclarado), conformance_source
    viene del registro de la cuenta (no del cuerpo), action_ref es nonce único.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    action_ref = (body.get("action_ref") or "").strip()
    api_key    = (body.get("api_key") or "").strip()

    if not (action_ref and api_key):
        return JSONResponse({"error": "action_ref, api_key required"}, status_code=400)

    import re
    if not re.fullmatch(r"[0-9a-f]{64}", action_ref):
        return JSONResponse({"error": "action_ref must be 64 hex chars (SHA-256)"}, status_code=422)

    account = mycelium_trails.get_payg_account(TRAILS_DB, api_key)
    if not account:
        return JSONResponse({"error": "api_key not found"}, status_code=401)

    # agent_id viene del registro de la cuenta, no del cuerpo
    agent_id = account["agent_id"]

    # replay protection: cada action_ref es nonce único
    if mycelium_trails.has_external_nonce(TRAILS_DB, action_ref):
        return JSONResponse({"error": "action_ref already processed"}, status_code=409)

    # tier viene del registro de la cuenta, no del cuerpo
    conformance_source = (account.get("conformance_source") or "").strip().lower()
    weight = CONFORMANCE_TIER.get(conformance_source, KARMA_DEFAULT_WEIGHT)

    mycelium_trails.record_external_nonce(TRAILS_DB, action_ref, agent_id)

    conn = get_db()
    upsert_wisdom(conn, agent_id, agent_id, "agent",
                  karma_delta=weight, action=True,
                  last_action=datetime.now(timezone.utc).isoformat())
    conn.commit()
    w = conn.execute("SELECT total_karma_real FROM wisdom WHERE entity_id = ?", (agent_id,)).fetchone()
    conn.close()

    return JSONResponse({
        "ok": True,
        "agent_id": agent_id,
        "action_ref": action_ref,
        "source": conformance_source or "unknown",
        "karma_delta": weight,
        "karma_total": w["total_karma_real"] if w else weight,
        "tier": "conformance_verified" if conformance_source in CONFORMANCE_TIER else "default",
    }, status_code=201)


@app.post("/nexus/trail")
async def nexus_trail(request: Request):
    """Registra un trail desde un receipt externo NEXUS.

    NEXUS (nexus-agent-xa12.onrender.com) no usa firma Ed25519 — la autenticación
    es la recomputación del action_ref desde los 4 preimage fields. Si el action_ref
    no coincide, el trail se rechaza.

    Body: receipt NEXUS (packet_version 1.0):
      {action_ref, service, preimage: {agent_id, action_type, scope, ts},
       payment_hash, output_hash, hash_algo, preimage_format, timestamp, ...}
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    action_ref = body.get("action_ref", "")
    service = body.get("service", "")
    payment_hash = body.get("payment_hash", "") or ""
    negotiation_ref = body.get("negotiation_ref") or None
    preimage = body.get("preimage") or {}
    _origin_raw = body.get("origin", "nexus")
    origin_val = _origin_raw if _origin_raw in ("nexus", "pioneer") else "nexus"

    agent_id = preimage.get("agent_id", "")
    action_type = preimage.get("action_type", "")
    scope = preimage.get("scope", "")
    ts = preimage.get("ts")

    if not (action_ref and service and agent_id and action_type and ts is not None):
        return JSONResponse(
            {"error": "action_ref, service, preimage.{agent_id,action_type,scope,ts} required"},
            status_code=400,
        )

    # Recomputar action_ref para validar integridad del receipt
    import json as _json2
    canonical = _json2.dumps(
        dict(sorted({"agent_id": agent_id, "action_type": action_type,
                     "scope": scope or "", "timestamp": str(ts)}.items())),
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    expected = hashlib.sha256(canonical).hexdigest()

    # NEXUS usa preimage_format "agent_id:action_type:scope:ts" (colon-separated)
    # pero el spec action-ref.md v1.0 usa JCS. Aceptamos ambos durante transición.
    if action_ref != expected:
        colon_payload = f"{agent_id}:{action_type}:{scope or ''}:{int(ts)}"
        colon_ref = hashlib.sha256(colon_payload.encode("utf-8")).hexdigest()
        if action_ref != colon_ref:
            return JSONResponse(
                {"error": "action_ref mismatch — receipt tampered or preimage incorrect"},
                status_code=422,
            )

    # Consume PAYG credit before hitting Free monthly limit
    payg_account = mycelium_trails.get_payg_account_by_agent(TRAILS_DB, agent_id)
    payg_consumed = False
    if payg_account:
        payg_consumed = mycelium_trails.consume_payg_credit(TRAILS_DB, payg_account["api_key"])

    trail_id = mycelium_trails.record_trail(
        TRAILS_DB,
        agent_id=agent_id,
        service=service,
        operation=action_type,
        nonce=action_ref,          # action_ref es el nonce determinístico
        karma_at_time=None,
        success=True,
        scope=scope or None,
        delegation_ref=payment_hash or None,  # payment_hash externo NEXUS
        negotiation_ref=negotiation_ref,
        skip_monthly_limit=payg_consumed,
        origin=origin_val,
    )

    if trail_id:
        _conn = mycelium_trails._connect(TRAILS_DB)
        _conn.execute("UPDATE trails SET action_ref = ? WHERE trail_id = ?", (action_ref, trail_id))
        _conn.close()

        # Anchor on-chain en background — no bloquea la respuesta al cliente
        # Karma solo si el anchor es exitoso (tx_hash != null): karma = actividad verificable on-chain
        TRAIL_KARMA_DELTA = 1
        if _ARB_PAY_OK:
            def _do_anchor(tid: str, aref: str, aid: str, orig: str):
                tx = _arb_pay.anchor_action_ref(aref)
                if tx:
                    mycelium_trails.set_trail_tx_hash(TRAILS_DB, tid, tx)
                    # Karma solo para trails de clientes externos (origin=nexus)
                    if orig == "nexus":
                        conn = get_db()
                        upsert_wisdom(conn, aid, aid, "agent",
                                      karma_delta=TRAIL_KARMA_DELTA, action=True,
                                      last_action=datetime.now(timezone.utc).isoformat())
                        conn.commit()
                        conn.close()
            _threading.Thread(target=_do_anchor, args=(trail_id, action_ref, agent_id, "nexus"), daemon=True).start()
        else:
            # Anchor deshabilitado — no sumar karma (sin verificación on-chain)
            pass

    if trail_id is None:
        if payg_consumed:
            # Refund the credit — record_trail failed for another reason (daily cap, invalid input)
            mycelium_trails.topup_payg(TRAILS_DB, payg_account["api_key"], 1)
        used_month = mycelium_trails.count_trails_this_month(TRAILS_DB, agent_id)
        if used_month >= mycelium_trails.MONTHLY_LIMIT_FREE:
            if _SMTP_OK:
                _smtp.notify_trail_limit(agent_id, used_month, mycelium_trails.MONTHLY_LIMIT_FREE)
            return JSONResponse({
                "error": "monthly_limit_exceeded",
                "limit": mycelium_trails.MONTHLY_LIMIT_FREE,
                "used": used_month,
                "tier": "free",
                "upgrade": "https://argentum-api.rgiskard.xyz/docs#payg",
            }, status_code=429)
        return JSONResponse({"error": "rate limit exceeded"}, status_code=429)

    return JSONResponse({
        "trail_id": trail_id,
        "agent_id": agent_id,
        "service": service,
        "operation": action_type,
        "action_ref": action_ref,
        "negotiation_ref": negotiation_ref,
        "payment_hash": payment_hash or None,
        "trail_status": "committed",
        "anchor": "pending" if _ARB_PAY_OK else "disabled",
    }, status_code=201)


DOCUSEAL_TOKEN    = os.environ.get("DOCUSEAL_TOKEN", "")
PIONEER_AGENT_API = os.environ.get("PIONEER_AGENT_API", "http://localhost:8030")
ADMIN_TOKEN       = os.environ.get("ADMIN_TOKEN", "")

# Hosts autorizados para fetch de PDFs DocuSeal — SSRF allowlist
_DOCUSEAL_ALLOWED_HOSTS = {"api.docuseal.com", "api.docuseal.co", "app.docuseal.com", "docuseal.com"}

import socket as _socket
from urllib.parse import urlparse as _urlparse
import ipaddress as _ipaddress

_PRIVATE_NETWORKS = [
    _ipaddress.ip_network(r) for r in (
        "127.0.0.0/8", "::1/128", "10.0.0.0/8",
        "172.16.0.0/12", "192.168.0.0/16",
        "169.254.0.0/16", "0.0.0.0/8", "fc00::/7",
    )
]

def _safe_docuseal_url(url: str) -> bool:
    """Devuelve True solo si la URL es https y apunta a un host DocuSeal conocido y público."""
    try:
        parsed = _urlparse(url)
        if parsed.scheme != "https":
            return False
        host = parsed.hostname or ""
        if host not in _DOCUSEAL_ALLOWED_HOSTS:
            return False
        # Resolver DNS y rechazar IPs privadas/loopback
        for _, _, _, _, sockaddr in _socket.getaddrinfo(host, None):
            ip = _ipaddress.ip_address(sockaddr[0])
            if any(ip in net for net in _PRIVATE_NETWORKS):
                return False
        return True
    except Exception:
        return False


@app.post("/webhook/docuseal")
async def docuseal_webhook(request: Request):
    """Webhook DocuSeal — dispara trail de activación RSA cuando un documento se completa.

    DocuSeal envía event_type='form.completed' cuando todos los firmantes firman.
    Computa negotiation_ref = SHA-256(PDF bytes) y delega el trail a Pioneer.
    Autenticación: header X-DocuSeal-Token contra DOCUSEAL_TOKEN env var.
    """
    # Log only header names (not values) to identify DocuSeal's auth header
    import logging as _log
    _REDACT = {"authorization", "cookie", "x-auth-token", "x-docuseal-token",
               "x-docuseal-signature", "x-webhook-token", "x-api-key"}
    _log.warning("DOCUSEAL_WEBHOOK header names: %s",
                 [k for k in request.headers.keys() if k.lower() not in _REDACT])

    # Fail-closed: si el token no está configurado el endpoint no opera
    if not DOCUSEAL_TOKEN:
        raise HTTPException(503, "webhook not configured")
    sig = (
        request.headers.get("X-DocuSeal-Signature")
        or request.headers.get("X-DocuSeal-Token")
        or request.headers.get("X-Webhook-Token")
        or ""
    )
    if not sig or not hmac.compare_digest(sig, DOCUSEAL_TOKEN):
        raise HTTPException(401, "Invalid DocuSeal token")

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    event_type = body.get("event_type", "")
    if event_type not in ("form.completed", "submission.completed"):
        return JSONResponse({"status": "ignored", "event_type": event_type})

    data = body.get("data", {})

    # Payload structure: submitter data at top level (email, role) + submission nested
    submission_id = data.get("submission", {}).get("id") or data.get("id", "")
    signer_email  = data.get("email", "")

    # Signed contract PDF — first document in documents[], fallback to audit_log_url
    documents = data.get("documents", [])
    document_url = (documents[0].get("url") if documents else None) or data.get("audit_log_url", "")

    # Descargar PDF para computar SHA-256
    # — solo si la URL pasa la allowlist SSRF; token NO se reenvía a URL externa
    negotiation_ref = None
    if document_url and _safe_docuseal_url(document_url):
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                pdf_resp = await client.get(document_url)
                if pdf_resp.status_code == 200:
                    negotiation_ref = hashlib.sha256(pdf_resp.content).hexdigest()
        except Exception:
            pass

    # Delegar trail a Pioneer via endpoint interno
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            pioneer_resp = await client.post(
                f"{PIONEER_AGENT_API}/trigger/rsa_activation",
                json={
                    "submission_id": str(submission_id),
                    "signer_email":  signer_email,
                    "negotiation_ref": negotiation_ref,
                    "scope": "mycelium.safeagent",
                },
            )
            pioneer_ok = pioneer_resp.status_code == 200
    except Exception:
        pioneer_ok = False

    # Fallback: registrar trail directamente desde argentum si Pioneer no está disponible
    if not pioneer_ok:
        import time as _t, json as _j
        ts_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        canonical = _j.dumps(
            {"action_type": "rsa_activation", "agent_id": "pioneer-agent-001",
             "scope": "mycelium.safeagent", "timestamp": ts_str},
            separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        action_ref = hashlib.sha256(canonical).hexdigest()
        trail_id = mycelium_trails.record_trail(
            TRAILS_DB,
            agent_id="pioneer-agent-001",
            service="mycelium.safeagent",
            operation="rsa_activation",
            nonce=action_ref,
            success=True,
            scope="mycelium.safeagent",
            negotiation_ref=negotiation_ref,
        )
    else:
        trail_id = None

    if _SMTP_OK and trail_id:
        _smtp.notify_rsa_activation(
            trail_id=trail_id,
            signer_email=signer_email,
            negotiation_ref=negotiation_ref or "",
            action_ref="",
        )

    return JSONResponse({
        "status":          "trail_triggered",
        "submission_id":   str(submission_id),
        "signer_email":    signer_email,
        "negotiation_ref": negotiation_ref,
        "via_pioneer":     pioneer_ok,
        "trail_id":        trail_id,
    })


if __name__ == "__main__":
    import threading
    import uvicorn as _uvicorn

    # REST API on 8017
    def run_rest():
        _uvicorn.run(app, host="0.0.0.0", port=8017)

    threading.Thread(target=run_rest, daemon=True).start()

    # MCP on 8019
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)
