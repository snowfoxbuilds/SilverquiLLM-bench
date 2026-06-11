"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import cast_spell as engine_cast_spell, resolve_top
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import advance_to_phase, create_game, set_board_state


class Probe(Instant):
    """Test-local instant: controller gains 1 life."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Probe")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 1


def _counter_setup(game, *, wizard):
    """Opponent casts Probe; p1 casts Mana Sculpt targeting it.

    Returns the probe card. Leaves both spells resolved/countered.
    """
    p1, p2 = game.players
    battlefield = []
    if wizard:
        battlefield.append(
            Creature(name="Sage", base_power=1, base_toughness=1, subtypes={"Wizard"})
        )
    sculpt = ManaSculpt(owner=p1)
    set_board_state(game, 0, battlefield=battlefield, hand=[sculpt],
                    mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})

    probe = Probe(owner=p2)
    set_board_state(game, 1, hand=[probe], mana={ManaType.COLORLESS: 2})
    engine_cast_spell(game, p2, probe)

    target = game.stack.peek()
    p1._script.appendleft(target)
    engine_cast_spell(game, p1, sculpt)
    resolve_top(game)  # Mana Sculpt resolves, countering the probe
    return probe


class TestCounter:
    def test_counters_target_spell(self):
        game = create_game()
        p1, p2 = game.players
        probe = _counter_setup(game, wizard=True)

        assert game.stack.is_empty()
        assert p2.zones[Zone.GRAVEYARD].contains(probe)
        assert p2.life == 20  # probe never resolved

    def test_cannot_cast_with_empty_stack(self):
        game = create_game()
        sculpt = ManaSculpt(owner=game.players[0])
        assert sculpt.can_cast(game) is False


class TestDelayedMana:
    def test_wizard_gives_mana_at_next_main(self):
        """Countered spell cost {2}: at your next precombat main, add {C}{C}."""
        game = create_game()
        p1 = game.players[0]
        _counter_setup(game, wizard=True)  # turn 1, p1's untap step

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert len(game.stack) == 1
        resolve_top(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

    def test_no_wizard_no_mana(self):
        game = create_game()
        p1 = game.players[0]
        _counter_setup(game, wizard=False)

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.stack.is_empty()
        assert p1.mana_pool.total() == 0

    def test_does_not_fire_on_opponents_main(self):
        """Cast during p1's end step: skips p2's main, fires on p1's next."""
        from engine.types import Step

        game = create_game()
        p1, p2 = game.players
        advance_to_phase(game, Phase.ENDING, Step.END)
        _counter_setup(game, wizard=True)

        # Turn 2: p2's precombat main — no trigger for p1.
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p2
        assert game.stack.is_empty()

        # Turn 3: p1's precombat main — trigger fires, one-shot.
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p1
        assert len(game.stack) == 1
        resolve_top(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

        # One-shot: gone on p1's following main.
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # turn 4 (p2)
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # turn 5 (p1)
        assert game.active_player is p1
        assert game.stack.is_empty()

    def test_free_cast_spell_gives_no_mana(self):
        """A spell cast without paying mana: amount spent is 0."""
        from engine.casting import cast_spell_free

        game = create_game()
        p1, p2 = game.players
        wiz = Creature(name="Sage", base_power=1, base_toughness=1,
                       subtypes={"Wizard"})
        sculpt = ManaSculpt(owner=p1)
        set_board_state(game, 0, battlefield=[wiz], hand=[sculpt],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        probe = Probe(owner=p2)
        p2.zones[Zone.EXILE].add(probe)
        cast_spell_free(game, p2, probe, Zone.EXILE)

        p1._script.appendleft(game.stack.peek())
        engine_cast_spell(game, p1, sculpt)
        resolve_top(game)
        assert p2.zones[Zone.GRAVEYARD].contains(probe)

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.stack.is_empty()
        assert p1.mana_pool.total() == 0
