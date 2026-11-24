"""Vector key gate: fixtures that claim an external schema carry no invented fields.

argentum-core#96 first shipped farley-receipt-signature payloads with "tool"
where draft-farley-acta-signed-receipts-03 §3.1.1 requires "tool_name". Both
verifiers passed: the signature covers whatever bytes are there. This gate
checks what they don't.
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_vector_keys as gate  # noqa: E402

FARLEY = ROOT / "examples/conformance/farley-receipt-signature"
SPEC = (ROOT / "docs/spec/vendor/draft-farley-acta-signed-receipts-03.txt").read_text(encoding="utf-8")


def test_manifest_sets_pass():
    assert gate.check_manifest() == []


def test_catches_invented_field(tmp_path):
    # Replay the original #96 error: tool_name -> tool.
    for p in FARLEY.glob("*.json"):
        doc = json.loads(p.read_text(encoding="utf-8"))
        text = json.dumps(doc).replace('"tool_name"', '"tool"')
        (tmp_path / p.name).write_text(text, encoding="utf-8")
    assert "tool" in gate.unbacked_keys(SPEC, tmp_path, {"index.json"})


def test_common_word_in_prose_does_not_back_a_field():
    assert "tool" in SPEC and gate.field_uses(SPEC, "tool") == 0


def test_spec_hash_is_pinned(tmp_path, monkeypatch):
    manifest = json.loads(gate.MANIFEST.read_text(encoding="utf-8"))
    bad = copy.deepcopy(manifest)
    bad["sets"][0]["spec_sha256"] = "0" * 64
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    monkeypatch.setattr(gate, "MANIFEST", path)
    assert any("spec_sha256" in e for e in gate.check_manifest())


# ---- the gate must not pass on nothing ---------------------------------------------------------------

def _manifest(tmp_path, monkeypatch, mutate):
    manifest = json.loads(gate.MANIFEST.read_text(encoding="utf-8"))
    mutate(manifest)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(gate, "MANIFEST", path)
    return gate.check_manifest()


def test_manifest_without_sets_fails(tmp_path, monkeypatch):
    errs = _manifest(tmp_path, monkeypatch, lambda m: m.update(sets=[]))
    assert any("no sets" in e for e in errs)


def test_set_with_no_json_keys_fails(tmp_path, monkeypatch):
    empty = tmp_path / "empty_vectors"
    empty.mkdir()
    errs = _manifest(tmp_path, monkeypatch, lambda m: m["sets"][0].update(vectors=str(empty)))   # absolute path replaces ROOT / ...
    assert any("no JSON keys" in e for e in errs)


def test_set_whose_files_are_all_excluded_fails(tmp_path, monkeypatch):
    errs = _manifest(tmp_path, monkeypatch,
                     lambda m: m["sets"][0].update(exclude=[p.name for p in FARLEY.glob("*.json")]))
    assert any("no JSON keys" in e for e in errs)


def test_cli_mode_on_empty_dir_fails(tmp_path, capsys):
    spec = tmp_path / "spec.txt"
    spec.write_text("anything", encoding="utf-8")
    empty = tmp_path / "e"
    empty.mkdir()
    assert gate.main([str(spec), str(empty)]) == 1
    assert "no JSON keys" in capsys.readouterr().out
