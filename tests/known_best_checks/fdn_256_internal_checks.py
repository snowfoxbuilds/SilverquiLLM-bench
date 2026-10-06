"""Known-Best checks moved out of fdn_256's FDN Audited Tests: no FDN effect turns a creature into a land,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_256.card_impl import MeteorGolem
from engine.card import Creature, printed_class
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from engine.stack import resolve_top_of_stack
from engine.types import CardType
from test_interface import ManaType, Phase, Zone
from test_utils import Intent, set_board_state
from test_utils import create_game as legacy_create_game


class TestMeteorGolemETB:

    def test_target_becomes_land_before_resolution_not_destroyed(self):
        """Negative revalidation: the target becomes a land before the ETB
        resolves → no longer a 'nonland permanent', so it is not destroyed."""
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, _p1, p2, golem = _legacy_setup([bear])
        _cast_no_resolve(game, 0, golem, [bear])
        bear.card_types = set(bear.card_types) | {CardType.LAND}  # became a land
        resolve_top_of_stack(game)
        assert game.get_battlefield(p2).contains(bear)          # not destroyed
        assert not p2.zones[Zone.GRAVEYARD].contains(bear)


def _legacy_setup(opp_permanents):
    game = legacy_create_game()
    p1, p2 = game.players
    golem = MeteorGolem(owner=p1, controller=p1)
    set_board_state(game, 0, hand=[golem], mana={ManaType.COLORLESS: 7})
    set_board_state(game, 1, battlefield=opp_permanents)
    return game, p1, p2, golem


def _cast_no_resolve(game, player_index, card, targets):
    """Cast *card* (sorcery-speed) choosing *targets* via an Intent, WITHOUT
    resolving, so a test can change the target before the ETB resolves."""
    player = game.players[player_index]
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    prefs = tuple(
        Decision.obj(instance=game.refs.instance_id(t, Zone.BATTLEFIELD.value))
        for t in targets
    )
    player.start_intent("cast", Intent(
        pattern=GameRef(card=frozenset({("printed", printed_class(card))})),
        preferences=prefs,
    ))
    try:
        engine_cast_spell(game, player, card)
    finally:
        player.end_intent("cast")
