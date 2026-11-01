from sarthi.core.inputs import KNOWN_INPUTS, REJECTION_GROUNDS


def test_known_inputs_exact_twelve():
    assert len(KNOWN_INPUTS) == 12
    assert "continuous_cover_months" in KNOWN_INPUTS and "reasons_cite_terms" in KNOWN_INPUTS


def test_rejection_grounds_unique_and_has_other():
    assert len(set(REJECTION_GROUNDS)) == len(REJECTION_GROUNDS)
    assert "other" in REJECTION_GROUNDS
