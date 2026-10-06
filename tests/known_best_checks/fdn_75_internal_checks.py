"""Known-Best checks moved out of fdn_75's FDN Audited Tests: no FDN card makes a creature card in a graveyard stop being one,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_75.card_impl import VampireSoulcaller
from engine.card import Creature
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from engine.stack import resolve_top_of_stack
from engine.types import CardType, ManaType, Phase, Zone
from test_utils import Intent, set_board_state
from test_utils import scenario_game as legacy_game

_MANA = {ManaType.BLACK: 1, ManaType.COLORLESS: 4}


class TestVampireSoulcallerRevalidation:
    """Rule 608.2b: the reanimation revalidates the FULL predicate ("a creature
    card in your graveyard") at resolution, not merely graveyard presence.

    No card makes a creature card in a graveyard stop being one, so this test
    still changes the card directly."""

    def test_no_return_when_target_ceases_to_be_creature_card(self):
        game = legacy_game()
        p1 = game.players[0]
        game.active_player_index = 0
        soulcaller = VampireSoulcaller(owner=p1, controller=p1)
        dead = Creature(name="Fallen Vampire", base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[soulcaller], graveyard=[dead], mana=_MANA)
        game.phase = Phase.PRECOMBAT_MAIN
        game.priority_player_index = 0
        game.step = None
        p1.start_intent(
            "cast",
            Intent(
                pattern=GameRef(card=frozenset({("printed", VampireSoulcaller)})),
                preferences=(Decision.obj(instance=game.refs.instance_id(dead, Zone.GRAVEYARD.value)),),
            ),
        )
        try:
            engine_cast_spell(game, p1, soulcaller)
        finally:
            p1.end_intent("cast")
        # Before resolution the target stops being a creature card.
        dead.card_types = set(dead.card_types) - {CardType.CREATURE}
        while not game.stack.is_empty():
            resolve_top_of_stack(game)

        # Effect did nothing: the card stays in the graveyard, not the hand.
        assert game.get_graveyard(p1).contains(dead)
        assert not game.get_hand(p1).contains(dead)
        # The Soulcaller itself still resolved onto the battlefield.
        assert game.get_battlefield(p1).contains(soulcaller)
