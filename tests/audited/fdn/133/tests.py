"""Audited tests for Soulstone Sanctuary (FDN collector number 133)."""
from __future__ import annotations
import pytest
from card_impl import SoulstoneSanctuary
from engine.card import Land
from engine.types import ManaType
from tests.test_utils import create_game, set_board_state


@pytest.mark.basic
class TestSoulstoneSanctuaryBasic:
    def test_is_land(self) -> None:
        card = SoulstoneSanctuary(name="Soulstone Sanctuary", owner=None)
        assert isinstance(card, Land)

    def test_does_not_enter_tapped(self) -> None:
        card = SoulstoneSanctuary(name="Soulstone Sanctuary", owner=None)
        assert not getattr(card, "enters_tapped", False)


@pytest.mark.ability
class TestSoulstoneSanctuaryMana:
    def test_has_mana_ability(self) -> None:
        card = SoulstoneSanctuary(name="Soulstone Sanctuary", owner=None)
        assert len(card.get_mana_abilities()) == 1

    def test_taps_for_colorless(self) -> None:
        game = create_game()
        card = SoulstoneSanctuary(name="Soulstone Sanctuary", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        abilities[0].mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.COLORLESS) >= 1


@pytest.mark.ability
class TestSoulstoneSanctuaryActivated:
    def test_has_activated_ability(self) -> None:
        card = SoulstoneSanctuary(name="Soulstone Sanctuary", owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) == 1

    def test_ability_description_mentions_counter(self) -> None:
        card = SoulstoneSanctuary(name="Soulstone Sanctuary", owner=None)
        abilities = card.get_activated_abilities()
        assert "+1/+1 counter" in abilities[0].description

    def test_ability_description_mentions_vigilance(self) -> None:
        card = SoulstoneSanctuary(name="Soulstone Sanctuary", owner=None)
        abilities = card.get_activated_abilities()
        assert "vigilance" in abilities[0].description

    def test_ability_places_counter_on_target(self) -> None:
        """Activated ability puts a +1/+1 counter on target creature (effect only)."""
        from engine.card import Creature
        game = create_game()
        p = game.players[0]
        card = SoulstoneSanctuary(name="Soulstone Sanctuary", owner=p)
        card.controller = p
        creature = Creature(name="Bear", owner=p, base_power=2, base_toughness=2)
        creature.controller = p
        set_board_state(game, 0, battlefield=[card, creature])
        card._current_target = creature
        abilities = card.get_activated_abilities()
        # Directly invoke effect (bypassing cost which has pay_generic limitation)
        abilities[0].effect(game)
        assert creature.plus1_counters == 1

    def test_ability_grants_vigilance_until_eot(self) -> None:
        """Activated ability gives target creature vigilance until end of turn."""
        from engine.card import Creature
        game = create_game()
        p = game.players[0]
        card = SoulstoneSanctuary(name="Soulstone Sanctuary", owner=p)
        card.controller = p
        creature = Creature(name="Bear", owner=p, base_power=2, base_toughness=2)
        creature.controller = p
        set_board_state(game, 0, battlefield=[card, creature])
        card._current_target = creature
        abilities = card.get_activated_abilities()
        abilities[0].effect(game)
        assert creature.vigilance_until_eot is True

    def test_ability_requires_untapped(self) -> None:
        """Cannot activate when already tapped."""
        game = create_game()
        p = game.players[0]
        card = SoulstoneSanctuary(name="Soulstone Sanctuary", owner=p)
        card.controller = p
        card.is_tapped = True
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_activated_abilities()
        result = abilities[0].cost(game, card)
        assert result is False
