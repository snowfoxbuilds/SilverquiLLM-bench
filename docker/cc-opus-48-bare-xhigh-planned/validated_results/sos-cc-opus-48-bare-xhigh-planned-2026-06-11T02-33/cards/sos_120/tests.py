"""Tests for SOS 120 — Improvisation Capstone (exile-cast + Paradigm via E2)."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Sorcery
from engine.casting import resolve_top
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import create_game, cast_spell, set_board_state, advance_to_phase


class FreeBolt(Instant):
    """MV 4; deals 3 to the opponent on resolve."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "FreeBolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        from engine.game import deal_damage
        opp = [p for p in game.players if p is not self.controller][0]
        deal_damage(game, self, opp, 3)


def _fill(game, idx, n, mv=2):
    lib = game.players[idx].zones[Zone.LIBRARY]
    for i in range(n):
        lib.add(Creature(name=f"Filler{i}", mana_cost=ManaCost.parse("{%d}" % mv),
                         base_power=1, base_toughness=1))


def _cast_capstone(game, inner_choices):
    p0 = game.players[0]
    set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                    mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
    p0._script.extend(inner_choices)
    cast_spell(game, 0, "Improvisation Capstone")


class TestProperties:
    def test_basic(self):
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert "Lesson" in card.subtypes


class TestExile:
    def test_exiles_until_mv4_and_self_exiles(self):
        game = create_game()
        p0 = game.players[0]
        _fill(game, 0, 5, mv=2)
        _cast_capstone(game, [False, False])  # decline both casts
        # MV 2 + 2 = 4 → exactly 2 cards exiled.
        assert len(p0.zones[Zone.LIBRARY]) == 3
        exile_names = [c.name for c in p0.zones[Zone.EXILE].get_all()]
        assert exile_names.count("Improvisation Capstone") == 1  # self-exiled
        assert sum(1 for n in exile_names if n.startswith("Filler")) == 2
        assert not p0.zones[Zone.GRAVEYARD].contains(
            next(c for c in p0.zones[Zone.EXILE].get_all()
                 if c.name == "Improvisation Capstone")
        )

    def test_cast_exiled_spell_for_free(self):
        game = create_game()
        p0, p1 = game.players
        p0.zones[Zone.LIBRARY].add(FreeBolt(owner=None))  # only card, MV 4
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        p0._script.append(True)  # yes, cast the exiled FreeBolt
        cast_spell(game, 0, "Improvisation Capstone")
        assert p1.life == 17  # FreeBolt resolved
        assert p0.zones[Zone.GRAVEYARD].contains(
            next(c for c in p0.zones[Zone.GRAVEYARD].get_all() if c.name == "FreeBolt")
        )

    def test_library_runs_out(self):
        game = create_game()
        p0 = game.players[0]
        _fill(game, 0, 1, mv=2)  # only 1 card, MV 2 < 4
        _cast_capstone(game, [False])
        assert len(p0.zones[Zone.LIBRARY]) == 0
        assert sum(1 for c in p0.zones[Zone.EXILE].get_all()
                   if c.name.startswith("Filler")) == 1


class TestParadigm:
    def test_recurring_copy_each_first_main(self):
        game = create_game()
        p0, p1 = game.players
        _fill(game, 0, 6, mv=2)
        _cast_capstone(game, [False, False])  # original peels 2 → library 4
        assert len(p0.zones[Zone.LIBRARY]) == 4
        capstone = next(c for c in p0.zones[Zone.EXILE].get_all()
                        if c.name == "Improvisation Capstone")

        # Reach p0's next precombat main (turn 3 in a 2-player game).
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)   # turn 2, p1
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)   # turn 3, p0
        assert game.active_player is p0

        # Paradigm fired: cast the copy (yes), decline its 2 inner casts.
        p0._script.extend([True, False, False])
        resolve_top(game)   # the Paradigm trigger → casts the copy
        resolve_top(game)   # the copy resolves → peels 2 more

        assert len(p0.zones[Zone.LIBRARY]) == 2          # copy peeled 2 more
        assert p0.zones[Zone.EXILE].contains(capstone)   # original stays exiled
        assert any(c.name == "Improvisation Capstone"
                   for c in p0.zones[Zone.GRAVEYARD].get_all())  # the copy
