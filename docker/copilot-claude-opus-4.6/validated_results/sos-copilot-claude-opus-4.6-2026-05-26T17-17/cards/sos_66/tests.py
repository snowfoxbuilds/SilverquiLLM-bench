"""Tests for SOS 66 — Run Behind.

Run Behind is a {3}{U} Instant that puts a target creature on top or bottom
of its owner's library. It costs {1} less if targeting an attacking creature.
"""

from __future__ import annotations

from cards.sos.sos_66.card_impl import RunBehind
from engine.card import Creature, Instant
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class TestRunBehindProperties:
    """Static card data should match the SOS 66 spec."""

    def test_is_instant(self) -> None:
        card = RunBehind(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = RunBehind(owner=None)
        assert card.name == "Run Behind"

    def test_mana_cost(self) -> None:
        card = RunBehind(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{U}")


class TestRunBehindCostReduction:
    """The spell costs {1} less when targeting an attacking creature."""

    def test_normal_cost_without_attacking_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RunBehind(owner=p1, controller=p1)
        # Without an attacking creature target, total cost should be 4 (3+U)
        bear = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        bear.is_attacking = False
        card.chosen_targets = [bear]
        cost = card.get_total_cost(game)
        assert cost.total_mana() == 4

    def test_reduced_cost_with_attacking_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RunBehind(owner=p1, controller=p1)
        bear = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        bear.is_attacking = True
        card.chosen_targets = [bear]
        cost = card.get_total_cost(game)
        # Should cost {2}{U} = 3 total mana
        assert cost.total_mana() == 3


class TestRunBehindTargeting:
    """Run Behind targets a creature."""

    def test_returns_target_requirement(self) -> None:
        game = create_game()
        card = RunBehind(owner=None)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_accepts_creature(self) -> None:
        game = create_game()
        req = RunBehind(owner=None).get_targets(game)[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True


class TestRunBehindResolution:
    """On resolve, the target creature is put on top or bottom of owner's library."""

    def test_creature_removed_from_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bear = Creature(
            name="Grizzly Bears", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(bear)

        spell = RunBehind(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        # Bear should no longer be on the battlefield
        bf_cards = game.get_battlefield(p2).get_all()
        assert bear not in bf_cards

    def test_creature_goes_to_owner_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bear = Creature(
            name="Grizzly Bears", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(bear)

        spell = RunBehind(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        # Bear should be in owner's library (top or bottom)
        library = game.get_library(p2)
        assert bear in library.get_all()
