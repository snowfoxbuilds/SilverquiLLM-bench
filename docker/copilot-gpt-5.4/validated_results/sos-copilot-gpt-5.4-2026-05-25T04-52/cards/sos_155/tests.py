"""Tests for SOS 155 — Noxious Newt."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_155.card_impl import NoxiousNewt
from benchmarks.sos.workspace.engine.card import Creature, ManaAbility
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestNoxiousNewtProperties:
    """Static card data should match the SOS 155 spec."""

    def test_is_salamander_creature_with_deathtouch(self) -> None:
        card = NoxiousNewt(owner=None)

        assert isinstance(card, Creature)
        assert "Salamander" in card.subtypes
        assert Keyword.DEATHTOUCH in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = NoxiousNewt(owner=None)

        assert card.name == "Noxious Newt"
        assert card.mana_cost == ManaCost.parse("{1}{G}")
        assert card.base_power == 1
        assert card.base_toughness == 2


class TestNoxiousNewtManaAbility:
    """Noxious Newt should tap for green mana."""

    def test_has_a_single_mana_ability(self) -> None:
        abilities = NoxiousNewt(owner=None).get_mana_abilities()

        assert len(abilities) == 1
        assert isinstance(abilities[0], ManaAbility)

    def test_mana_ability_cost_taps_this_creature_and_cannot_be_paid_while_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = NoxiousNewt(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_mana_abilities()[0]

        assert ability.cost(game, card) is True
        assert card.is_tapped is True
        assert ability.cost(game, card) is False

    def test_mana_ability_adds_one_green_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = NoxiousNewt(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_mana_abilities()[0]

        assert ability.cost(game, card) is True

        ability.mana_produced(game)

        assert p1.mana_pool.get(ManaType.GREEN) == 1
