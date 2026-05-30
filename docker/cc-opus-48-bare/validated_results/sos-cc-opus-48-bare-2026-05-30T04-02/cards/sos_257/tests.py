"""Tests for SOS 257 — Great Hall of the Biblioplex (mana land + animation)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Instant
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class _Zap(Instant):
    """Minimal instant used to fire spell-cast triggers."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)


def _hall(player: Any) -> GreatHallOfTheBiblioplex:
    hall = GreatHallOfTheBiblioplex(owner=player, controller=player)
    return hall


def _fire_cast(game: Any, player: Any, spell: Any) -> None:
    """Fire a SpellCastTriggeredEvent and resolve any resulting triggers."""
    game.trigger_manager.fire_event(
        game,
        SpellCastTriggeredEvent(spell=spell, player=player, card=spell, controller=player),
    )
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestGreatHallProperties:
    def test_name(self) -> None:
        assert GreatHallOfTheBiblioplex().name == "Great Hall of the Biblioplex"

    def test_is_land_with_no_mana_cost(self) -> None:
        hall = GreatHallOfTheBiblioplex()
        assert CardType.LAND in hall.card_types
        assert hall.mana_cost.cmc == 0

    def test_not_a_creature_initially(self) -> None:
        hall = GreatHallOfTheBiblioplex()
        assert CardType.CREATURE not in hall.card_types
        # No power/toughness characteristics until animated.
        assert not hasattr(hall, "base_power")
        assert not hasattr(hall, "power")
        assert not hasattr(hall, "toughness")


class TestGreatHallManaAbilities:
    def test_tap_for_colorless(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        hall = _hall(p1)
        set_board_state(game, 0, battlefield=[hall])
        tap_c = hall.get_mana_abilities()[0]
        assert tap_c.cost(game, hall) is True
        tap_c.mana_produced(game)
        assert hall.is_tapped is True
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_tapped_land_cannot_tap_again(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        hall = _hall(p1)
        set_board_state(game, 0, battlefield=[hall])
        tap_c = hall.get_mana_abilities()[0]
        assert tap_c.cost(game, hall) is True
        assert tap_c.cost(game, hall) is False

    def test_pay_life_for_any_color(self) -> None:
        # Script the controller to choose blue.
        game = create_game(scripts=([ManaType.BLUE], []))
        p1, _ = game.players
        hall = _hall(p1)
        set_board_state(game, 0, battlefield=[hall], life=20)
        pay_life = hall.get_mana_abilities()[1]
        assert pay_life.cost(game, hall) is True
        pay_life.mana_produced(game)
        assert hall.is_tapped is True
        assert p1.life == 19
        assert p1.mana_pool.get(ManaType.BLUE) == 1

    def test_pay_life_blocked_at_zero_life(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        hall = _hall(p1)
        set_board_state(game, 0, battlefield=[hall], life=0)
        pay_life = hall.get_mana_abilities()[1]
        assert pay_life.cost(game, hall) is False
        assert hall.is_tapped is False


class TestGreatHallAnimation:
    def _setup(self):
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        hall = _hall(p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        return game, p1, p2, hall

    def test_five_mana_animates_into_creature(self) -> None:
        game, p1, _, hall = self._setup()
        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is True
        ability.effect(game)
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types  # still a land
        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4
        assert p1.mana_pool.total() == 0

    def test_animation_is_idempotent(self) -> None:
        game, p1, _, hall = self._setup()
        ability = hall.get_activated_abilities()[0]
        ability.cost(game, hall)
        ability.effect(game)
        # Second activation: already a creature → no extra trigger registered.
        ability.effect(game)
        triggers = game.trigger_manager.get_triggers_for_source(hall)
        assert len(triggers) == 1

    def test_survives_effect_recalculation(self) -> None:
        game, p1, _, hall = self._setup()
        ability = hall.get_activated_abilities()[0]
        ability.cost(game, hall)
        ability.effect(game)
        # A full continuous-effect recalculation must not strip creature-hood.
        game.effect_manager.apply_all(game)
        assert CardType.CREATURE in hall.card_types
        assert hall.power == 2
        assert hall.toughness == 4

    def test_cast_trigger_pumps_power(self) -> None:
        game, p1, _, hall = self._setup()
        ability = hall.get_activated_abilities()[0]
        ability.cost(game, hall)
        ability.effect(game)
        _fire_cast(game, p1, _Zap(owner=p1, controller=p1))
        assert hall.power == 3
        assert hall.toughness == 4
        # A second instant stacks another +1/+0.
        _fire_cast(game, p1, _Zap(owner=p1, controller=p1))
        assert hall.power == 4

    def test_pump_only_for_instant_or_sorcery(self) -> None:
        from engine.card import Creature

        game, p1, _, hall = self._setup()
        ability = hall.get_activated_abilities()[0]
        ability.cost(game, hall)
        ability.effect(game)
        creature_spell = Creature(
            name="Ogre", owner=p1, controller=p1, base_power=3, base_toughness=3
        )
        _fire_cast(game, p1, creature_spell)
        assert hall.power == 2

    def test_no_pump_before_animation(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        hall = _hall(p1)
        set_board_state(game, 0, battlefield=[hall])
        # No animation yet → casting a spell does nothing and no trigger exists.
        _fire_cast(game, p1, _Zap(owner=p1, controller=p1))
        assert not hasattr(hall, "power")

    def test_pump_expires_at_cleanup(self) -> None:
        game, p1, _, hall = self._setup()
        ability = hall.get_activated_abilities()[0]
        ability.cost(game, hall)
        ability.effect(game)
        _fire_cast(game, p1, _Zap(owner=p1, controller=p1))
        assert hall.power == 3
        # End-of-turn sweep removes the "+1/+0 until end of turn" effect.
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)
        assert hall.power == 2
