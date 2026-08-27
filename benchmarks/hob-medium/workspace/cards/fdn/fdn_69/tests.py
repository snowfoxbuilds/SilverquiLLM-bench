"""Reference test for FDN 69 — Seeker's Folly.

Exemplar for a **modal spell** (Phase D, Pattern 5 + Pattern 1). The mode is
chosen in ``get_targets`` (answered by a MODE Intent) and stored on
``chosen_mode``; mode 0 ("Target opponent discards two cards") returns a
player-target requirement, mode 1 ("Creatures your opponents control get -1/-1")
is a non-targeted board effect resolved via a continuous effect.
"""

from __future__ import annotations

from cards.fdn.fdn_69.card_impl import SeekersFolly
from engine.card import Creature
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _specs_for_mode(game, player, card, mode_name):
    """Drive ``get_targets`` with a MODE Intent selecting *mode_name*."""
    player.start_intent(
        "mode",
        Intent(
            pattern=GameRef(card=frozenset({("name", card.name)})),
            preferences=(Decision.mode(mode_name),),
        ),
    )
    try:
        return card.get_targets(game)
    finally:
        player.end_intent("mode")


def _cast_mode(game, player_index, player, card_name, mode_name):
    """Cast a modal spell selecting *mode_name* (no target) via an Intent."""
    player.start_intent(
        "mode",
        Intent(
            pattern=GameRef(card=frozenset({("name", card_name)})),
            preferences=(Decision.mode(mode_name),),
        ),
    )
    try:
        cast_spell(game, player_index, card_name)
    finally:
        player.end_intent("mode")


class TestSeekersFollyProperties:
    def test_static_data(self):
        card = SeekersFolly(owner=None)
        assert card.name == "Seeker's Folly"
        assert card.mana_cost == ManaCost.parse("{2}{B}")
        names = [m.name for m in card.get_modes()]
        assert names == ["Discard", "Shrink"]


class TestSeekersFollyModes:
    def test_mode0_targets_an_opponent_who_discards_two(self):
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        folly = SeekersFolly(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[folly],
                        mana={ManaType.BLACK: 1, ManaType.COLORLESS: 2})
        set_board_state(game, 1, hand=[_bear("H1"), _bear("H2"), _bear("H3")])
        game.phase = Phase.PRECOMBAT_MAIN

        # cast_spell with a player target defaults the mode to the first offered
        # (Discard = mode 0) and targets p2.
        cast_spell(game, 0, "Seeker's Folly", targets=[p2])
        assert folly.chosen_mode == 0
        assert len(game.get_hand(p2).get_all()) == 1  # two discarded

    def test_mode1_shrinks_opponents_creatures(self):
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        folly = SeekersFolly(owner=p1, controller=p1)
        mine = _bear("My Bear")
        theirs = _bear("Their Bear")
        set_board_state(game, 0, hand=[folly], battlefield=[mine],
                        mana={ManaType.BLACK: 1, ManaType.COLORLESS: 2})
        set_board_state(game, 1, battlefield=[theirs])
        game.phase = Phase.PRECOMBAT_MAIN

        _cast_mode(game, 0, p1, "Seeker's Folly", "Shrink")
        game.effect_manager.apply_all(game)
        assert folly.chosen_mode == 1
        # Only the opponent's creatures shrink.
        assert (theirs.power, theirs.toughness) == (1, 1)
        assert (mine.power, mine.toughness) == (2, 2)

    def test_option_set_mode0_targets_only_opponents(self):
        """Legality invariant: mode 0's requirement accepts an opponent player
        and rejects you and non-player objects; mode 1 requests no target."""
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        folly = SeekersFolly(owner=p1, controller=p1)
        creature = _bear("Some Creature")
        set_board_state(game, 0, battlefield=[folly])
        set_board_state(game, 1, battlefield=[creature])

        mode0 = _specs_for_mode(game, p1, folly, "Discard")
        assert folly.chosen_mode == 0
        assert len(mode0) == 1
        spec = mode0[0]
        assert spec.filter_fn(p2) is True
        assert spec.filter_fn(p1) is False
        assert spec.filter_fn(creature) is False

        mode1 = _specs_for_mode(game, p1, folly, "Shrink")
        assert folly.chosen_mode == 1
        assert mode1 == []
