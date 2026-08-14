"""Conformance test: verify_chain() reporta negotiation_linkage explícito.

Cierra un gap señalado por Henri Sirkkavaara (draft-sirkkavaara-vaara-receipt,
IETF scitt@ietf.org, 2026-08-14) sobre draft-fassbender-scitt-time-anchor-03:
si un campo de vinculación es opcional y nunca entra en el commitment central,
un verificador que llega a un resultado con el campo ausente y uno que llega a
un resultado con el campo presente deben ser distinguibles en el output, no
solo en la cabeza de quien audita. negotiation-ref.md invariante 4 ya decía
que la ausencia "no hace ninguna afirmación" -- pero eso era una garantía de
la spec, no del resultado del verificador. Estos tests cierran esa brecha.
"""
import os
import sys
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import mycelium_trails


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "trails.db")
    mycelium_trails.init_db(db_path)
    return db_path


def test_verify_chain_reports_absent_when_no_negotiation_ref(db):
    trail_id = mycelium_trails.record_trail(
        db, "agent-linkage-test", "oasis", "enter", uuid.uuid4().hex, karma_at_time=10,
    )
    result = mycelium_trails.verify_chain(db, trail_id)
    assert result["valid"] is True
    assert result["negotiation_linkage"] == "absent"


def test_verify_chain_reports_present_when_negotiation_ref_set(db):
    trail_id = mycelium_trails.record_trail(
        db, "agent-linkage-test", "oasis", "enter", uuid.uuid4().hex, karma_at_time=10,
        negotiation_ref="a0e8bc2658eee9266d87d56b205a5f01e5b1ecc445f0693b3bba46cb8764ad52",
    )
    result = mycelium_trails.verify_chain(db, trail_id)
    assert result["valid"] is True
    assert result["negotiation_linkage"] == "present"


def test_negotiation_linkage_present_but_unverified_by_construction(db):
    """negotiation-ref.md invariante 3: Mycelium nunca valida el artefacto referenciado.

    "present" significa "el campo está seteado", no "el artefacto fue verificado" --
    un negotiation_ref inventado/sin sentido produce el mismo "present" que uno real,
    porque la validación del artefacto es responsabilidad de quien consulta, no de
    Mycelium. El test documenta ese límite explícitamente para que no se lea como
    una garantía más fuerte de la que el campo ofrece.
    """
    trail_id = mycelium_trails.record_trail(
        db, "agent-linkage-test", "oasis", "enter", uuid.uuid4().hex, karma_at_time=10,
        negotiation_ref="not-a-real-hash-just-a-string",
    )
    result = mycelium_trails.verify_chain(db, trail_id)
    assert result["negotiation_linkage"] == "present"


def test_negotiation_linkage_present_on_broken_chain(db):
    """La distinción sobrevive incluso cuando la cadena falla por otra razón --
    negotiation_linkage no depende del resultado de valid."""
    result = mycelium_trails.verify_chain(db, "trail-id-que-no-existe")
    assert result["valid"] is False
    assert result["reason"] == "trail_not_found"
    assert result["negotiation_linkage"] == "absent"
