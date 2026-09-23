import pytest

from agents.budget_allocator import _to_float


@pytest.mark.parametrize("value, expected", [("12.5", 12.5), (7, 7.0), (3.25, 3.25)])
def test_to_float(value, expected):
    assert _to_float(value) == expected
