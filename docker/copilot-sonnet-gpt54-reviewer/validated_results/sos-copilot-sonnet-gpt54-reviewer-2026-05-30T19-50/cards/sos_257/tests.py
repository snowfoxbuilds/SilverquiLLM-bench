"""Tests for Great Hall of the Biblioplex (sos_257).

Covers:
- Card attributes (Land type, no mana cost)
- Ability 1: {T}: Add {C}
- Ability 2: {T}, Pay 1 life: Add one mana of any color
- Ability 2: life is actually paid (life total decreases)
- Ability 3: animation — becomes 2/4 Wizard creature (still a Land)
- Ability 3: does not animate if already a creature
- While animated: +1/+0 trigger on instant/sorcery cast
- Multiple instants/sorceries stack multiple +1/+0
- While not animated: no +1/+0 trigger
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Instant, Land, Sorcery
from engine.types import CardType, ManaType, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hall(game: Any, player_index: int = 0) -> GreatHallOfTheBiblioplex:
    """Place a Great Hall of the Biblioplex on *player_index*'s battlefield."""
    player = game.players[player_index]
    hall = GreatHallOfTheBiblioplex(owner=player, controller=player)
    set_board_state(game, player_index, battlefield=[hall])
    return hall


def _tap_for_colorless(game: Any, hall: GreatHallOfTheBiblioplex) -> bool:
    """Activate ability 1: {T}: Add {C}. Returns True if cost was paid."""
    abilities = hall.get_mana_abilities()
    cost_fn = abilities[0].cost
    effect_fn = abilities[0].mana_produced
    paid = cost_fn(game, hall)
    if paid:
        effect_fn(game)
    return paid


def _tap_for_colored(game: Any, hall: GreatHallOfTheBiblioplex, mana_type: ManaType) -> bool:
    """Activate ability 2: {T}, Pay 1 life: Add colored mana. Returns True if cost was paid."""
    hall._chosen_mana_type = mana_type
    abilities = hall.get_mana_abilities()
    cost_fn = abilities[1].cost
    effect_fn = abilities[1].mana_produced
    paid = cost_fn(game, hall)
    if paid:
        effect_fn(game)
    return paid


def _animate(game: Any, hall: GreatHallOfTheBiblioplex) -> bool:
    """Activate ability 3: {5} to animate. Returns True if cost was paid."""
    abilities = hall.get_activated_abilities()
    cost_fn = abilities[0].cost
    effect_fn = abilities[0].effect
    paid = cost_fn(game, hall)
    if paid:
        effect_fn(game)
    return paid


