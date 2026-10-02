"""Reference test for FDN 35 — Drake Hatcher (Phase F counter flow).

Drake Hatcher: "Whenever this creature deals combat damage to a player, put that
many incubation counters on it. Remove three incubation counters: Create a 2/2
blue Drake creature token with flying."

Phase F moved the incubation counters off a card-private ``incubation_counters``
attribute onto the engine counter system (``add_counter`` / ``remove_counter``,
readable via ``.counters``), so the replay executor can sync them from the GRE
``CounterAdded`` stream and the activation cost is payable from real state.
"""
from __future__ import annotations

from cards.fdn.fdn_35.card_impl import DrakeHatcher
from engine.events import DealsDamageTriggeredEvent
from engine.types import Keyword, Zone
from test_utils import activate_card_ability, create_game, resolve_stack, set_board_state


def _drake_tokens(game, player_index):
    bf = game.players[player_index].zones[Zone.BATTLEFIELD]
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False) and "Drake" in getattr(o, "subtypes", set())
    ]


class TestDrakeHatcherCounterFlow:
    def test_combat_damage_adds_engine_counters(self) -> None:
        drake = DrakeHatcher()
        game = create_game()
        p = game.players[0]
        set_board_state(game, 0, battlefield=[drake])
        drake.owner = p
        drake.controller = p
        drake.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            DealsDamageTriggeredEvent(
                source=drake, target=game.players[1], amount=3, is_combat=True
            ),
        )
        resolve_stack(game)

        # Counters live in the engine counter system, not a private attr.
        assert drake.counters.get("incubation") == 3
        assert not hasattr(drake, "incubation_counters")
        assert drake._generic_counters.get("incubation") == 3

    def test_ability_pays_three_counters_and_mints_drake(self) -> None:
        drake = DrakeHatcher()
        game = create_game()
        p = game.players[0]
        set_board_state(game, 0, battlefield=[drake])
        drake.owner = p
        drake.controller = p
        drake.register_triggers(game)

        from engine.game import add_counter
        add_counter(game, drake, "incubation", 4)
        assert drake.counters.get("incubation") == 4

        activate_card_ability(game, p, drake, 0)
        resolve_stack(game)

        tokens = _drake_tokens(game, 0)
        assert len(tokens) == 1
        assert (tokens[0].base_power, tokens[0].base_toughness) == (2, 2)
        assert Keyword.FLYING in tokens[0].keywords
        # Three counters removed; one remains.
        assert drake.counters.get("incubation") == 1

    def test_ability_unpayable_below_three_counters(self) -> None:
        from engine.abilities import AbilityError

        drake = DrakeHatcher()
        game = create_game()
        p = game.players[0]
        set_board_state(game, 0, battlefield=[drake])
        drake.owner = p
        drake.controller = p
        drake.register_triggers(game)

        from engine.game import add_counter
        add_counter(game, drake, "incubation", 2)

        try:
            activate_card_ability(game, p, drake, 0)
            raised = False
        except AbilityError:
            raised = True
        assert raised
        # No counters spent on a failed activation.
        assert drake.counters.get("incubation") == 2
        assert len(_drake_tokens(game, 0)) == 0
