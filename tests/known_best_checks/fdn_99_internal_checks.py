"""Known-Best checks moved out of fdn_99's FDN Audited Tests: no FDN card stops a creature being a creature at instant speed,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_99.card_impl import (
    ApothecaryStomper,
    ApothecaryStomperAbility3,
)
from engine.card import Creature, printed_class
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from engine.stack import resolve_top_of_stack
from engine.types import CardType, ManaType, Phase, Zone
from test_utils import Intent, set_board_state
from test_utils import scenario_game as legacy_game

_MANA = {ManaType.GREEN: 2, ManaType.COLORLESS: 4}


# Legacy setup for the revalidation test below.
def _cast_no_resolve_mode(game, player_index, spell, mode, targets):
    """Cast a modal *card*, choosing *mode* and *targets* for its enters
    trigger, and leave that trigger on the stack."""
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
            pattern=GameRef(card=frozenset({("printed", printed_class(spell))})),
            preferences=prefs,
        ),
    )
    try:
        engine_cast_spell(game, player, spell)
        # The creature spell resolves and its enters trigger goes on the stack
        # as the game settles, choosing its mode and target then (rule 603.3d).
        resolve_top_of_stack(game)
    finally:
        player.end_intent("cast")


class TestApothecaryStomperRevalidation:
    """Rule 608.2b: mode 0 revalidates the FULL predicate ("a creature you
    control") at resolution, not merely control + presence.

    No card makes a creature stop being one in response, so this test still
    changes the target directly."""

    def test_mode0_no_counters_when_target_not_a_creature(self):
        game = legacy_game()
        p1, _p2 = game.players
        game.active_player_index = 0
        stomper = ApothecaryStomper(owner=p1, controller=p1)
        mine = Creature(name="My Bear", base_power=2, base_toughness=2)
        set_board_state(
            game,
            0,
            hand=[stomper],
            battlefield=[mine],
            mana={ManaType.GREEN: 2, ManaType.COLORLESS: 4},
        )
        game.phase = Phase.PRECOMBAT_MAIN

        _cast_no_resolve_mode(game, 0, stomper, ApothecaryStomperAbility3, [mine])
        # Before the trigger resolves the chosen target loses creature-ness;
        # the trigger resolves without the game settling first, which would
        # recompute the creature's types.
        mine.card_types = set(mine.card_types) - {CardType.CREATURE}
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        # No counters were placed.
        assert mine.plus_one_counters == 0
        # The Stomper itself still entered the battlefield.
        assert game.get_battlefield(p1).contains(stomper)
