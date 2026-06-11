"""Tests for SOS 31 — Shattered Acolyte."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_31.card_impl import ShatteredAcolyte
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Artifact, Creature, Enchantment
from benchmarks.sos.workspace.engine.mana import ManaPool
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestShatteredAcolyteProperties:
    """Static card data should match the SOS 31 spec."""

    def test_is_dwarf_warlock_creature_with_lifelink(self) -> None:
        card = ShatteredAcolyte(owner=None)
        assert isinstance(card, Creature)
        assert "Dwarf" in card.subtypes
        assert "Warlock" in card.subtypes
        assert Keyword.LIFELINK in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = ShatteredAcolyte(owner=None)
        assert card.name == "Shattered Acolyte"
        assert card.mana_cost == ManaCost.parse("{1}{W}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestShatteredAcolyteActivatedAbility:
    """Shattered Acolyte should sacrifice itself to destroy artifacts or enchantments."""

    def test_has_a_single_activated_ability(self) -> None:
        abilities = ShatteredAcolyte(owner=None).get_activated_abilities()
        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_cost_requires_one_mana_and_sacrifices_this_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ShatteredAcolyte(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_activated_abilities()[0]

        p1.mana_pool = ManaPool()
        assert ability.cost(game, card) is False
        assert game.get_battlefield(p1).contains(card)
        assert not game.get_graveyard(p1).contains(card)

        p1.mana_pool = ManaPool()
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        assert ability.cost(game, card) is True
        assert p1.mana_pool.total() == 0
        assert not game.get_battlefield(p1).contains(card)
        assert game.get_graveyard(p1).contains(card)

    def test_effect_destroys_target_artifact(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ShatteredAcolyte(owner=p1, controller=p1)
        target = Artifact(name="Relic", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])
        ability = card.get_activated_abilities()[0]
        card._current_target = target

        ability.effect(game)

        assert not game.get_battlefield(p2).contains(target)
        assert game.get_graveyard(p2).contains(target)

    def test_effect_destroys_target_enchantment(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ShatteredAcolyte(owner=p1, controller=p1)
        target = Enchantment(name="Curious Lesson", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])
        ability = card.get_activated_abilities()[0]
        card._current_target = target

        ability.effect(game)

        assert not game.get_battlefield(p2).contains(target)
        assert game.get_graveyard(p2).contains(target)
