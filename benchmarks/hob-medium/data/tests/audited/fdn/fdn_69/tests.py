"""Seeker's Folly selects modes through Intents and changes only opponent state."""

from __future__ import annotations

from cards.fdn.fdn_69.card_impl import SeekersFolly
from engine.card import Creature
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import ManaCost, ManaType, Phase
from test_utils import cast_spell, create_game, set_board_state


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


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


class TestSeekersFollyModes:
    def test_mode0_targets_an_opponent_who_discards_two(self):
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        folly = SeekersFolly(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[folly], mana={ManaType.BLACK: 1, ManaType.COLORLESS: 2})
        set_board_state(game, 1, hand=[_bear("H1"), _bear("H2"), _bear("H3")])
        game.phase = Phase.PRECOMBAT_MAIN

        # cast_spell with a player target defaults the mode to the first offered
        # (Discard = mode 0) and targets p2.
        cast_spell(game, 0, "Seeker's Folly", targets=[p2])
        assert len(game.get_hand(p2).get_all()) == 1  # two discarded

    def test_mode1_shrinks_opponents_creatures(self):
        game = create_game()
        p1, _p2 = game.players
        game.active_player_index = 0
        folly = SeekersFolly(owner=p1, controller=p1)
        mine = _bear("My Bear")
        theirs = _bear("Their Bear")
        set_board_state(
            game,
            0,
            hand=[folly],
            battlefield=[mine],
            mana={ManaType.BLACK: 1, ManaType.COLORLESS: 2},
        )
        set_board_state(game, 1, battlefield=[theirs])
        game.phase = Phase.PRECOMBAT_MAIN

        _cast_mode(game, 0, p1, "Seeker's Folly", "Shrink")
        game.effect_manager.apply_all(game)
        # Only the opponent's creatures shrink.
        assert (theirs.power, theirs.toughness) == (1, 1)
        assert (mine.power, mine.toughness) == (2, 2)

    def test_discard_mode_cannot_target_the_caster_or_a_creature(self):
        game = create_game()
        p1, p2 = game.players
        folly = SeekersFolly(owner=p1, controller=p1)
        mine = [_bear("Mine one"), _bear("Mine two")]
        theirs = [_bear("Theirs one"), _bear("Theirs two"), _bear("Theirs three")]
        creature = _bear("Not a player")
        set_board_state(
            game, 0, hand=[folly, *mine], mana={ManaType.BLACK: 1, ManaType.COLORLESS: 2}
        )
        set_board_state(game, 1, hand=theirs, battlefield=[creature])
        p1.set_baseline(
            Intent(
                pattern=GameRef(),
                preferences=(
                    Decision.mode("Discard"),
                    Decision.player(seat=0),
                    Decision.player(seat=1),
                ),
            )
        )
        p2.set_baseline(Intent(pattern=GameRef()))
        cast_spell(game, 0, folly.name)
        assert game.get_hand(p1).get_all() == mine
        assert len(game.get_hand(p2).get_all()) == 1
        assert game.get_battlefield(p2).contains(creature)
