"""Tests for SOS 57 — Mana Sculpt (counter + delayed mana, uses E2)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Sorcery
from engine.casting import cast_spell as engine_cast
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


def _resolve_stack(game) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class _BigGainSorcery(Sorcery):
    """Probe sorcery: controller gains 100 life on resolve (so we can tell if
    it was countered)."""

    def __init__(self, cost: str = "{2}", **kwargs: Any) -> None:
        kwargs.setdefault("name", "BigGain")
        kwargs.setdefault("mana_cost", ManaCost.parse(cost))
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        if self.controller is not None:
            self.controller.life += 100


def _wizard() -> Creature:
    return Creature(name="Wiz", base_power=1, base_toughness=1, subtypes={"Wizard"})


def _cast_target_then_sculpt(game, p0, target_card, sculpt) -> Any:
    """Cast *target_card* (a sorcery) onto the stack, then cast Mana Sculpt in
    response targeting it.  Returns the target's StackObject."""
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    engine_cast(game, p0, target_card)
    target_so = game.stack.peek()
    p0._script.append(target_so)  # Mana Sculpt's target
    engine_cast(game, p0, sculpt)
    return target_so


def _advance_to_next_own_main(game, pidx: int, after_turn: int) -> None:
    for _ in range(60):
        game.advance_phase()
        _resolve_stack(game)
        if (
            game.active_player_index == pidx
            and game.phase == Phase.PRECOMBAT_MAIN
            and game.turn_number > after_turn
        ):
            return
    raise AssertionError("did not reach the player's next precombat main")


class TestProperties:
    def test_static_data(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")
        assert CardType.INSTANT in card.card_types

    def test_cannot_cast_with_empty_stack(self) -> None:
        game = create_game()
        assert ManaSculpt(owner=None).can_cast(game) is False


class TestCounter:
    def test_counters_target_spell(self) -> None:
        game = create_game()
        p0 = game.players[0]
        target = _BigGainSorcery(cost="{2}", owner=p0, controller=p0)
        sculpt = ManaSculpt(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[target, sculpt],
                        mana={ManaType.COLORLESS: 3, ManaType.BLUE: 2})
        before = p0.life
        _cast_target_then_sculpt(game, p0, target, sculpt)
        _resolve_stack(game)
        # The sorcery was countered → its effect never happened.
        assert p0.life == before
        assert game.get_graveyard(p0).contains(target)
        assert game.get_graveyard(p0).contains(sculpt)


class TestDelayedMana:
    def test_mana_added_next_main_with_wizard(self) -> None:
        game = create_game()
        p0 = game.players[0]
        wiz = _wizard()
        target = _BigGainSorcery(cost="{2}{U}", owner=p0, controller=p0)  # cmc 3
        sculpt = ManaSculpt(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[wiz], hand=[target, sculpt],
                        mana={ManaType.COLORLESS: 4, ManaType.BLUE: 3})
        _cast_target_then_sculpt(game, p0, target, sculpt)
        _resolve_stack(game)  # counter resolves, registers delayed trigger
        cast_turn = game.turn_number
        _advance_to_next_own_main(game, 0, cast_turn)
        # 3 mana was spent on the countered spell ({2}{U}).
        assert p0.mana_pool.get(ManaType.COLORLESS) == 3

    def test_no_mana_without_wizard(self) -> None:
        game = create_game()
        p0 = game.players[0]
        target = _BigGainSorcery(cost="{2}{U}", owner=p0, controller=p0)
        sculpt = ManaSculpt(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[target, sculpt],
                        mana={ManaType.COLORLESS: 4, ManaType.BLUE: 3})
        _cast_target_then_sculpt(game, p0, target, sculpt)
        _resolve_stack(game)
        cast_turn = game.turn_number
        _advance_to_next_own_main(game, 0, cast_turn)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0

    def test_amount_matches_mana_spent(self) -> None:
        game = create_game()
        p0 = game.players[0]
        wiz = _wizard()
        target = _BigGainSorcery(cost="{4}{U}{U}", owner=p0, controller=p0)  # cmc 6
        sculpt = ManaSculpt(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[wiz], hand=[target, sculpt],
                        mana={ManaType.COLORLESS: 5, ManaType.BLUE: 4})
        _cast_target_then_sculpt(game, p0, target, sculpt)
        _resolve_stack(game)
        cast_turn = game.turn_number
        _advance_to_next_own_main(game, 0, cast_turn)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 6
