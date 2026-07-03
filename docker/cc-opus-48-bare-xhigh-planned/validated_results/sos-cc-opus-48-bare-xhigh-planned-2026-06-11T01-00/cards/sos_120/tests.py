"""Tests for Improvisation Capstone (sos_120)."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Instant, Land
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, ManaType, Phase
from test_utils import cast_spell, create_game, set_board_state


class _GainLifeInstant(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Heal")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 2


def _set_library(game, idx, cards):
    """Set the library so cards[-1] is the top card."""
    lib = game.get_library(game.players[idx])
    for o in lib.get_all():
        lib.remove(o)
    for c in cards:
        c.owner = game.players[idx]
        c.controller = game.players[idx]
        lib.add(c)


def _drain(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _vanilla(name, cmc):
    return Instant(name=name, mana_cost=ManaCost(generic=cmc))


class TestProperties:
    def test_static(self):
        c = ImprovisationCapstone(owner=None)
        assert c.name == "Improvisation Capstone"
        assert c.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert CardType.SORCERY in c.card_types
        assert "Lesson" in c.subtypes


class TestExileUntilMv4:
    def test_exiles_until_total_mv_4(self):
        game = create_game()
        cap = ImprovisationCapstone(owner=None)
        # top-down order: bottom ... top. Top three are cmc 2,1,1 → 2,3,4.
        a = _vanilla("A", 1)
        b = _vanilla("B", 1)
        top = _vanilla("Top", 2)
        _set_library(game, 0, [a, b, top])  # 'top' is the top card
        set_board_state(game, 0, hand=[cap],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        p0 = game.players[0]
        # Decline casting each of the 3 exiled (all instants).
        p0._script.extend([False, False, False])
        cast_spell(game, 0, "Improvisation Capstone")
        exile = game.get_exile(p0)
        assert exile.contains(top) and exile.contains(b) and exile.contains(a)
        # Capstone itself exiled by Paradigm.
        assert exile.contains(cap)
        assert not game.get_graveyard(p0).contains(cap)

    def test_library_runs_out(self):
        game = create_game()
        cap = ImprovisationCapstone(owner=None)
        only = _vanilla("Only", 1)  # total MV never reaches 4
        _set_library(game, 0, [only])
        set_board_state(game, 0, hand=[cap],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        p0 = game.players[0]
        p0._script.append(False)
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p0).contains(only)
        assert len(game.get_library(p0)) == 0


class TestFreeCasts:
    def test_cast_exiled_spell_free_land_stays(self):
        game = create_game()
        cap = ImprovisationCapstone(owner=None)
        heal_top = _GainLifeInstant(name="HealTop")
        land = Land(name="Waste")
        heal_bot = _GainLifeInstant(name="HealBot")
        # top-down: heal_bot (bottom), land, heal_top (top)
        _set_library(game, 0, [heal_bot, land, heal_top])
        set_board_state(game, 0, hand=[cap],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        p0 = game.players[0]
        # Exile order: heal_top(2)->2, land(0)->2, heal_bot(2)->4 stop.
        # Offered casts: heal_top, heal_bot (land skipped). Cast both.
        p0._script.extend([True, True])
        cast_spell(game, 0, "Improvisation Capstone")
        assert p0.life == 24  # both heals resolved (+2 +2)
        assert game.get_graveyard(p0).contains(heal_top)
        assert game.get_graveyard(p0).contains(heal_bot)
        assert game.get_exile(p0).contains(land)  # land stays exiled


class TestParadigm:
    def test_recurring_copy_at_next_main(self):
        game = create_game()
        cap = ImprovisationCapstone(owner=None)
        # 4 cmc-2 instants; 2 exiled by the original, 2 by the copy next turn.
        cards = [_vanilla(f"L{i}", 2) for i in range(4)]
        _set_library(game, 0, cards)  # L3 is top
        set_board_state(game, 0, hand=[cap],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        p0 = game.players[0]
        # Original: decline the 2 offered casts.
        p0._script.extend([False, False])
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p0).contains(cap)
        assert len(game.get_library(p0)) == 2  # 2 exiled by original
        cast_turn = game.turn_number

        # Advance to p0's next precombat main; Paradigm trigger fires.
        # Paradigm prompt = yes, then decline the copy's 2 offered casts.
        p0._script.extend([True, False, False])
        for _ in range(40):
            game.advance_phase()
            if (game.phase == Phase.PRECOMBAT_MAIN
                    and game.active_player is p0
                    and game.turn_number > cast_turn):
                break
        _drain(game)
        # Copy exiled the remaining 2 cards; Capstone still in exile.
        assert len(game.get_library(p0)) == 0
        assert game.get_exile(p0).contains(cap)
