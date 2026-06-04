"""Tests for SOS 57 — Mana Sculpt (counter + deferred {C} for Wizards)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import cast_spell as engine_cast_spell
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Phase
from test_utils import _resolve_top_of_stack, create_game, set_board_state


class _NoOp(Instant):
    """A trivial instant with a configurable mana cost; resolves to nothing."""

    def __init__(self, cost: str = "{3}", **kwargs: Any) -> None:
        kwargs.setdefault("name", "Decoy")
        kwargs.setdefault("mana_cost", ManaCost.parse(cost))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        pass


def _wizard(name: str = "Wiz") -> Creature:
    w = Creature(name=name, base_power=1, base_toughness=1)
    w.card_types = {CardType.CREATURE}
    w.subtypes = {"Wizard"}
    return w


def _push_victim(game: Any, player_index: int, cost: str = "{3}") -> Any:
    """Cast a decoy spell so it sits on the stack; return its StackObject."""
    player = game.players[player_index]
    victim = _NoOp(cost=cost, owner=player, controller=player)
    generic = ManaCost.parse(cost).cmc
    set_board_state(
        game, player_index, hand=[victim], mana={ManaType.COLORLESS: generic}
    )
    engine_cast_spell(game, player, victim)
    return victim, game.stack.objects()[0]


def _sculpt_mana() -> dict[ManaType, int]:
    return {ManaType.COLORLESS: 1, ManaType.BLUE: 2}


def _cast_with_target(game: Any, player: Any, card: Any, target: Any) -> None:
    """Cast *card* via the engine while another spell is on the stack, then
    resolve the whole stack. (test_utils.cast_spell forbids a non-empty
    stack, so a counterspell must be driven through the engine directly.)"""
    player._script.appendleft(target)
    engine_cast_spell(game, player, card)
    _resolve_top_of_stack(game)


class TestManaSculptProperties:
    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_cannot_cast_with_empty_stack(self) -> None:
        game = create_game()
        sculpt = ManaSculpt(owner=game.players[0])
        assert sculpt.can_cast(game) is False
        assert sculpt.get_targets(game) == []


class TestManaSculptCounter:
    def test_counters_target_spell(self) -> None:
        game = create_game()
        p0, p1 = game.players
        victim, victim_obj = _push_victim(game, 1, cost="{3}")

        sculpt = ManaSculpt(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[sculpt], mana=_sculpt_mana())

        _cast_with_target(game, p0, sculpt, victim_obj)

        assert game.get_graveyard(p1).contains(victim)
        assert game.stack.is_empty()


class TestManaSculptDeferredMana:
    def test_wizard_grants_deferred_colorless(self) -> None:
        game = create_game()
        p0, p1 = game.players
        victim, victim_obj = _push_victim(game, 1, cost="{4}")

        sculpt = ManaSculpt(owner=p0, controller=p0)
        set_board_state(
            game, 0, hand=[sculpt], battlefield=[_wizard()], mana=_sculpt_mana()
        )

        _cast_with_target(game, p0, sculpt, victim_obj)
        assert game.get_graveyard(p1).contains(victim)
        # Mana Sculpt itself was spent — pool empty before the deferred trigger.
        assert p0.mana_pool.total() == 0

        # Simulate the beginning of p0's next main phase.
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(
                player=p0, phase=Phase.PRECOMBAT_MAIN
            ),
        )
        _resolve_top_of_stack(game)

        assert p0.mana_pool.get(ManaType.COLORLESS) == 4

        # One-shot: a later main phase does not add more mana.
        p0.mana_pool.empty()
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(
                player=p0, phase=Phase.PRECOMBAT_MAIN
            ),
        )
        _resolve_top_of_stack(game)
        assert p0.mana_pool.total() == 0

    def test_no_wizard_no_deferred_mana(self) -> None:
        game = create_game()
        p0, p1 = game.players
        victim, victim_obj = _push_victim(game, 1, cost="{4}")

        sculpt = ManaSculpt(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[sculpt], mana=_sculpt_mana())

        _cast_with_target(game, p0, sculpt, victim_obj)
        assert game.get_graveyard(p1).contains(victim)

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(
                player=p0, phase=Phase.PRECOMBAT_MAIN
            ),
        )
        _resolve_top_of_stack(game)

        assert p0.mana_pool.total() == 0
