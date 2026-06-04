"""Tests for SOS 57 — Mana Sculpt (counter + scheduled mana)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import cast_spell as engine_cast
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state
from test_utils import _resolve_top_of_stack


class DummySpell(Instant):
    """Test-only no-op instant costing {3}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dummy Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        pass


def _setup(with_wizard: bool):
    game = create_game()
    p1, p2 = game.players

    dummy = DummySpell(owner=p2, controller=p2)
    set_board_state(game, 1, hand=[dummy], mana={ManaType.COLORLESS: 3}, life=20)

    sculpt = ManaSculpt(owner=p1, controller=p1)
    bf = []
    if with_wizard:
        wiz = Creature(name="Wiz", owner=p1, controller=p1,
                       base_power=1, base_toughness=1, subtypes={"Wizard"})
        wiz.card_types = {CardType.CREATURE}
        bf = [wiz]
    set_board_state(game, 0, battlefield=bf, hand=[sculpt],
                    mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1}, life=20)

    # p2 casts the dummy so it sits on the stack.
    engine_cast(game, p2, dummy)
    dummy_obj = game.stack.peek()

    # p1 responds with Mana Sculpt targeting the dummy spell.
    p1._script.appendleft(dummy_obj)
    engine_cast(game, p1, sculpt)
    _resolve_top_of_stack(game)
    return game, p1, p2, dummy, sculpt


class TestProperties:
    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name_cost(self) -> None:
        c = ManaSculpt(owner=None)
        assert c.name == "Mana Sculpt"
        assert c.mana_cost == ManaCost.parse("{1}{U}{U}")


class TestCounter:
    def test_records_mana_spent_on_cast(self) -> None:
        game = create_game()
        p1, p2 = game.players
        dummy = DummySpell(owner=p2, controller=p2)
        set_board_state(game, 1, hand=[dummy], mana={ManaType.COLORLESS: 3})
        engine_cast(game, p2, dummy)
        assert dummy.mana_spent == 3

    def test_counters_target_spell(self) -> None:
        game, p1, p2, dummy, sculpt = _setup(with_wizard=False)
        assert game.stack.is_empty()
        assert dummy in p2.zones[Zone.GRAVEYARD].get_all()
        assert sculpt in p1.zones[Zone.GRAVEYARD].get_all()


class TestScheduledMana:
    def test_wizard_grants_C_at_next_main_phase(self) -> None:
        game, p1, p2, dummy, sculpt = _setup(with_wizard=True)
        p1.mana_pool.empty()

        # Simulate the beginning of p1's next main phase.
        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(phase=Phase.PRECOMBAT_MAIN)
        )
        _resolve_top_of_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

        # One-shot: a subsequent main phase grants no more mana.
        p1.mana_pool.empty()
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(phase=Phase.PRECOMBAT_MAIN)
        )
        _resolve_top_of_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_no_wizard_no_mana(self) -> None:
        game, p1, p2, dummy, sculpt = _setup(with_wizard=False)
        p1.mana_pool.empty()
        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(phase=Phase.PRECOMBAT_MAIN)
        )
        _resolve_top_of_stack(game)
        assert p1.mana_pool.total() == 0

    def test_mana_only_on_your_main_phase(self) -> None:
        game, p1, p2, dummy, sculpt = _setup(with_wizard=True)
        p1.mana_pool.empty()
        # Opponent's main phase: active player is p2, so no mana for p1.
        game.active_player_index = 1
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(phase=Phase.PRECOMBAT_MAIN)
        )
        _resolve_top_of_stack(game)
        assert p1.mana_pool.total() == 0
