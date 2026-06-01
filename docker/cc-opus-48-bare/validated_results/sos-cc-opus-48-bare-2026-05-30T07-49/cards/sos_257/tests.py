"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Instant
from engine.events import SpellCastTriggeredEvent
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, set_board_state


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _fire_cast(game, player, spell) -> None:
    spell.controller = player
    game.trigger_manager.fire_event(
        game,
        SpellCastTriggeredEvent(spell=spell, player=player, card=spell, controller=player),
    )


class TestGreatHallProperties:
    def test_is_a_land_not_a_creature(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.name == "Great Hall of the Biblioplex"
        assert CardType.LAND in card.card_types
        assert CardType.CREATURE not in card.card_types
        # Un-animated: power/toughness are not exposed at all.
        assert not hasattr(card, "toughness")
        assert not hasattr(card, "power")

    def test_can_cast_is_false(self) -> None:
        game = create_game()
        assert GreatHallOfTheBiblioplex(owner=game.players[0]).can_cast(game) is False


class TestGreatHallManaAbilities:
    def test_colorless_mana_ability(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={})

        colorless = land.get_mana_abilities()[0]
        assert colorless.cost(game, land) is True
        colorless.mana_produced(game)
        assert p1.mana_pool.total() == 1
        # Already tapped — cannot pay the tap cost again.
        assert colorless.cost(game, land) is False

    def test_any_color_costs_one_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], life=20, mana={})

        any_color = land.get_mana_abilities()[1]
        p1._script.append(ManaType.BLUE)
        assert any_color.cost(game, land) is True
        any_color.mana_produced(game)
        assert p1.life == 19
        assert p1.mana_pool.total() == 1


class TestGreatHallAnimation:
    def _animate(self, game, land, p1) -> None:
        ability = land.get_activated_abilities()[0]
        assert ability.cost(game, land) is True
        ability.effect(game)

    def test_five_mana_animates_to_2_4_wizard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 5})

        self._animate(game, land, p1)

        assert p1.mana_pool.total() == 0
        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types  # still a land
        assert "Wizard" in land.subtypes
        assert land.power == 2
        assert land.toughness == 4

    def test_insufficient_mana_cannot_activate(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 4})

        ability = land.get_activated_abilities()[0]
        assert ability.cost(game, land) is False
        assert CardType.CREATURE not in land.card_types

    def test_animate_is_noop_if_already_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 5})
        self._animate(game, land, p1)

        # Pump once, then "re-animate" — must not reset the pump or re-add type.
        land.modified_power = 5
        land._animate(game)
        assert land.power == 5


class TestGreatHallPump:
    def _animate(self, game, land) -> None:
        ability = land.get_activated_abilities()[0]
        ability.cost(game, land)
        ability.effect(game)

    def test_pump_per_instant_or_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 5})
        self._animate(game, land)
        land.register_triggers(game)

        _fire_cast(game, p1, Instant(name="Zap", mana_cost=ManaCost.parse("{R}")))
        _resolve_all(game)
        assert land.power == 3
        assert land.toughness == 4  # +1/+0 only

        _fire_cast(game, p1, Instant(name="Zap2", mana_cost=ManaCost.parse("{R}")))
        _resolve_all(game)
        assert land.power == 4

    def test_no_pump_when_not_animated(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land])
        land.register_triggers(game)

        _fire_cast(game, p1, Instant(name="Zap", mana_cost=ManaCost.parse("{R}")))
        # No trigger should have been placed on the stack.
        assert game.stack.is_empty()
        assert CardType.CREATURE not in land.card_types

    def test_pump_survives_layer_recalculation_then_expires(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 5})
        self._animate(game, land)
        land.register_triggers(game)

        _fire_cast(game, p1, Instant(name="Zap", mana_cost=ManaCost.parse("{R}")))
        _resolve_all(game)
        assert land.power == 3

        # A mid-turn layer recalculation must reproduce the pump.
        game.effect_manager.apply_all(game)
        assert land.power == 3
        assert CardType.CREATURE in land.card_types

        # End-of-turn sweep removes the until-EOT pump.
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)
        assert land.power == 2


class TestGreatHallStateBasedActions:
    def test_unanimated_land_survives_sba(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land])

        resolve_state_based_actions(game)
        assert land in game.get_battlefield(p1).get_all()
