"""Audited tests for FDN 001 — Plains (Basic Land)."""

from __future__ import annotations

import pytest

from card_impl import Plains


class TestPlains:
    """Plains is a Basic Land that taps for {W}."""

    @pytest.mark.basic
    def test_plains_is_land(self) -> None:
        from engine.card import Land
        card = Plains(name="Plains", owner=None)
        assert isinstance(card, Land)

    @pytest.mark.basic
    def test_plains_taps_for_white_mana(self) -> None:
        card = Plains(name="Plains", owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) > 0
        assert any("{W}" in a.description for a in abilities)

    @pytest.mark.basic
    def test_plains_name(self) -> None:
        card = Plains(name="Plains", owner=None)
        assert card.name == "Plains"
