"""init_db() must leave wisdom.total_karma_real on a new database, and keep an existing one intact."""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _argentum(tmp_path):
    sys.modules.pop("argentum", None)
    import argentum
    argentum.DB_PATH = tmp_path / "argentum.db"
    return argentum


def _cols(path):
    conn = sqlite3.connect(path)
    out = [r[1] for r in conn.execute("PRAGMA table_info(wisdom)")]
    conn.close()
    return out


def test_new_database_has_the_column(tmp_path):
    a = _argentum(tmp_path)
    a.init_db()
    assert "total_karma_real" in _cols(a.DB_PATH)


def test_old_database_is_migrated_once_and_values_survive(tmp_path):
    a = _argentum(tmp_path)
    conn = sqlite3.connect(a.DB_PATH)
    conn.execute("CREATE TABLE wisdom (entity_id TEXT PRIMARY KEY, entity_name TEXT NOT NULL, entity_type TEXT NOT NULL, "
                 "total_karma INTEGER DEFAULT 0, verified_actions INTEGER DEFAULT 0, attestations_given INTEGER DEFAULT 0, "
                 "last_action TEXT)")
    conn.execute("INSERT INTO wisdom (entity_id, entity_name, entity_type, total_karma) VALUES ('e', 'e', 'agent', 7)")
    conn.commit()
    conn.close()
    a.init_db()
    conn = sqlite3.connect(a.DB_PATH)
    assert conn.execute("SELECT total_karma, total_karma_real FROM wisdom").fetchone() == (7, 7.0)
    conn.execute("UPDATE wisdom SET total_karma_real = 7.5")
    conn.commit()
    conn.close()
    a.init_db()   # a second run must not overwrite the migrated value
    conn = sqlite3.connect(a.DB_PATH)
    assert conn.execute("SELECT total_karma_real FROM wisdom").fetchone() == (7.5,)
    conn.close()
