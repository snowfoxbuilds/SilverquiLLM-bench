"""Reference test for FDN 93 — Searslicer Goblin (Phase H token minter).

Raid — "At the beginning of your end step, if you attacked this turn, create a
1/1 red Goblin creature token." The engine does not currently emit
``EndStepTriggeredEvent`` on its own (the trigger is dormant in the replay
executor), so this test registers the trigger, marks that an attack happened,
and fires the end-step event through the trigger manager directly, then resolves
the stack — exercising the real registered effect. It proves the minted Goblin
carries the exact 1/1 red Goblin characteristics ``token_id_map.json`` records.
"""
from __future__ import annotations

from cards.fdn.fdn_93.card_impl import SearslicerGoblin
from engine.events import EndStepTriggeredEvent
from engine.protection import get_colors
from engine.types import Color, Zone
from test_utils import create_game, resolve_stack, set_board_state


def _goblin_tokens(game, player_index):
    bf = game.players[player_index].zones[Zone.BATTLEFIELD]
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False)
        and "Goblin" in getattr(o, "subtypes", set())
    ]


class TestSearslicerGoblinMint:
    def test_raid_end_step_mints_11_red_goblin_token(self) -> None:
        goblin = SearslicerGoblin()
        game = create_game()
        set_board_state(game, 0, battlefield=[goblin])

        goblin.register_triggers(game)
        # Raid condition: the controller (active player) attacked this turn.
        game.attacked_this_turn = True
        game.trigger_manager.fire_event(
            game, EndStepTriggeredEvent(player=game.players[0])
        )
        resolve_stack(game)

        tokens = _goblin_tokens(game, 0)
        assert len(tokens) == 1
        token = tokens[0]
        assert token.subtypes == {"Goblin"}
        assert get_colors(token) == {Color.RED}
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert token.is_token is True
