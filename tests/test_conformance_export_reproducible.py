"""The committed conformance-export.json and conformance-vectors.json must be what the
build scripts produce from the sets on disk.

build_export.py takes a fixed generated_at (argument or SOURCE_DATE_EPOCH), so the whole output
is reproducible. These tests regenerate with a fixed timestamp and require everything except
generated_at to match the committed files: a vector set added without regenerating the export
(as trail-head-cadence-ref and trail-head-shape-ref once were) fails here.

Only files tracked by git are exported, so a set must be `git add`ed to be seen.
"""
import importlib.util
import json
import os
import unittest
from pathlib import Path

CONF = Path(__file__).resolve().parent.parent / "examples" / "conformance"
FIXED = "2000-01-01T00:00:00.000Z"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, CONF / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _without_ts(doc):
    return {k: v for k, v in doc.items() if k != "generated_at"}


class ExportReproducible(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.export_mod = _load("build_export")
        cls.vectors_mod = _load("build_conformance_vectors")
        cls.committed_export = json.loads((CONF / "conformance-export.json").read_text())
        cls.committed_vectors = json.loads((CONF / "conformance-vectors.json").read_text())
        cls.rebuilt_export = cls.export_mod.build("conformance-export.json", FIXED)

    def test_every_set_is_in_the_committed_export(self):
        rebuilt, committed = set(self.rebuilt_export["sets"]), set(self.committed_export["sets"])
        self.assertEqual(sorted(rebuilt - committed), [],
                         "sets on disk but not in conformance-export.json: run build_export.py "
                         "then build_conformance_vectors.py")
        self.assertEqual(sorted(committed - rebuilt), [])

    def test_committed_export_matches_rebuild_except_generated_at(self):
        self.assertEqual(_without_ts(self.rebuilt_export), _without_ts(self.committed_export))

    def test_committed_vectors_match_rebuild_except_generated_at(self):
        rebuilt = self.vectors_mod.build(self.rebuilt_export)
        self.assertEqual(_without_ts(rebuilt), _without_ts(self.committed_vectors))

    def test_vectors_and_export_carry_the_same_generated_at(self):
        self.assertEqual(self.committed_vectors["generated_at"], self.committed_export["generated_at"])

    def test_fixed_timestamp_gives_identical_bytes(self):
        a = json.dumps(self.export_mod.build("conformance-export.json", FIXED), indent=2, ensure_ascii=False)
        b = json.dumps(self.export_mod.build("conformance-export.json", FIXED), indent=2, ensure_ascii=False)
        self.assertEqual(a, b)

    def test_source_date_epoch_is_honoured_and_argument_wins(self):
        old = os.environ.get("SOURCE_DATE_EPOCH")
        try:
            os.environ["SOURCE_DATE_EPOCH"] = "946684800"
            self.assertEqual(self.export_mod.resolve_generated_at(), FIXED)
            self.assertEqual(self.export_mod.resolve_generated_at("2001-02-03T04:05:06.000Z"),
                             "2001-02-03T04:05:06.000Z")
            os.environ["SOURCE_DATE_EPOCH"] = "12x"
            with self.assertRaises(SystemExit):
                self.export_mod.resolve_generated_at()
        finally:
            if old is None:
                os.environ.pop("SOURCE_DATE_EPOCH", None)
            else:
                os.environ["SOURCE_DATE_EPOCH"] = old

    def test_default_is_the_current_time(self):
        os.environ.pop("SOURCE_DATE_EPOCH", None)
        ts = self.export_mod.resolve_generated_at()
        self.assertRegex(ts, r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.000Z\Z")
        self.assertGreater(ts, "2026-11-26")


if __name__ == "__main__":
    unittest.main()
