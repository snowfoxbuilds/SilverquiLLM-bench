"""Known-Best checks moved out of fdn_104's FDN Audited Tests: no FDN card makes a graveyard card stop being a permanent card,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_104.card_impl import ElvishRegrower
from engine.card import Land, printed_class
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from engine.stack import resolve_top_of_stack
from engine.types import CardType, ManaType, Phase, Zone
from test_utils import Intent, set_board_state
from test_utils import scenario_game as legacy_game

_MANA = {ManaType.GREEN: 2, ManaType.COLORLESS: 2}


# Legacy setup for the revalidation test below.
def _cast_no_resolve(game, player_index, spell, targets, zone=Zone.BATTLEFIELD):
    """Cast *card* choosing *targets* (in *zone*) but leave it on the stack.

    Mirrors ``test_utils.cast_spell`` but stops before resolution so a test can
    mutate the chosen target and then resolve manually to exercise
    resolution-time target revalidation.
    """
    player = game.players[player_index]
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    prefs = tuple(Decision.obj(instance=game.refs.instance_id(t, zone.value)) for t in targets)
    player.start_intent(
        "cast",
        Intent(
            pattern=GameRef(card=frozenset({("printed", printed_class(spell))})),
            preferences=prefs,
        ),
    )
    try:
        engine_cast_spell(game, player, spell)
    finally:
        player.end_intent("cast")


def _setup(dead=None):
    game = legacy_game()
    p1, p2 = game.players
    game.active_player_index = 0
    regrower = ElvishRegrower(owner=p1, controller=p1)
    dead = dead if dead is not None else Land(name="Fallen Forest")
    set_board_state(
        game,
        0,
        hand=[regrower],
        graveyard=[dead],
        mana={ManaType.GREEN: 2, ManaType.COLORLESS: 2},
    )
    game.phase = Phase.PRECOMBAT_MAIN
    return game, p1, p2, regrower, dead


def _setup(dead):
    game = legacy_game()
    p1, p2 = game.players
    game.active_player_index = 0
    regrower = ElvishRegrower(owner=p1, controller=p1)
    set_board_state(game, 0, hand=[regrower], graveyard=[dead], mana=_MANA)
    game.phase = Phase.PRECOMBAT_MAIN
    return game, p1, p2, regrower, dead


class TestElvishRegrowerETB:

    def test_target_no_longer_permanent_card_does_nothing(self):
        """Resolution-time revalidation (rule 608.2b): the ETB re-checks the
        FULL predicate, not merely graveyard membership. If the chosen card
        ceases to be a *permanent* card before resolution, it is not returned —
        the Regrower still enters, but the graveyard card stays put.

        No card makes a graveyard card stop being a permanent card, so this
        test still changes the card directly."""
        game, p1, _p2, regrower, dead = _setup(Land(name="Fallen Forest"))
        _cast_no_resolve(game, 0, regrower, [dead], zone=Zone.GRAVEYARD)
        # The chosen card stops being a permanent card while the spell resolves.
        dead.card_types = {CardType.INSTANT}
        resolve_top_of_stack(game)
        assert game.get_graveyard(p1).contains(dead)  # not returned
        assert not game.get_hand(p1).contains(dead)
        assert game.get_battlefield(p1).contains(regrower)  # creature entered
