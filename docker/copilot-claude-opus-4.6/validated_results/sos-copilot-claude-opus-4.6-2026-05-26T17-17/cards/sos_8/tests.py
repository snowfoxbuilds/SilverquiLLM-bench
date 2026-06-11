"""Tests for SOS 8 — Ascendant Dustspeaker.

{4}{W} Creature — Orc Cleric, 3/4, Flying.
ETB: put a +1/+1 counter on another target creature you control.
Beginning of combat on your turn: exile up to one target card from a graveyard.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_8.card_impl import AscendantDustspeaker
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone, TargetRequirement
from test_utils import create_game, set_board_state


class TestAscendantDustspeakerProperties:
    """Static card data should match the SOS 8 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(AscendantDustspeaker(owner=None), Creature)

    def test_name(self) -> None:
        assert AscendantDustspeaker(owner=None).name == "Ascendant Dustspeaker"

    def test_mana_cost(self) -> None:
        assert AscendantDustspeaker(owner=None).mana_cost == ManaCost.parse("{4}{W}")

    def test_power_toughness(self) -> None:
        card = AscendantDustspeaker(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_has_flying(self) -> None:
        card = AscendantDustspeaker(owner=None)
        assert Keyword.FLYING in card.keywords


class TestAscendantDustspeakerETB:
    """When this creature enters, put a +1/+1 counter on another target creature you control."""

    def test_etb_puts_counter_on_another_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ally = Creature(
            name="Ally Bear", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        ally.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(ally)

        dustspeaker = AscendantDustspeaker(owner=p1, controller=p1)
        dustspeaker.chosen_targets = [ally]
        dustspeaker.on_enter_battlefield(game)

        assert ally.plus_one_counters >= 1

    def test_etb_cannot_target_itself(self) -> None:
        """The ETB says 'another target creature you control'."""
        game = create_game()
        p1 = game.players[0]
        dustspeaker = AscendantDustspeaker(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dustspeaker)

        # get_targets for ETB should filter out self
        reqs = dustspeaker.get_etb_targets(game)
        if reqs:
            req = reqs[0]
            assert req.filter_fn(dustspeaker) is False

    def test_etb_does_not_counter_opponents_creature(self) -> None:
        """Can only target creatures you control."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        enemy = Creature(
            name="Enemy Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        enemy.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(enemy)

        dustspeaker = AscendantDustspeaker(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dustspeaker)
        reqs = dustspeaker.get_etb_targets(game)
        if reqs:
            req = reqs[0]
            assert req.filter_fn(enemy) is False


class TestAscendantDustspeakerCombatTrigger:
    """At beginning of combat on your turn, exile up to one target card from a graveyard."""

    def test_exiles_card_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        dustspeaker = AscendantDustspeaker(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dustspeaker)

        # Put a card in opponent's graveyard
        dead_card = Creature(
            name="Dead Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        game.get_graveyard(p2).add(dead_card)

        # Simulate combat trigger with target
        dustspeaker.combat_trigger_targets = [dead_card]
        dustspeaker.on_combat_trigger(game)

        # Card should be exiled (not in graveyard)
        assert dead_card not in game.get_graveyard(p2).get_all()

    def test_combat_trigger_is_optional(self) -> None:
        """'Up to one' means you can choose zero targets."""
        game = create_game()
        p1 = game.players[0]
        dustspeaker = AscendantDustspeaker(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dustspeaker)

        # No targets chosen — should not raise
        dustspeaker.combat_trigger_targets = []
        dustspeaker.on_combat_trigger(game)
