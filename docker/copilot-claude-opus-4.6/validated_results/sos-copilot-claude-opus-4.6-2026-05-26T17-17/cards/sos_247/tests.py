"""Tests for SOS 247 — Biblioplex Tomekeeper.

Artifact Creature — Construct  {4}
3/4
Oracle: When this creature enters, choose up to one —
• Target creature becomes prepared.
• Target creature becomes unprepared.
"""

from __future__ import annotations

from cards.sos.sos_247.card_impl import BiblioplexTomekeeper
from engine.card import Creature
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game


class TestBiblioplexTomekeeperProperties:
    """Static card data should match the SOS 247 spec."""

    def test_name(self) -> None:
        card = BiblioplexTomekeeper(owner=None)
        assert card.name == "Biblioplex Tomekeeper"

    def test_mana_cost(self) -> None:
        card = BiblioplexTomekeeper(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}")

    def test_power_toughness(self) -> None:
        card = BiblioplexTomekeeper(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_is_creature(self) -> None:
        card = BiblioplexTomekeeper(owner=None)
        assert isinstance(card, Creature)

    def test_subtypes(self) -> None:
        card = BiblioplexTomekeeper(owner=None)
        subtypes = getattr(card, "subtypes", set())
        assert "Construct" in subtypes


class TestBiblioplexTomekeeperETB:
    """ETB trigger: choose up to one — prepare or unprepare a target creature."""

    def test_has_enters_trigger(self) -> None:
        """Should have an ETB triggered ability."""
        card = BiblioplexTomekeeper(owner=None)
        assert hasattr(card, "on_enter") or hasattr(card, "etb_triggers") or hasattr(card, "get_triggers")

    def test_prepare_mode_makes_creature_prepared(self) -> None:
        """Choosing the prepare mode should set prepared status on target."""
        game = create_game()
        p1 = game.players[0]
        target = Creature(name="Test Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        target.card_types = {CardType.CREATURE}
        # A creature must have a prepare spell to become prepared
        target.has_prepare_spell = True
        game.get_battlefield(p1).add(target)

        card = BiblioplexTomekeeper(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.chosen_mode = "prepare"
        card.on_enter(game)
        assert getattr(target, "prepared", False) is True

    def test_unprepare_mode_makes_creature_unprepared(self) -> None:
        """Choosing the unprepare mode should clear prepared status on target."""
        game = create_game()
        p1 = game.players[0]
        target = Creature(name="Test Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        target.card_types = {CardType.CREATURE}
        target.prepared = True
        game.get_battlefield(p1).add(target)

        card = BiblioplexTomekeeper(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.chosen_mode = "unprepare"
        card.on_enter(game)
        assert getattr(target, "prepared", False) is False

    def test_choose_none_is_valid(self) -> None:
        """'Choose up to one' means choosing zero modes is legal — no-op."""
        game = create_game()
        p1 = game.players[0]
        card = BiblioplexTomekeeper(owner=p1, controller=p1)
        card.chosen_targets = []
        card.chosen_mode = None
        # Should not raise
        card.on_enter(game)

    def test_prepare_requires_prepare_spell(self) -> None:
        """Only creatures with prepare spells can become prepared."""
        game = create_game()
        p1 = game.players[0]
        target = Creature(name="Vanilla Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        target.card_types = {CardType.CREATURE}
        target.has_prepare_spell = False
        game.get_battlefield(p1).add(target)

        card = BiblioplexTomekeeper(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.chosen_mode = "prepare"
        card.on_enter(game)
        # Target without prepare spell should NOT become prepared
        assert getattr(target, "prepared", False) is False
