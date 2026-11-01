import datetime

import pytest

from sarthi.core.expr import UnsafeExpression, evaluate, names

COND = "continuous_cover_months >= 60 and not fraud_alleged"


def test_true_case():
    assert evaluate(COND, {"continuous_cover_months": 74, "fraud_alleged": False}) is True


def test_false_case():
    assert evaluate(COND, {"continuous_cover_months": 59, "fraud_alleged": False}) is False


def test_missing_name_returns_none():
    assert evaluate(COND, {"continuous_cover_months": 74}) is None


def test_none_value_returns_none():
    assert evaluate(COND, {"continuous_cover_months": 74, "fraud_alleged": None}) is None


def test_names():
    assert names(COND) == {"continuous_cover_months", "fraud_alleged"}


@pytest.mark.parametrize(
    "bad",
    [
        "__import__('os')",
        "a.b",
        "f(1)",
        "[x for x in y]",
        "x[0]",
        "lambda: 1",
        "(y := 1) > 0",
        "x == 'a'",
        "x is None",
        "x == None",
        "x ==",
        "x * 2 > 1",
        "-x > 1",
    ],
)
def test_rejected(bad):
    with pytest.raises(UnsafeExpression):
        evaluate(bad, {"x": 1})
    with pytest.raises(UnsafeExpression):
        names(bad)


def test_unsafe_raises_even_if_inputs_missing():
    with pytest.raises(UnsafeExpression):
        evaluate("__import__('os')", {})


def test_chained_comparison():
    assert evaluate("0 <= x < 10", {"x": 5}) is True
    assert evaluate("0 <= x < 10", {"x": 10}) is False


def test_arithmetic_and_negative_constant():
    assert evaluate("a + 1 - b > -1", {"a": 1, "b": 1.5}) is True


def test_bool_constants():
    assert evaluate("x == True", {"x": True}) is True


def test_top_level_arithmetic_rejected():
    with pytest.raises(UnsafeExpression, match="boolean"):
        evaluate("a + 1", {"a": 1})


def test_bare_name_is_boolean():
    assert evaluate("flag", {"flag": True}) is True


def test_non_numeric_input_type_error():
    with pytest.raises(TypeError, match="start"):
        evaluate("start > 1", {"start": datetime.date(2020, 1, 1)})
    with pytest.raises(TypeError, match="s"):
        evaluate("s > 1", {"s": "x"})
