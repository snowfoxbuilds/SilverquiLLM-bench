"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land, Sorcery
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


def _fill_library(game, player_index, cards) -> None:
    """Add cards to a player's library; last item ends up on top."""
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


class TestProperties:
    def test_static_data(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert isinstance(card, Sorcery)
        assert "Lesson" in card.subtypes


class TestResolution:
    def test_exile_until_mv_4_and_cast_some(self) -> None:
        # Library top-down: Bolt {R} (1), Land (0), Bear {3}{G} (4) → 3 exiled.
        game = create_game(scripts=([False, True], []))
        p1 = game.players[0]
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{3}{G}"),
                        base_power=4, base_toughness=4)
        land = Land(name="Wastes")
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        deep = Creature(name="Deep", mana_cost=ManaCost.parse("{1}"),
                        base_power=1, base_toughness=1)
        _fill_library(game, 0, [deep, bear, land, bolt])  # bolt on top

        capstone = ImprovisationCapstone()
        set_board_state(game, 0, hand=[capstone],
                        mana={ManaType.RED: 2, ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Improvisation Capstone")

        # Bolt (declined) and the land remain exiled; Bear was cast free.
        exile = game.get_exile(p1)
        assert exile.contains(bolt)
        assert exile.contains(land)
        assert game.get_battlefield(p1).contains(bear)
        assert p1.zones[Zone.LIBRARY].contains(deep)     # untouched
        # Paradigm: the capstone itself was exiled, not binned.
        assert exile.contains(capstone)
        assert not game.get_graveyard(p1).contains(capstone)

    def test_library_runs_out_before_mv_4(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        land = Land(name="Wastes")
        _fill_library(game, 0, [land])

        capstone = ImprovisationCapstone()
        set_board_state(game, 0, hand=[capstone],
                        mana={ManaType.RED: 2, ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_exile(p1).contains(land)
        assert len(p1.zones[Zone.LIBRARY]) == 0
        assert game.get_exile(p1).contains(capstone)


class TestParadigm:
    def _resolve_capstone(self, game):
        capstone = ImprovisationCapstone()
        set_board_state(game, 0, hand=[capstone],
                        mana={ManaType.RED: 2, ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Improvisation Capstone")
        return capstone

    def _to_p1_next_main(self, game) -> None:
        from test_utils import advance_to_phase

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)   # opponent's main
        assert game.stack.is_empty()                   # not our main phase
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)   # our main again

    def test_recast_each_first_main_phase(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        capstone = self._resolve_capstone(game)
        assert game.get_exile(p1).contains(capstone)

        self._to_p1_next_main(game)
        assert len(game.stack) == 1                    # paradigm trigger

        p1._script.extend(["pass", True, "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)

        # Empty library: the recast exiles nothing, capstone returns to exile.
        assert game.get_exile(p1).contains(capstone)
        assert not game.get_graveyard(p1).contains(capstone)
        # No trigger duplication from the second resolution.
        triggers = game.trigger_manager.get_triggers_for_source(capstone)
        assert len(triggers) == 1

    def test_may_decline_recast(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        capstone = self._resolve_capstone(game)

        self._to_p1_next_main(game)
        p1._script.extend(["pass", False])
        p2._script.extend(["pass"])
        priority_loop(game)

        assert game.get_exile(p1).contains(capstone)
        assert game.stack.is_empty()
