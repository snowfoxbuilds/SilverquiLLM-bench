"""Tests for SOS 257 — Great Hall of the Biblioplex (mana land + animate)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import (
    AbilityError,
    ActivatedAbilityInstance,
    activate_ability,
)
from engine.card import Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from engine.zones import move_to_zone
from test_utils import _resolve_top_of_stack, cast_spell, create_game, set_board_state


def _sorcery(name: str) -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse("{1}"))


def _mana_instance(hall, player, index: int) -> ActivatedAbilityInstance:
    ma = hall.get_mana_abilities()[index]
    return ActivatedAbilityInstance(
        source=hall, controller=player, cost=ma.cost,
        effect=ma.mana_produced, is_mana_ability=True,
    )


def _animate_instance(hall, player) -> ActivatedAbilityInstance:
    ab = hall.get_activated_abilities()[0]
    return ActivatedAbilityInstance(
        source=hall, controller=player, cost=ab.cost,
        effect=ab.effect, is_mana_ability=False,
    )


class TestGreatHallProperties:
    def test_name(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None).name == "Great Hall of the Biblioplex"

    def test_is_land_not_creature(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE not in hall.card_types

    def test_no_power_toughness_before_animation(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        # Not a creature yet — must not look like one to combat / SBAs.
        assert not hasattr(hall, "power")
        assert not hasattr(hall, "toughness")
        assert not hasattr(hall, "base_power")


class TestGreatHallManaAbilities:
    def test_tap_for_colorless(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[hall])
        activate_ability(game, p1, _mana_instance(hall, p1, 0))
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped is True

    def test_tap_pay_life_for_any_color(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        game = create_game(scripts=([ManaType.RED], []))
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[hall], life=20)
        activate_ability(game, p1, _mana_instance(hall, p1, 1))
        assert p1.mana_pool.get(ManaType.RED) == 1
        assert p1.life == 19
        assert hall.is_tapped is True

    def test_tapped_land_cannot_produce_mana(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[hall])
        hall.is_tapped = True
        try:
            activate_ability(game, p1, _mana_instance(hall, p1, 0))
        except AbilityError:
            pass
        else:
            raise AssertionError("expected AbilityError — tapped land has no mana ability")
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0


class TestGreatHallAnimate:
    def test_becomes_24_wizard_creature_still_land(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        activate_ability(game, p1, _animate_instance(hall, p1))
        _resolve_top_of_stack(game)
        assert hall._animated is True
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types  # still a land
        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4

    def test_animate_is_idempotent_while_creature(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 10})
        activate_ability(game, p1, _animate_instance(hall, p1))
        _resolve_top_of_stack(game)
        # Re-activate while already a creature — guarded no-op.
        activate_ability(game, p1, _animate_instance(hall, p1))
        _resolve_top_of_stack(game)
        assert hall.power == 2
        assert hall.toughness == 4


class TestGreatHallSpellCastBuff:
    def _battlefield_with_triggers(self, game, hall) -> None:
        set_board_state(game, 0, hand=[hall])
        move_to_zone(game, hall, Zone.HAND, Zone.BATTLEFIELD)

    def test_plus_one_zero_on_instant_or_sorcery_cast_while_animated(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        spell = _sorcery("Pulse")
        game = create_game()
        p1 = game.players[0]
        self._battlefield_with_triggers(game, hall)
        # Animate.
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        activate_ability(game, p1, _animate_instance(hall, p1))
        _resolve_top_of_stack(game)
        # Cast an instant/sorcery — the trigger should buff +1/+0.
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Pulse")
        _resolve_top_of_stack(game)
        game.effect_manager.apply_all(game)
        assert hall.power == 3
        assert hall.toughness == 4

    def test_no_buff_when_not_animated(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        spell = _sorcery("Pulse")
        game = create_game()
        p1 = game.players[0]
        self._battlefield_with_triggers(game, hall)
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Pulse")
        _resolve_top_of_stack(game)
        game.effect_manager.apply_all(game)
        assert not hall._animated
        assert not hasattr(hall, "power")
        # No continuous effect was contributed by the un-animated land.
        assert all(e.source is not hall for e in game.effect_manager.get_all())
