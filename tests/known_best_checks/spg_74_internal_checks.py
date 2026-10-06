"""Known-Best checks moved out of spg_74's FDN Audited Tests: no FDN effect removes a creature from combat,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.spg_74.card_impl import Condemn
from engine.card import Creature, printed_class
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from engine.stack import resolve_top_of_stack
from test_interface import ManaType, Phase, Zone
from test_utils import Intent, set_board_state
from test_utils import scenario_game as legacy_create_game


class TestCondemnResolve:

    def test_target_removed_from_combat_before_resolution_does_nothing(self):
        """Resolution-time revalidation (rule 608.2b): a creature that leaves
        combat before Condemn resolves is no longer a legal 'attacking creature'
        target, so Condemn does nothing — it stays on the battlefield and its
        controller gains no life."""
        game, _p1, p2, condemn, attacker = _legacy_setup(toughness=5)
        _cast_no_resolve(game, 0, condemn, [attacker])
        # The attacker is removed from combat while Condemn is on the stack.
        attacker.is_attacking = False
        resolve_top_of_stack(game)
        assert game.get_battlefield(p2).contains(attacker)  # not bottomed
        assert not p2.zones[Zone.LIBRARY].contains(attacker)
        assert p2.life == 20  # no life gained


def _bear(p, name="Bear", toughness=2):
    return Creature(name=name, base_power=2, base_toughness=toughness, owner=p, controller=p)


def _legacy_setup(toughness=2):
    game = legacy_create_game()
    p1, p2 = game.players
    condemn = Condemn(owner=p1, controller=p1)
    attacker = _bear(p2, "Their Attacker", toughness=toughness)
    set_board_state(game, 0, hand=[condemn], mana={ManaType.WHITE: 1})
    set_board_state(game, 1, battlefield=[attacker], life=20)
    attacker.is_attacking = True
    return game, p1, p2, condemn, attacker


def _cast_no_resolve(game, player_index, card, targets):
    """Cast *card* choosing *targets* but leave it on the stack (no resolve)."""
    player = game.players[player_index]
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    prefs = tuple(
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
