from datetime import date

import pytest

from sarthi.core.parse_values import parse_date_in, parse_inr


@pytest.mark.parametrize("s", ["Rs. 1,20,000/-", "₹1.2 lakh", "INR 120000", "१,२०,०००", "Rs 1.2 lac"])
def test_parse_inr_120000(s):
    assert parse_inr(s) == 120000


def test_parse_inr_crore_and_garbage():
    assert parse_inr("2 crore") == 20000000
    assert parse_inr("1.5 cr") == 15000000
    assert parse_inr("abc") is None
    assert parse_inr("") is None


def test_parse_inr_paise_rounds_half_up():
    assert parse_inr("Rs. 100.50") == 101
    assert parse_inr("Rs. 100.49") == 100


def test_parse_date_photo_ambiguous():
    assert parse_date_in("04/05/2024", from_photo=True) == (date(2024, 5, 4), True)


def test_parse_date_not_ambiguous_cases():
    assert parse_date_in("25/12/2023", from_photo=True) == (date(2023, 12, 25), False)
    assert parse_date_in("5 March 2024", from_photo=True) == (date(2024, 3, 5), False)
    assert parse_date_in("04/05/2024", from_photo=False) == (date(2024, 5, 4), False)
    assert parse_date_in("05/05/2024", from_photo=True) == (date(2024, 5, 5), False)


def test_parse_date_formats_and_garbage():
    assert parse_date_in("05-Mar-2024", from_photo=False) == (date(2024, 3, 5), False)
    assert parse_date_in("05.03.2024", from_photo=False) == (date(2024, 3, 5), False)
    assert parse_date_in("12-25-2023", from_photo=False) == (None, False)  # never MM/DD
    assert parse_date_in("31/02/2024", from_photo=False) == (None, False)
    assert parse_date_in("nope", from_photo=False) == (None, False)
