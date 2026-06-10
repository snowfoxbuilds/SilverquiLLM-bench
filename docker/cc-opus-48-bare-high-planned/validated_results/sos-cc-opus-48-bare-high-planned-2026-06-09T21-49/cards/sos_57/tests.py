"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Sorcery
from engine.casting import cast_spell as engine_cast
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_utils import create_game, set_board_state


class _Dummy(Sorcery):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Dummy Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        pass


def _put_spell_on_stack(game):
    """p1 casts a {2} sorcery, leaving it on the stack; return its StackObject."""
    p1 = game.players[1]
    dummy = _Dummy()
    set_board_state(game, 1, hand=[dummy], mana={ManaType.COLORLESS: 2})
    game.active_player_index = 1
    game.priority_player_index = 1
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    engine_cast(game, p1, dummy)
    return game.stack.peek()


def _advance_to_p0_precombat(game):
    """Drive the real advance_phase into p0's precombat main (E2 fires there)."""
    p0 = game.players[0]
    game.active_player_index = 0
    game.phase = Phase.BEGINNING
    game.step = Step.DRAW
    game.advance_phase()  # -> PRECOMBAT_MAIN, active still p0, fires E2
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestProperties:
    def test_static(self):
        c = ManaSculpt(owner=None)
        assert c.mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_cannot_cast_with_empty_stack(self):
        game = create_game()
        assert ManaSculpt(owner=None).can_cast(game) is False


class TestCounter:
    def test_counter_with_wizard_grants_delayed_mana(self):
        game = create_game()
        p0, p1 = game.players
        wizard = Creature(name="Apprentice", base_power=1, base_toughness=1,
                          subtypes={"Wizard"})
        set_board_state(game, 0, battlefield=[wizard],
                        hand=[ManaSculpt(owner=None)],
                        mana={ManaType.COLORLESS: 1, ManaType.BLUE: 2})
        target_so = _put_spell_on_stack(game)
        ms = next(c for c in p0.zones[Zone.HAND].get_all()
                  if getattr(c, "name", "") == "Mana Sculpt")
        p0._script.append(target_so)
        engine_cast(game, p0, ms)
        # Resolve Mana Sculpt (counters the dummy).
        game.stack.pop().on_resolve(game)
        # Dummy was countered into p1's graveyard.
        assert any(getattr(c, "name", "") == "Dummy Sorcery"
                   for c in p1.zones[Zone.GRAVEYARD].get_all())
        # Delayed: {C}=2 (mana spent on the dummy) at p0's next precombat main.
        _advance_to_p0_precombat(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 2

    def test_counter_without_wizard_no_mana(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 0, battlefield=[],
                        hand=[ManaSculpt(owner=None)],
                        mana={ManaType.COLORLESS: 1, ManaType.BLUE: 2})
        target_so = _put_spell_on_stack(game)
        ms = next(c for c in p0.zones[Zone.HAND].get_all()
                  if getattr(c, "name", "") == "Mana Sculpt")
        p0._script.append(target_so)
        engine_cast(game, p0, ms)
        game.stack.pop().on_resolve(game)
        assert any(getattr(c, "name", "") == "Dummy Sorcery"
                   for c in p1.zones[Zone.GRAVEYARD].get_all())
        _advance_to_p0_precombat(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0
