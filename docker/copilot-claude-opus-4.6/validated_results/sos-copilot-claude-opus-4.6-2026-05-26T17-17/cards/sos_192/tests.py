"""Tests for SOS 192 — Grapple with Death."""

from __future__ import annotations

import pytest

from cards.sos.sos_192.card_impl import GrappleWithDeath
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestGrappleWithDeathProperties:
    """Static card data should match SOS 192 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(GrappleWithDeath(owner=None), Sorcery)

    def test_name(self) -> None:
        assert GrappleWithDeath(owner=None).name == "Grapple with Death"

    def test_mana_cost(self) -> None:
        assert GrappleWithDeath(owner=None).mana_cost == ManaCost.parse("{1}{B}{G}")


class TestGrappleWithDeathTargeting:
    """Targeting: target artifact or creature."""

    def test_requires_target(self) -> None:
        game = create_game()
        reqs = GrappleWithDeath(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1

    def test_target_accepts_creature(self) -> None:
        game = create_game()
        req = GrappleWithDeath(owner=None).get_targets(game)[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter(creature) is True

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = GrappleWithDeath(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD


class TestGrappleWithDeathEffect:
    """Resolve: destroy target artifact or creature, gain 1 life."""

    def test_destroys_target_creature(self) -> None:
        game = create_game()
        target = Creature(name="Doomed Bear", base_power=2, base_toughness=2)
        target.owner = game.players[1]
        spell = GrappleWithDeath(owner=game.players[0])
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1})
        set_board_state(game, 1, battlefield=[target])

        cast_spell(game, 0, "Grapple with Death", targets=[target])

        # Target should be in graveyard
        assert target.zone == Zone.GRAVEYARD

    def test_gains_one_life(self) -> None:
        game = create_game()
        target = Creature(name="Doomed Bear", base_power=2, base_toughness=2)
        target.owner = game.players[1]
        spell = GrappleWithDeath(owner=game.players[0])
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1})
        set_board_state(game, 1, battlefield=[target])

        life_before = game.players[0].life
        cast_spell(game, 0, "Grapple with Death", targets=[target])

        assert game.players[0].life == life_before + 1

    def test_gains_life_even_if_target_indestructible(self) -> None:
        """Life gain is not contingent on successful destruction."""
        game = create_game()
        target = Creature(name="Indestructible Thing", base_power=3, base_toughness=3)
        target.owner = game.players[1]
        target.indestructible = True
        spell = GrappleWithDeath(owner=game.players[0])
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1})
        set_board_state(game, 1, battlefield=[target])

        life_before = game.players[0].life
        cast_spell(game, 0, "Grapple with Death", targets=[target])

        # Should still gain 1 life since it's not dependent on destruction
        assert game.players[0].life == life_before + 1
