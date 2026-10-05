"""Reference test for FDN 99 — Apothecary Stomper.

Exemplar for a **modal ETB creature** (Phase D, Pattern 5 + Pattern 1). The mode
is chosen at cast in ``get_targets`` (answered by a MODE Intent) and stored on
``chosen_mode``; mode 0 ("Put two +1/+1 counters on target creature you control")
returns a creature-target requirement, mode 1 ("You gain 4 life") is
non-targeted. The effect resolves in ``on_resolve`` before the Stomper arrives.
"""

from __future__ import annotations

from cards.fdn.fdn_99.card_impl import (
    ApothecaryStomper,
    ApothecaryStomperAbility3,
    ApothecaryStomperAbility4,
)
from engine.card import Creature, printed_class
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from test_utils import Intent
from engine.stack import resolve_top_of_stack
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, set_board_state
from test_utils import scenario_game as create_game


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _cast_no_resolve_mode(game, player_index, card, mode, targets):
    """Cast a modal *card* choosing *mode_name*, leaving it on the stack."""
    player = game.players[player_index]
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    prefs = (Decision.mode(printed=mode),) + tuple(
        Decision.obj(instance=game.refs.instance_id(t, Zone.BATTLEFIELD.value)) for t in targets
    )
    player.start_intent(
        "cast",
        Intent(
            pattern=GameRef(card=frozenset({("printed", printed_class(card))})),
            preferences=prefs,
        ),
    )
    try:
        engine_cast_spell(game, player, card)
    finally:
        player.end_intent("cast")


def _cast_mode(game, player_index, player, card, mode):
    player.start_intent(
        "mode",
        Intent(
            pattern=GameRef(card=frozenset({("printed", card)})),
            preferences=(Decision.mode(printed=mode),),
        ),
    )
    try:
        cast_spell(game, player_index, card)
    finally:
        player.end_intent("mode")


class TestApothecaryStomperProperties:
    def test_static_data(self):
        card = ApothecaryStomper(owner=None)
        assert printed_class(card) is ApothecaryStomper
        assert card.mana_cost == ManaCost.parse("{4}{G}{G}")
        assert (card.base_power, card.base_toughness) == (4, 4)
        assert card.subtypes == {"Elephant"}
        assert Keyword.VIGILANCE & card.keywords


class TestApothecaryStomperModes:
    def test_mode0_puts_two_counters_on_your_creature(self):
        game = create_game()
        p1, _p2 = game.players
        game.active_player_index = 0
        stomper = ApothecaryStomper(owner=p1, controller=p1)
        mine = _bear("My Bear")
        set_board_state(
            game,
            0,
            hand=[stomper],
            battlefield=[mine],
            mana={ManaType.GREEN: 2, ManaType.COLORLESS: 4},
        )
        game.phase = Phase.PRECOMBAT_MAIN

        # First offered mode is Counters (mode 0); target the friendly creature.
        cast_spell(game, 0, ApothecaryStomper, targets=[mine])
        assert mine.plus_one_counters == 2
        assert (mine.power, mine.toughness) == (4, 4)
        assert game.get_battlefield(p1).contains(stomper)

    def test_mode1_gains_four_life(self):
        game = create_game()
        p1, _p2 = game.players
        game.active_player_index = 0
        stomper = ApothecaryStomper(owner=p1, controller=p1)
        set_board_state(
            game, 0, hand=[stomper], life=20, mana={ManaType.GREEN: 2, ManaType.COLORLESS: 4}
        )
        game.phase = Phase.PRECOMBAT_MAIN

        _cast_mode(game, 0, p1, ApothecaryStomper, ApothecaryStomperAbility4)
        assert p1.life == 24
        assert game.get_battlefield(p1).contains(stomper)

    def test_option_set_mode0_targets_only_creatures_you_control(self):
        from engine.card import Artifact
        from test_utils import cast_card, object_preference, prefer

        game = create_game()
        p1, _p2 = game.players
        stomper = ApothecaryStomper(owner=p1)
        mine = _bear("Mine")
        theirs = _bear("Theirs")
        rock = Artifact(name="Rock")
        set_board_state(
            game, 0, battlefield=[mine, rock], mana={ManaType.GREEN: 2, ManaType.COLORLESS: 4}
        )
        set_board_state(game, 1, battlefield=[theirs])
        prefer(
            p1,
            Decision.mode(printed=ApothecaryStomperAbility3),
            object_preference(game, theirs),
            object_preference(game, rock),
            object_preference(game, mine),
        )
        cast_card(game, p1, stomper)
        assert mine.plus_one_counters == 2 and theirs.plus_one_counters == 0


class TestApothecaryStomperRevalidation:
    """Rule 608.2b: mode 0 revalidates the FULL predicate ("a creature you
    control") at resolution, not merely control + presence."""

    def test_mode0_no_counters_when_target_not_a_creature(self):
        game = create_game()
        p1, _p2 = game.players
        game.active_player_index = 0
        stomper = ApothecaryStomper(owner=p1, controller=p1)
        mine = _bear("My Bear")
        set_board_state(
            game,
            0,
            hand=[stomper],
            battlefield=[mine],
            mana={ManaType.GREEN: 2, ManaType.COLORLESS: 4},
        )
        game.phase = Phase.PRECOMBAT_MAIN

        _cast_no_resolve_mode(game, 0, stomper, ApothecaryStomperAbility3, [mine])
        # Before resolution the chosen target loses creature-ness.
        mine.card_types = set(mine.card_types) - {CardType.CREATURE}
        while not game.stack.is_empty():
            resolve_top_of_stack(game)

        # No counters were placed.
        assert mine.plus_one_counters == 0
        # The Stomper itself still entered the battlefield.
        assert game.get_battlefield(p1).contains(stomper)
