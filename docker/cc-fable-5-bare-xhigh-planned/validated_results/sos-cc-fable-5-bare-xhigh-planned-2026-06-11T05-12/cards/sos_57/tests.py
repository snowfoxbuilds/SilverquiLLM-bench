"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.casting import CastingError, cast_spell as engine_cast_spell
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType, Phase, Step, Zone
from test_utils import advance_to_phase, create_game, set_board_state


def _to_p2_main(game: Any) -> None:
    """Advance to turn 2, player 2's precombat main."""
    advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
    game.advance_phase()  # wrap to turn 2 — active player 2
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)


def _to_next_p1_main(game: Any) -> None:
    """Advance from p2's turn into p1's next precombat main."""
    advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
    game.advance_phase()  # wrap — active player 1
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)


def _counter_scenario(game: Any, countered_spell: Any, *, spell_mana,
                      sculpt_mana=None) -> None:
    """p2 casts *countered_spell*; p1 counters it with Mana Sculpt."""
    p1, p2 = game.players
    _to_p2_main(game)
    # Mana must be granted after advancing phases (pools empty per phase).
    set_board_state(game, 1, hand=[countered_spell], mana=spell_mana)
    engine_cast_spell(game, p2, countered_spell)
    spell_so = game.stack.peek()
    sculpt = ManaSculpt()
    set_board_state(
        game, 0, hand=[sculpt],
        mana=sculpt_mana or {ManaType.BLUE: 2, ManaType.COLORLESS: 1},
    )
    p1._script.extend([spell_so, "pass"])
    p2._script.extend(["pass"])
    engine_cast_spell(game, p1, sculpt)
    priority_loop(game)


class TestProperties:
    def test_static_data(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")
        assert CardType.INSTANT in card.card_types


class TestCounter:
    def test_counters_target_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", mana_cost=ManaCost(generic=3),
                        base_power=2, base_toughness=2)
        _counter_scenario(game, bear, spell_mana={ManaType.COLORLESS: 3})
        assert p2.zones[Zone.GRAVEYARD].contains(bear)
        assert not game.get_battlefield(p2).contains(bear)
        assert game.stack.is_empty()

    def test_cannot_cast_with_empty_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt()
        set_board_state(game, 0, hand=[sculpt],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        with pytest.raises(CastingError):
            engine_cast_spell(game, p1, sculpt)


class TestDelayedMana:
    def test_wizard_grants_c_equal_to_mana_spent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = Creature(name="Sage", subtypes={"Wizard"},
                          base_power=1, base_toughness=2)
        set_board_state(game, 0, battlefield=[wizard])
        bear = Creature(name="Bear", mana_cost=ManaCost(generic=3),
                        base_power=2, base_toughness=2)
        _counter_scenario(game, bear, spell_mana={ManaType.COLORLESS: 3})
        _to_next_p1_main(game)
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_no_wizard_no_delayed_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", mana_cost=ManaCost(generic=3),
                        base_power=2, base_toughness=2)
        _counter_scenario(game, bear, spell_mana={ManaType.COLORLESS: 3})
        _to_next_p1_main(game)
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert p1.mana_pool.total() == 0

    def test_amount_is_mana_actually_paid_not_mana_value(self) -> None:
        """A cost-reduced spell yields its paid amount, not its printed cost."""

        class Discounted(Sorcery):
            def __init__(self, **kwargs: Any) -> None:
                kwargs.setdefault("name", "Discounted")
                kwargs.setdefault("mana_cost", ManaCost(generic=4))
                super().__init__(**kwargs)

            def cost_reduction(self, game: Any) -> int:
                return 3

        game = create_game()
        p1, p2 = game.players
        wizard = Creature(name="Sage", subtypes={"Wizard"},
                          base_power=1, base_toughness=2)
        set_board_state(game, 0, battlefield=[wizard])
        spell = Discounted()
        _counter_scenario(game, spell, spell_mana={ManaType.COLORLESS: 1})
        assert p2.zones[Zone.GRAVEYARD].contains(spell)
        _to_next_p1_main(game)
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
