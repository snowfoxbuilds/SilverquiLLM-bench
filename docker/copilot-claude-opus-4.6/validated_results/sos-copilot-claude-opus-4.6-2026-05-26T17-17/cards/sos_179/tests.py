"""Tests for SOS 179 — Cauldron of Essence."""

from __future__ import annotations

import pytest

from cards.sos.sos_179.card_impl import CauldronOfEssence
from engine.card import Artifact, Creature
from engine.types import ManaCost, ManaType
from test_utils import create_game, set_board_state


class TestCauldronOfEssenceProperties:
    """Static card properties match spec."""

    def test_is_artifact(self) -> None:
        assert isinstance(CauldronOfEssence(owner=None), Artifact)

    def test_name(self) -> None:
        assert CauldronOfEssence(owner=None).name == "Cauldron of Essence"

    def test_mana_cost(self) -> None:
        assert CauldronOfEssence(owner=None).mana_cost == ManaCost.parse("{1}{B}{G}")


class TestCauldronDeathTrigger:
    """Whenever a creature you control dies, each opponent loses 1 life and you gain 1 life."""

    def test_creature_dying_drains_opponent(self) -> None:
        game = create_game()
        cauldron = CauldronOfEssence(owner=game.players[0])
        token = Creature(name="Doomed Token", base_power=1, base_toughness=1)
        token.owner = game.players[0]
        set_board_state(game, 0, battlefield=[cauldron, token])
        # Simulate creature dying
        game.destroy(token)
        assert game.players[1].life == 19  # opponent loses 1
        assert game.players[0].life == 21  # controller gains 1

    def test_opponent_creature_dying_does_not_trigger(self) -> None:
        game = create_game()
        cauldron = CauldronOfEssence(owner=game.players[0])
        opp_creature = Creature(name="Opp Creature", base_power=2, base_toughness=2)
        opp_creature.owner = game.players[1]
        set_board_state(game, 0, battlefield=[cauldron])
        set_board_state(game, 1, battlefield=[opp_creature])
        game.destroy(opp_creature)
        # Should not trigger — life totals unchanged
        assert game.players[0].life == 20
        assert game.players[1].life == 20

    def test_multiple_creatures_dying_triggers_multiple_times(self) -> None:
        game = create_game()
        cauldron = CauldronOfEssence(owner=game.players[0])
        c1 = Creature(name="Token A", base_power=1, base_toughness=1)
        c1.owner = game.players[0]
        c2 = Creature(name="Token B", base_power=1, base_toughness=1)
        c2.owner = game.players[0]
        set_board_state(game, 0, battlefield=[cauldron, c1, c2])
        game.destroy(c1)
        game.destroy(c2)
        assert game.players[1].life == 18  # opponent loses 2
        assert game.players[0].life == 22  # controller gains 2


class TestCauldronActivatedAbility:
    """
    {1}{B}{G}, {T}, Sacrifice a creature: Return target creature card from
    your graveyard to the battlefield. Activate only as sorcery.
    """

    def test_returns_creature_from_graveyard_to_battlefield(self) -> None:
        game = create_game()
        cauldron = CauldronOfEssence(owner=game.players[0])
        sacrifice_fodder = Creature(name="Fodder", base_power=1, base_toughness=1)
        sacrifice_fodder.owner = game.players[0]
        target_in_gy = Creature(name="Big Creature", base_power=5, base_toughness=5)
        target_in_gy.owner = game.players[0]
        set_board_state(game, 0, battlefield=[cauldron, sacrifice_fodder],
                        graveyard=[target_in_gy],
                        mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1})
        # Activate the ability targeting Big Creature in graveyard, sacrificing Fodder
        cauldron.activate(game, sacrifice=sacrifice_fodder, target=target_in_gy)
        bf_names = [c.name for c in game.players[0].battlefield]
        assert "Big Creature" in bf_names

    def test_sacrificed_creature_goes_to_graveyard(self) -> None:
        game = create_game()
        cauldron = CauldronOfEssence(owner=game.players[0])
        fodder = Creature(name="Fodder", base_power=1, base_toughness=1)
        fodder.owner = game.players[0]
        target = Creature(name="Target", base_power=3, base_toughness=3)
        target.owner = game.players[0]
        set_board_state(game, 0, battlefield=[cauldron, fodder],
                        graveyard=[target],
                        mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1})
        cauldron.activate(game, sacrifice=fodder, target=target)
        gy_names = [c.name for c in game.players[0].graveyard]
        assert "Fodder" in gy_names

    def test_cauldron_taps_on_activation(self) -> None:
        game = create_game()
        cauldron = CauldronOfEssence(owner=game.players[0])
        fodder = Creature(name="Fodder", base_power=1, base_toughness=1)
        fodder.owner = game.players[0]
        target = Creature(name="Target", base_power=3, base_toughness=3)
        target.owner = game.players[0]
        set_board_state(game, 0, battlefield=[cauldron, fodder],
                        graveyard=[target],
                        mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1})
        cauldron.activate(game, sacrifice=fodder, target=target)
        assert cauldron.tapped is True