def _fire_spell_cast_event(game: Any, card: Any, player: Any) -> None:
    """Fire a SpellCastTriggeredEvent and resolve any triggers."""
    from engine.events import SpellCastTriggeredEvent
    from engine.stack import StackObject

    spell_obj = StackObject(source=card, controller=player, on_resolve=lambda g: None)
    event = SpellCastTriggeredEvent(spell=spell_obj, player=player, card=card, controller=player)
    game.trigger_manager.fire_event(game, event)
    # Resolve any trigger that landed on the stack.
    while not game.stack.is_empty():
        top = game.stack.peek()
        game.stack.pop()
        if top.on_resolve:
            top.on_resolve(game)


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestGreatHallProperties:
    def test_name(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        assert hall.name == "Great Hall of the Biblioplex"

    def test_is_land(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(hall, Land)
        assert CardType.LAND in hall.card_types

    def test_no_mana_cost(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        assert hall.mana_cost.cmc == 0

    def test_not_a_creature_initially(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.CREATURE not in hall.card_types

    def test_not_tapped_initially(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        assert hall.is_tapped is False

    def test_has_two_mana_abilities(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        assert len(hall.get_mana_abilities()) == 2

    def test_has_one_activated_ability(self) -> None:
        hall = GreatHallOfTheBiblioplex(owner=None)
        assert len(hall.get_activated_abilities()) == 1


# ---------------------------------------------------------------------------
# Ability 1: {T}: Add {C}
# ---------------------------------------------------------------------------

class TestAbility1AddColorless:
    def test_adds_colorless_mana(self) -> None:
        game = create_game()
        hall = _make_hall(game)
        before = game.players[0].mana_pool.get(ManaType.COLORLESS)
        paid = _tap_for_colorless(game, hall)
        assert paid is True
        assert game.players[0].mana_pool.get(ManaType.COLORLESS) == before + 1

    def test_taps_the_land(self) -> None:
        game = create_game()
        hall = _make_hall(game)
        _tap_for_colorless(game, hall)
        assert hall.is_tapped is True

    def test_cannot_tap_twice(self) -> None:
        game = create_game()
        hall = _make_hall(game)
        _tap_for_colorless(game, hall)
        pool_after_first = game.players[0].mana_pool.get(ManaType.COLORLESS)
        paid = _tap_for_colorless(game, hall)
        assert paid is False
        assert game.players[0].mana_pool.get(ManaType.COLORLESS) == pool_after_first


# ---------------------------------------------------------------------------
# Ability 2: {T}, Pay 1 life: Add one mana of any color
# ---------------------------------------------------------------------------

class TestAbility2AddColoredMana:
    def test_adds_chosen_color(self) -> None:
        game = create_game()
        hall = _make_hall(game)
        for color in (ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN):
            g2 = create_game()
            h2 = _make_hall(g2)
            before = g2.players[0].mana_pool.get(color)
            paid = _tap_for_colored(g2, h2, color)
            assert paid is True
            assert g2.players[0].mana_pool.get(color) == before + 1

    def test_life_is_paid(self) -> None:
        game = create_game(player1_life=20)
        hall = _make_hall(game)
        _tap_for_colored(game, hall, ManaType.BLUE)
        assert game.players[0].life == 19

    def test_taps_land(self) -> None:
        game = create_game()
        hall = _make_hall(game)
        _tap_for_colored(game, hall, ManaType.GREEN)
        assert hall.is_tapped is True

    def test_cannot_activate_if_insufficient_life(self) -> None:
        game = create_game(player1_life=1)
        hall = _make_hall(game, 0)
        # Pay 1 life first to get to 0.
        game.players[0].life = 0
        paid = _tap_for_colored(game, hall, ManaType.RED)
        assert paid is False

    def test_cannot_tap_if_already_tapped(self) -> None:
        game = create_game()
        hall = _make_hall(game)
        hall.is_tapped = True
        paid = _tap_for_colored(game, hall, ManaType.WHITE)
        assert paid is False
        # Life should not have been spent.
        assert game.players[0].life == 20


# ---------------------------------------------------------------------------
# Ability 3: {5} — land animation
# ---------------------------------------------------------------------------

class TestAbility3Animation:
    def test_animation_requires_five_mana(self) -> None:
        game = create_game()
        hall = _make_hall(game)
        # No mana available — cost should fail.
        paid = _animate(game, hall)
        assert paid is False
        assert CardType.CREATURE not in hall.card_types

    def test_becomes_creature_with_five_mana(self) -> None:
        game = create_game()
        hall = _make_hall(game)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        paid = _animate(game, hall)
        assert paid is True
        assert CardType.CREATURE in hall.card_types

    def test_still_a_land_after_animation(self) -> None:
        game = create_game()
        hall = _make_hall(game)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        _animate(game, hall)
        assert CardType.LAND in hall.card_types

    def test_power_and_toughness_are_2_4(self) -> None:
        game = create_game()
        hall = _make_hall(game)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        _animate(game, hall)
        assert hall.power == 2
        assert hall.toughness == 4

    def test_wizard_subtype_added(self) -> None:
        game = create_game()
        hall = _make_hall(game)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        _animate(game, hall)
        assert "Wizard" in hall.subtypes

    def test_does_not_animate_if_already_creature(self) -> None:
        game = create_game()
        hall = _make_hall(game)
        # Manually mark as animated already.
        hall._is_animated = True
        hall.card_types.add(CardType.CREATURE)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        # Cost check: if it's already a creature, cost returns False.
        abilities = hall.get_activated_abilities()
        paid = abilities[0].cost(game, hall)
        assert paid is False

    def test_five_mana_is_consumed(self) -> None:
        game = create_game()
        hall = _make_hall(game)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        _animate(game, hall)
        assert game.players[0].mana_pool.total() == 0


# ---------------------------------------------------------------------------
# Triggered ability: +1/+0 while animated on instant/sorcery cast
# ---------------------------------------------------------------------------

class TestAnimatedTrigger:
    def _setup_animated(self) -> tuple[Any, GreatHallOfTheBiblioplex]:
        game = create_game()
        hall = _make_hall(game)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        _animate(game, hall)
        return game, hall

    def test_instant_triggers_plus_one_power(self) -> None:
        game, hall = self._setup_animated()
        player = game.players[0]
        instant = Instant(name="Lightning Bolt", owner=player, controller=player)
        instant.card_types.add(CardType.INSTANT)
        base_power = hall.power
        _fire_spell_cast_event(game, instant, player)
        # Apply effects to reflect the modification.
        game.effect_manager.apply_all(game)
        assert hall.power == base_power + 1

    def test_sorcery_triggers_plus_one_power(self) -> None:
        game, hall = self._setup_animated()
        player = game.players[0]
        sorcery = Sorcery(name="Divination", owner=player, controller=player)
        sorcery.card_types.add(CardType.SORCERY)
        base_power = hall.power
        _fire_spell_cast_event(game, sorcery, player)
        game.effect_manager.apply_all(game)
        assert hall.power == base_power + 1

    def test_toughness_unchanged_after_trigger(self) -> None:
        game, hall = self._setup_animated()
        player = game.players[0]
        instant = Instant(name="Shock", owner=player, controller=player)
        instant.card_types.add(CardType.INSTANT)
        _fire_spell_cast_event(game, instant, player)
        game.effect_manager.apply_all(game)
        assert hall.toughness == 4

    def test_multiple_spells_stack_boosts(self) -> None:
        game, hall = self._setup_animated()
        player = game.players[0]
        base_power = hall.power
        for i in range(3):
            spell = Instant(name=f"Spell{i}", owner=player, controller=player)
            spell.card_types.add(CardType.INSTANT)
            _fire_spell_cast_event(game, spell, player)
        game.effect_manager.apply_all(game)
        assert hall.power == base_power + 3

    def test_opponent_spell_does_not_trigger(self) -> None:
        game, hall = self._setup_animated()
        opponent = game.players[1]
        instant = Instant(name="Counterspell", owner=opponent, controller=opponent)
        instant.card_types.add(CardType.INSTANT)
        base_power = hall.power
        _fire_spell_cast_event(game, instant, opponent)
        game.effect_manager.apply_all(game)
        assert hall.power == base_power

    def test_non_instant_sorcery_does_not_trigger(self) -> None:
        """A creature spell should not trigger the +1/+0 ability."""
        game, hall = self._setup_animated()
        player = game.players[0]
        from engine.card import Creature
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=player, controller=player)
        base_power = hall.power

        from engine.events import SpellCastTriggeredEvent
        from engine.stack import StackObject
        spell_obj = StackObject(source=creature, controller=player, on_resolve=lambda g: None)
        event = SpellCastTriggeredEvent(spell=spell_obj, player=player, card=creature, controller=player)
        game.trigger_manager.fire_event(game, event)
        while not game.stack.is_empty():
            top = game.stack.peek()
            game.stack.pop()
            if top.on_resolve:
                top.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert hall.power == base_power


# ---------------------------------------------------------------------------
# Not animated: no trigger
# ---------------------------------------------------------------------------

class TestNotAnimatedNoTrigger:
    def test_no_trigger_when_not_animated(self) -> None:
        game = create_game()
        hall = _make_hall(game)
        player = game.players[0]
        # Do NOT animate the hall.
        assert not hall._is_animated
        # Hall shouldn't have CREATURE in card_types.
        assert CardType.CREATURE not in hall.card_types
        # Fire a spell — no trigger should bump power.
        instant = Instant(name="Lightning Bolt", owner=player, controller=player)
        instant.card_types.add(CardType.INSTANT)
        _fire_spell_cast_event(game, instant, player)
        game.effect_manager.apply_all(game)
        # Power stays at 0 (not a creature; modified_power stays 0).
        assert hall.modified_power == 0
