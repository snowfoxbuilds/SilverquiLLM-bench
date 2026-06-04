"""Tests for Great Hall of the Biblioplex (SOS #257)."""

from __future__ import annotations

from collections import deque
from typing import Any

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant
from engine.events import SpellCastTriggeredEvent
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


def _resolve_all(game: Any) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _bolt() -> Instant:
    return Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))


def _activate_five(game: Any, card: GreatHallOfTheBiblioplex, player: Any) -> None:
    ability = card.get_activated_abilities(game)[0]
    inst = ActivatedAbilityInstance(
        source=card,
        controller=player,
        cost=ability.cost,
        effect=ability.effect,
        is_mana_ability=False,
        description=ability.description,
    )
    activate_ability(game, player, inst)
    _resolve_all(game)


def test_basic_characteristics():
    game = create_game()
    card = GreatHallOfTheBiblioplex()
    assert CardType.LAND in card.card_types
    assert CardType.CREATURE not in card.card_types
    # Un-animated: power/toughness are not exposed (keeps it safe from SBAs).
    assert not hasattr(card, "toughness")
    assert not hasattr(card, "power")

    mana_abilities = card.get_mana_abilities()
    assert len(mana_abilities) == 2
    assert len(card.get_activated_abilities(game)) == 1


def test_taps_for_colorless():
    game = create_game()
    p1, _ = game.players
    card = GreatHallOfTheBiblioplex()
    set_board_state(game, 0, battlefield=[card])

    ability = card.get_mana_abilities()[0]
    assert ability.cost(game, card) is True
    ability.mana_produced(game)

    assert card.is_tapped
    assert p1.mana_pool.can_pay(ManaCost.parse("{C}"))
    assert p1.mana_pool._pool.get(ManaType.COLORLESS, 0) == 1


def test_any_color_ability_costs_one_life():
    game = create_game()
    p1, _ = game.players
    p1.life = 20
    card = GreatHallOfTheBiblioplex()
    set_board_state(game, 0, battlefield=[card])

    # Choose red when the ability resolves its color choice.
    p1._script = deque([ManaType.RED])

    ability = card.get_mana_abilities()[1]
    assert ability.cost(game, card) is True
    ability.mana_produced(game)

    assert card.is_tapped
    assert p1.life == 19
    assert p1.mana_pool._pool.get(ManaType.RED, 0) == 1

    # A second activation can't pay the tap cost (already tapped).
    assert ability.cost(game, card) is False
    assert p1.life == 19


def test_un_animated_land_survives_state_based_actions():
    game = create_game()
    p1, _ = game.players
    card = GreatHallOfTheBiblioplex()
    set_board_state(game, 0, battlefield=[card])

    resolve_state_based_actions(game)

    # Not a creature → no zero-toughness death.
    assert game.get_battlefield(p1).contains(card)


def test_five_animates_into_wizard_creature():
    game = create_game()
    p1, _ = game.players
    card = GreatHallOfTheBiblioplex()
    set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 5})

    _activate_five(game, card, p1)

    assert CardType.CREATURE in card.card_types
    assert CardType.LAND in card.card_types  # still a land
    assert "Wizard" in card.subtypes
    assert card.power == 2
    assert card.toughness == 4
    assert p1.mana_pool.total() == 0

    # Animated creature with positive toughness survives SBAs.
    resolve_state_based_actions(game)
    assert game.get_battlefield(p1).contains(card)


def test_cast_trigger_pumps_power_until_end_of_turn():
    game = create_game()
    p1, _ = game.players
    card = GreatHallOfTheBiblioplex()
    set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 5})

    _activate_five(game, card, p1)
    card.register_triggers(game)

    bolt = _bolt()
    game.trigger_manager.fire_event(
        game,
        SpellCastTriggeredEvent(spell=bolt, player=p1, card=bolt, controller=p1),
    )
    _resolve_all(game)
    assert card.power == 3
    assert card.toughness == 4

    # A second instant/sorcery stacks another +1/+0.
    game.trigger_manager.fire_event(
        game,
        SpellCastTriggeredEvent(spell=_bolt(), player=p1, card=bolt, controller=p1),
    )
    _resolve_all(game)
    assert card.power == 4

    # End-of-turn cleanup wipes the until-end-of-turn buffs.
    game.effect_manager.remove_expired(game)
    game.effect_manager.apply_all(game)
    assert card.power == 2
    assert CardType.CREATURE in card.card_types  # animation is permanent


def test_cast_trigger_ignores_noncreature_caster_and_creatures():
    game = create_game()
    p1, p2 = game.players
    card = GreatHallOfTheBiblioplex()
    set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 5})

    _activate_five(game, card, p1)
    card.register_triggers(game)

    # Opponent casting an instant does not pump it.
    game.trigger_manager.fire_event(
        game,
        SpellCastTriggeredEvent(spell=_bolt(), player=p2, card=None, controller=p2),
    )
    _resolve_all(game)
    assert card.power == 2

    # A creature spell cast by the controller doesn't pump it either.
    bear = Creature(name="Bear", mana_cost=ManaCost.parse("{2}"), base_power=2, base_toughness=2)
    game.trigger_manager.fire_event(
        game,
        SpellCastTriggeredEvent(spell=bear, player=p1, card=bear, controller=p1),
    )
    _resolve_all(game)
    assert card.power == 2
