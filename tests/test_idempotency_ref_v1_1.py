"""idempotency-ref-v1.1: four-case logical-identity vectors.

Pins the test defined by impartshadow (crewAIInc/crewAI#5802) and
stringsofthemind-oss/once#45: same payload can be new work (case 3), same
identity cannot drift (case 4). Also pins that v1.1 is additive: the v1.0
fixture's idempotency_ref is unchanged.
"""
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SET_DIR = ROOT / "examples/conformance/idempotency-ref-v1.1"
sys.path.insert(0, str(ROOT))

from jcs import jcs_dumps  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(f"idem11_{name}", SET_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


build = _load("build")
verify = _load("verify")
DOC = json.loads((SET_DIR / "vectors.json").read_text(encoding="utf-8"))


def _event(doc, eid):
    return next(ev for ev in doc["events"] if ev["id"] == eid)


def test_vectors_json_is_build_output():
    assert json.dumps(build.build(), indent=2, ensure_ascii=False) + "\n" == (
        SET_DIR / "vectors.json"
    ).read_text(encoding="utf-8")


def test_vectors_verify():
    assert verify.verify(DOC) == []


def test_v1_0_fixture_unchanged():
    fx = json.loads((ROOT / "examples/conformance/idempotency-ref-v1.fixture.json").read_text())
    v = fx["vectors"][0]
    ref = hashlib.sha256(jcs_dumps(v["idempotency_artifact"]).encode()).hexdigest()
    assert ref == v["idempotency_ref"] == "4a6aa060624b6e3ec4fafb941a546e5842d0a1172861f6d21ffec9de4b098a97"


def _mut_expected_duplicate(doc):
    _event(doc, "case-4-drifted-retry")["expected"] = "DUPLICATE"


def _mut_same_key_for_b(doc):
    b = _event(doc, "case-3-second-intentional-same-payload")
    b["idempotency_artifact"] = copy.deepcopy(_event(doc, "case-1-first-intentional")["idempotency_artifact"])
    b["idempotency_ref"] = _event(doc, "case-1-first-intentional")["idempotency_ref"]


def _mut_digest_inside(doc):
    ev = _event(doc, "case-4-drifted-retry")
    ev["idempotency_artifact"]["admitted_payload_digest"] = ev["admitted_payload_digest"]
    ev["idempotency_ref"] = verify.sha256hex(ev["idempotency_artifact"])


def _mut_payload_tamper(doc):
    _event(doc, "case-1-first-intentional")["admitted_payload"]["amount_cents"] = 10001


def _mut_negative_divergence(doc):
    doc["negative_vectors"][0]["expected_divergence"]["outcome"] = "EXECUTE"


@pytest.mark.parametrize(
    "mutate",
    [_mut_expected_duplicate, _mut_same_key_for_b, _mut_digest_inside, _mut_payload_tamper, _mut_negative_divergence],
)
def test_mutations_are_caught(mutate):
    doc = copy.deepcopy(DOC)
    mutate(doc)
    assert verify.verify(doc) != []


def test_ledger_without_digest_check_is_caught(monkeypatch):
    real = verify.decide
    monkeypatch.setattr(verify, "decide", lambda ledger, ref, digest, check_digest=True: real(ledger, ref, digest, False))
    assert any(e.startswith("decision_rule") for e in verify.verify(DOC))
