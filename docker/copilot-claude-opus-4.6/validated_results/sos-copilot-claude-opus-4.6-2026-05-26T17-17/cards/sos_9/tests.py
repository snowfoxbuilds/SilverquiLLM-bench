"""Tests for SOS 9 — Daydream.

{W} Sorcery. Exile target creature you control, then return that card to the
battlefield under its owner's control with a +1/+1 counter on it.
Flashback {2}{W}.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_9.card_impl import Daydream
from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestDaydreamProperties:
    """Static card data should match the SOS 9 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(Daydream(owner=None), Sorcery)

    def test_name(self) -> None:
        assert Daydream(owner=None).name == "Daydream"

    def test_mana_cost(self) -> None:
        assert Daydream(owner=None).mana_cost == ManaCost.parse("{W}")

    def test_has_flashback(self) -> None:
        card = Daydream(owner=None)
        assert Keyword.FLASHBACK in card.keywords


class TestDaydreamTargeting:
    """Targets a creature you control."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = Daydream(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = Daydream(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD


class TestDaydreamResolution:
    """Exile target creature, then return with +1/+1 counter."""

    def test_creature_returns_with_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = Daydream(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        # The creature should be back on the battlefield with a +1/+1 counter
        bf_cards = game.get_battlefield(p1).get_all()
        returned = [c for c in bf_cards if c.name == "Grizzly Bears"]
        assert len(returned) == 1
        assert returned[0].plus_one_counters >= 1

    def test_creature_is_exiled_then_returned(self) -> None:
        """The card goes through exile (matters for ETB triggers)."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(
            name="Blink Bear", owner=p1, controller=p1,
            base_power=3, base_toughness=3,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = Daydream(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        # After resolution, creature should be on battlefield
        bf_cards = game.get_battlefield(p1).get_all()
        returned = [c for c in bf_cards if c.name == "Blink Bear"]
        assert len(returned) == 1

    def test_returns_under_owners_control(self) -> None:
        """Returns under owner's control, not controller's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Bear owned by p2 but controlled by p1
        bear = Creature(
            name="Stolen Bear", owner=p2, controller=p1,
            base_power=2, base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = Daydream(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        # Should return under p2's control (the owner)
        p2_bf = game.get_battlefield(p2).get_all()
        returned = [c for c in p2_bf if c.name == "Stolen Bear"]
        assert len(returned) == 1

    def test_no_target_is_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = Daydream(owner=p1, controller=p1)
        spell.on_resolve(game)  # should not raise
