"""Tests for SOS 57 — Mana Sculpt (counter + delayed Wizard mana via E2)."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import cast_spell as engine_cast, resolve_top
from engine.types import ManaCost, ManaType, Phase
from test_utils import create_game, set_board_state, advance_to_phase


class BigBolt(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "BigBolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{R}"))  # mana spent 5
        super().__init__(**kwargs)


class SmallSpell(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "SmallSpell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))  # mana spent 3
        super().__init__(**kwargs)


def _wizard():
    return Creature(name="Wiz", base_power=1, base_toughness=1, subtypes={"Wizard"})


def _counter_setup(target_spell, p0_battlefield, target_mana):
    """p1 casts *target_spell* onto the stack; p0 holds a Mana Sculpt."""
    game = create_game()
    p0, p1 = game.players
    set_board_state(game, 0, hand=[ManaSculpt(owner=None)], battlefield=p0_battlefield,
                    mana={ManaType.COLORLESS: 1, ManaType.BLUE: 2})
    set_board_state(game, 1, hand=[target_spell], mana=target_mana)
    engine_cast(game, p1, target_spell)        # goes on the stack, unresolved
    target_obj = game.stack.peek()
    p0._script.append(target_obj)              # Mana Sculpt's target
    ms = next(c for c in game.get_hand(p0).get_all() if c.name == "Mana Sculpt")
    engine_cast(game, p0, ms)
    resolve_top(game)                          # Mana Sculpt resolves → counter
    return game, p0, p1


class TestProperties:
    def test_basic(self):
        card = ManaSculpt(owner=None)
        assert isinstance(card, Instant)
        assert card.name == "Mana Sculpt"
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_cannot_cast_without_spell_on_stack(self):
        game = create_game()
        assert ManaSculpt(owner=None).can_cast(game) is False


class TestCounter:
    def test_counters_target(self):
        bb = BigBolt(owner=None)
        game, p0, p1 = _counter_setup(bb, [], {ManaType.COLORLESS: 3, ManaType.RED: 2})
        assert game.get_graveyard(p1).contains(bb)
        assert game.stack.is_empty()

    def test_wizard_adds_mana_next_main_phase(self):
        bb = BigBolt(owner=None)
        game, p0, p1 = _counter_setup(bb, [_wizard()],
                                      {ManaType.COLORLESS: 3, ManaType.RED: 2})
        # No mana yet — it arrives at the beginning of p0's next main phase.
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        resolve_top(game)  # resolve the delayed-mana trigger
        assert p0.mana_pool.get(ManaType.COLORLESS) == 5  # = mana spent on BigBolt

    def test_no_wizard_no_mana(self):
        bb = BigBolt(owner=None)
        game, p0, p1 = _counter_setup(bb, [],  # no Wizard
                                      {ManaType.COLORLESS: 3, ManaType.RED: 2})
        assert game.get_graveyard(p1).contains(bb)  # still countered
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        resolve_top(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0

    def test_amount_equals_mana_spent(self):
        spell = SmallSpell(owner=None)
        game, p0, p1 = _counter_setup(spell, [_wizard()],
                                      {ManaType.COLORLESS: 2, ManaType.RED: 1})
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        resolve_top(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 3  # {2}{R} → 3 spent

    def test_delayed_mana_is_one_shot(self):
        bb = BigBolt(owner=None)
        game, p0, p1 = _counter_setup(bb, [_wizard()],
                                      {ManaType.COLORLESS: 3, ManaType.RED: 2})
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        resolve_top(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 5
        # Advance a full cycle back to p0's precombat main — no second payout.
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p1's main (active p1)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p0's next main
        # Drain any stacked triggers defensively.
        while not game.stack.is_empty():
            resolve_top(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0  # pool emptied, no new mana
