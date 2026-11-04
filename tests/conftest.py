"""Existing app tests assert on the legacy page at "/"; keep them on it unless a test opts in."""
import pytest


@pytest.fixture(autouse=True)
def _legacy_ui_by_default(monkeypatch):
    monkeypatch.setenv("SARTHI_UI", "legacy")
