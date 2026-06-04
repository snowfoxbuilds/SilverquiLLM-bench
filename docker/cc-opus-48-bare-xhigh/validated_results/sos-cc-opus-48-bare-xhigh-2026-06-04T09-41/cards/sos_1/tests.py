"""Tests for The Dawning Archaic (SOS #1)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Sorcery
from engine.casting import get_cost_reduction
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, Keyword, ManaCost, Supertype, TargetRequirement, Zone
from test_utils import create_game, declare_attackers, set_board_state


def _is_creature(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


class _GraveBolt(Sorcery):
    def __init__(self) -> None:
        super().__init__(name="Grave Bolt", mana_cost=ManaCost.parse("{2}{R}"))

    def get_targets(self, game: Any) -> list[TargetRequirement]:
        return [TargetRequirement(_is_creature, "target creature", Zone.BATTLEFIELD)]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        targets = getattr(self, "chosen_targets", []) or []
        if targets and targets[0] is not None:
            deal_damage(game, self, targets[0], 3)


def _resolve_all(game: Any) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _spell(name: str) -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse("{1}{U}"))


def test_basic_characteristics():
    card = TheDawningArchaic()
    assert card.base_power == 7 and card.base_toughness == 7
    assert Keyword.REACH in card.keywords
    assert Supertype.LEGENDARY in card.supertypes


def test_cost_reduction_by_graveyard_count():
    game = create_game()
    p1 = game.players[0]
    set_board_state(
        game, 0, graveyard=[_spell("A"), _spell("B"), _spell("C"), _spell("D")]
    )
    card = TheDawningArchaic()
    card.controller = p1
    assert get_cost_reduction(game, card, p1) == 4


def test_cost_reduction_clamped_to_generic():
    game = create_game()
    p1 = game.players[0]
    set_board_state(game, 0, graveyard=[_spell(str(i)) for i in range(12)])
    card = TheDawningArchaic()
    card.controller = p1
    assert get_cost_reduction(game, card, p1) == 10


def test_attack_trigger_free_casts_and_exiles():
    # p1 attacks with Archaic, casts a sorcery from graveyard for free.
    game = create_game(scripts=([True, None, None], []))
    p1, p2 = game.players

    archaic = TheDawningArchaic()
    set_board_state(game, 0, battlefield=[archaic])
    archaic.summoning_sick = False
    archaic.register_triggers(game)

    bolt = _GraveBolt()
    set_board_state(game, 0, graveyard=[bolt])

    victim = Creature(
        name="Victim", mana_cost=ManaCost.parse("{1}"), base_power=0, base_toughness=8
    )
    set_board_state(game, 1, battlefield=[victim])

    # Script: yes (cast), choose the bolt, then bolt's target (victim).
    from collections import deque

    p1._script = deque([True, bolt, victim])

    declare_attackers(game, ["The Dawning Archaic"])
    _resolve_all(game)

    assert victim.damage_marked == 3
    # The free-cast spell is exiled, not in the graveyard.
    assert game.players[0].zones[Zone.EXILE].contains(bolt)
    assert not game.get_graveyard(p1).contains(bolt)


def test_attack_trigger_may_decline():
    game = create_game()
    p1, p2 = game.players

    archaic = TheDawningArchaic()
    set_board_state(game, 0, battlefield=[archaic])
    archaic.summoning_sick = False
    archaic.register_triggers(game)

    bolt = _GraveBolt()
    set_board_state(game, 0, graveyard=[bolt])

    from collections import deque

    p1._script = deque([False])

    declare_attackers(game, ["The Dawning Archaic"])
    _resolve_all(game)

    # Declined → spell stays in graveyard.
    assert game.get_graveyard(p1).contains(bolt)
