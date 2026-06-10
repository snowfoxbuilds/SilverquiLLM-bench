"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell as ecast
from engine.state_based_actions import resolve_state_based_actions
from engine.types import ManaCost, ManaType, Phase
from test_utils import create_game, set_board_state


class BigSpell(Sorcery):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Big Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        super().__init__(**kwargs)
        self.resolved = False

    def on_resolve(self, game):
        self.resolved = True


def _drain(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _setup_counter(with_wizard):
    game = create_game()
    p0 = game.players[0]
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0
    bf = []
    if with_wizard:
        bf.append(Creature(name="Lecturer", base_power=1, base_toughness=1,
                           subtypes={"Wizard"}))
    big = BigSpell(owner=None)
    sculpt = ManaSculpt(owner=None)
    set_board_state(game, 0, battlefield=bf, hand=[big, sculpt],
                    mana={ManaType.COLORLESS: 3, ManaType.RED: 1, ManaType.BLUE: 2})
    # Cast Big Spell (stays on stack).
    ecast(game, p0, big)
    target_so = game.stack.peek()
    # Respond with Mana Sculpt targeting Big Spell.
    p0._script.appendleft(target_so)
    ecast(game, p0, sculpt)
    _drain(game)  # Mana Sculpt resolves first → counters Big Spell.
    return game, p0, big


def _advance_to_my_next_precombat_main(game, player):
    for _ in range(40):
        game.advance_phase()
        if (game.phase is Phase.PRECOMBAT_MAIN and game.active_player is player
                and game.turn_number > 1):
            return
    raise AssertionError("did not reach player's next precombat main")


class TestProperties:
    def test_basics(self):
        c = ManaSculpt(owner=None)
        assert isinstance(c, Instant)
        assert c.name == "Mana Sculpt"
        assert c.mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_cannot_cast_empty_stack(self):
        game = create_game()
        assert ManaSculpt(owner=None).can_cast(game) is False


class TestCounter:
    def test_target_is_countered(self):
        game, p0, big = _setup_counter(with_wizard=True)
        assert big.resolved is False
        assert game.get_graveyard(p0).contains(big)


class TestDelayedMana:
    def test_wizard_adds_colorless_next_main(self):
        game, p0, big = _setup_counter(with_wizard=True)
        _advance_to_my_next_precombat_main(game, p0)
        _drain(game)  # resolve the delayed trigger
        # Big Spell cost {2}{R} → 3 mana spent → 3 {C}.
        assert p0.mana_pool.get(ManaType.COLORLESS) == 3

    def test_no_wizard_no_mana(self):
        game, p0, big = _setup_counter(with_wizard=False)
        _advance_to_my_next_precombat_main(game, p0)
        _drain(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0
