# Keep the module-level nonce cache in memory during tests (no .agent_signing_nonces.db in the repo).
import os

os.environ.setdefault("AGENT_SIGNING_NONCE_DB", ":memory:")
