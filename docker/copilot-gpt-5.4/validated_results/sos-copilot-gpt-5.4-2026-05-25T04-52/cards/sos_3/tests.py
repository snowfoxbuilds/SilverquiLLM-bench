"""Tests for SOS 3 — Sundering Archaic."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_3.card_impl import SunderingArchaic
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Land
from benchmarks.sos.workspace.engine.types import CardType, Color, ManaCost, Zone
from benchmarks.sos.workspace.engine.mana import ManaPool
from benchmarks.sos.workspace.engine.types import ManaType
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestSunderingArchaicProperties:
    """Static card data should match the SOS 3 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(SunderingArchaic(owner=None), Creature)

    def test_name_cost_and_power_toughness(self) -> None:
        card = SunderingArchaic(owner=None)
        assert card.name == "Sundering Archaic"
        assert card.mana_cost == ManaCost.parse("{6}")
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestSunderingArchaicConverge:
    """The ETB-like converge effect should exile only valid permanents."""

    def test_exiles_targeted_nonland_permanent_within_color_limit(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Opponent Bear",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}"),
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 1, battlefield=[target])

        card = SunderingArchaic(owner=p1, controller=p1)
        card.colors_spent = [Color.W, Color.U]
        card.chosen_targets = [target]
        card.on_resolve(game)

        assert not game.get_battlefield(p2).contains(target)
        assert game.get_exile(p2).contains(target)

    def test_does_not_exile_when_target_mana_value_exceeds_colors_spent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Big Opponent Bear",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{3}"),
            base_power=3,
            base_toughness=3,
        )
        set_board_state(game, 1, battlefield=[target])

        card = SunderingArchaic(owner=p1, controller=p1)
        card.colors_spent = [Color.W, Color.U]
        card.chosen_targets = [target]
        card.on_resolve(game)

        assert game.get_battlefield(p2).contains(target)
        assert not game.get_exile(p2).contains(target)

    def test_does_not_exile_lands(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Land(name="Forest", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])

        card = SunderingArchaic(owner=p1, controller=p1)
        card.colors_spent = [Color.W, Color.U, Color.B]
        card.chosen_targets = [target]
        card.on_resolve(game)

        assert game.get_battlefield(p2).contains(target)
        assert not game.get_exile(p2).contains(target)


class TestSunderingArchaicActivatedAbility:
    """The graveyard-recycling activation should move a card to library bottom."""

    def test_has_single_activated_ability(self) -> None:
        abilities = SunderingArchaic(owner=None).get_activated_abilities()
        assert len(abilities) == 1

    def test_activated_ability_cost_requires_two_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SunderingArchaic(owner=p1, controller=p1)
        ability = card.get_activated_abilities()[0]

        p1.mana_pool = ManaPool()
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        assert ability.cost(game, card) is False

        p1.mana_pool = ManaPool()
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        assert ability.cost(game, card) is True
        assert p1.mana_pool.total() == 0

    def test_activated_ability_puts_target_card_on_bottom_of_owners_library(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = CardImpl(name="Spent Spell", owner=p2, controller=p2)
        set_board_state(game, 1, graveyard=[target])

        card = SunderingArchaic(owner=p1, controller=p1)
        ability = card.get_activated_abilities()[0]
        card._current_target = target
        ability.effect(game)

        assert not game.get_graveyard(p2).contains(target)
        assert game.get_library(p2).bottom(1) == [target]
