"""Known-Best checks moved out of fdn_188's FDN Audited Tests: no FDN effect turns a creature into a noncreature at instant speed,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_188.card_impl import Abrade, AbradeAbility2
from engine.card import Creature, printed_class
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from engine.stack import resolve_top_of_stack
from engine.types import CardType, ManaType, Phase, Zone
from test_utils import Intent, set_board_state
from test_utils import scenario_game as legacy_create_game


def _cast_modal_no_resolve(game, idx, card, mode, target):
    """Cast modal *card* (choosing *mode_name* + *target*) but leave it on the
    stack, so a test can mutate the target and resolve manually to exercise
    resolution-time target revalidation."""
    player = game.players[idx]
    inst = game.refs.instance_id(target, Zone.BATTLEFIELD.value)
    player.start_intent(
        "cast",
        Intent(
            pattern=GameRef(card=frozenset({("printed", printed_class(card))})),
            preferences=(Decision.mode(printed=mode), Decision.obj(instance=inst)),
        ),
    )
    try:
        engine_cast_spell(game, player, card)
    finally:
        player.end_intent("cast")


def _prime(game):
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN


class TestAbradeDamageMode:

    def test_damage_mode_target_no_longer_creature_does_nothing(self):
        """Resolution-time revalidation (rule 608.2b): the damage mode re-checks
        that its target is still a creature on the battlefield. If the target
        stops being a creature before Abrade resolves, no damage is dealt."""
        game = legacy_create_game()
        p1, p2 = game.players
        abrade = Abrade(owner=p1, controller=p1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[abrade], mana={ManaType.RED: 2})
        set_board_state(game, 1, battlefield=[bear])
        _prime(game)
        _cast_modal_no_resolve(game, 0, abrade, AbradeAbility2, bear)
        # The target stops being a creature while Abrade is on the stack (still a
        # permanent — now an artifact — so it stays on the battlefield).
        bear.card_types = {CardType.ARTIFACT}
        resolve_top_of_stack(game)
        assert game.get_battlefield(p2).contains(bear)  # survives
        assert getattr(bear, "damage_marked", 0) == 0  # no damage dealt
