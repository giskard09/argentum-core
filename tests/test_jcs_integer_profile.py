"""JCS integer profile: RFC 8785 serializes numbers as IEEE-754 doubles, so
integers outside +/-(2^53 - 1) are out of profile and must be refused, not
emitted as their exact value (which a conformant verifier would not reproduce)."""
import pytest

from jcs import jcs_dumps


def test_largest_safe_integers_serialize():
    assert jcs_dumps({"n": 2**53 - 1}) == '{"n":9007199254740991}'
    assert jcs_dumps({"n": -(2**53 - 1)}) == '{"n":-9007199254740991}'


@pytest.mark.parametrize("value", [2**53, -(2**53), 2**53 + 1, -(2**53 + 1), 2**256 - 1])
def test_integers_outside_safe_range_are_refused(value):
    with pytest.raises(ValueError, match="out of JCS profile"):
        jcs_dumps({"n": value})


def test_refusal_applies_inside_nested_structures():
    with pytest.raises(ValueError):
        jcs_dumps({"outer": [{"inner": 2**53}]})
