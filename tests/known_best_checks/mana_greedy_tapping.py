"""Pytest plugin for ``mana_payment_presentation_checks.py``: the payer taps
every mana source on offer while a cost is paid (``mana_during_payment.GREEDY``)."""

import pytest

import mana_during_payment
from mana_during_payment import _mana_abilities_offered_during_payment  # noqa: F401


@pytest.fixture(autouse=True)
def _greedy(monkeypatch):
    monkeypatch.setattr(mana_during_payment, "GREEDY", True)
