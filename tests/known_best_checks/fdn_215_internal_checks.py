"""Known-Best checks moved out of fdn_215's FDN Audited Tests: no FDN card stops a creature being a creature at instant speed,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_215.card_impl import Bushwhack, BushwhackAbility3
from engine.card import Creature, printed_class
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from engine.types import CardType, ManaType, Phase
from test_utils import Intent, resolve_stack, set_board_state
from test_utils import scenario_game as legacy_game


def _cast_bushwhack_no_resolve(game, mode, obj_instance_ids):
    """Cast Bushwhack (choosing mode + targets) WITHOUT resolving, so a test can
    change a target before the fight resolves."""
    p1 = game.players[0]
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    bw = next(c for c in game.get_hand(p1).get_all() if printed_class(c) is Bushwhack)
    prefs = (Decision.mode(printed=mode),) + tuple(Decision.obj(instance=i) for i in obj_instance_ids)
    p1.start_intent(
        "bw",
        Intent(
            pattern=GameRef(card=frozenset({("printed", Bushwhack)})),
            preferences=prefs,
        ),
    )
    try:
        engine_cast_spell(game, p1, bw)
    finally:
        p1.end_intent("bw")


class TestBushwhackFightRevalidation:
    def _setup(self):
        game = legacy_game()
        p1, p2 = game.players
        bw = Bushwhack(owner=p1, controller=p1)
        ours = Creature(name="Ours", base_power=3, base_toughness=3)
        theirs = Creature(name="Theirs", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[bw], battlefield=[ours], mana={ManaType.GREEN: 1})
        set_board_state(game, 1, battlefield=[theirs])
        return game, p1, p2, ours, theirs

    def test_target_ceases_to_be_creature_before_resolution_no_fight(self):
        """Negative revalidation: one target stops being a creature before
        resolution → illegal, so the fight does not happen."""
        game, _p1, p2, ours, theirs = self._setup()
        _cast_bushwhack_no_resolve(game, BushwhackAbility3, [ours.instance_id, theirs.instance_id])
        ours.card_types = set(ours.card_types) - {CardType.CREATURE}  # no longer a creature
        resolve_stack(game)
        assert theirs.damage_marked == 0
        assert game.get_battlefield(p2).contains(theirs)
