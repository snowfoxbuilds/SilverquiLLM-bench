"""Unscored public-action reproductions of excluded frozen-baseline behaviors.

Run directly with --engine baseline or --engine oracle. Exit 1 means at least
one recorded defect persists. These diagnostics are outside the audited tree;
passing them is not a requirement imposed on the frozen candidate engine.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("baseline", "oracle"), default="baseline")
    args = parser.parse_args()
    benchmark = Path(__file__).resolve().parents[2]
    workspace = benchmark / (
        "workspace" if args.engine == "baseline" else "data/test_oracle_workspace"
    )
    sys.path.insert(0, str(workspace))
    spec = importlib.util.spec_from_file_location(
        "diagnostic_helpers", benchmark / "data/test_oracle_workspace/test_utils.py"
    )
    helpers = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helpers
    spec.loader.exec_module(helpers)

    from cards.fdn.fdn_13.card_impl import FleetingFlight
    from cards.fdn.fdn_88.card_impl import GoblinNegotiation
    from cards.fdn.fdn_93.card_impl import SearslicerGoblin
    from cards.fdn.fdn_200.card_impl import GoblinSurprise
    from cards.fdn.fdn_236.card_impl import WildwoodScourge
    from cards.fdn.fdn_244.card_impl import Progenitus
    from engine.card import Creature
    from engine.combat import combat_damage_step
    from engine.decisions import Decision
    from engine.game import destroy
    from engine.types import Keyword, ManaType, Phase, Step

    results = []

    def record(card, behavior, expected, observed):
        results.append(
            {
                "card_id": card,
                "behavior": behavior,
                "expected": expected,
                "observed": observed,
                "matches": observed == expected,
            }
        )

    game = helpers.behavioral_game()
    player, opponent = game.players
    target = helpers.put_on_battlefield(
        game, opponent, Creature(name="Negotiation target", base_power=2, base_toughness=2)
    )
    spell = GoblinNegotiation(owner=player)
    helpers.fund_mana_cost(player, spell.mana_cost)
    player.mana_pool.add(ManaType.COLORLESS, 4)
    helpers.prefer(player, Decision.number(4), helpers.object_preference(game, target))
    helpers.cast_card(game, player, spell)
    record(
        "fdn_88",
        "Choose and pay X=4, then deal excess damage",
        {"target_in_graveyard": True, "goblins": 2, "mana_remaining": 0},
        {
            "target_in_graveyard": game.get_graveyard(opponent).contains(target),
            "goblins": sum(
                card.name == "Goblin" for card in game.get_battlefield(player).get_all()
            ),
            "mana_remaining": player.mana_pool.total(),
        },
    )

    game = helpers.behavioral_game()
    player = game.players[0]
    goblin = helpers.enter_permanent(game, player, SearslicerGoblin())
    goblin.summoning_sick = False
    helpers.declare_attackers(game, [goblin.name])
    helpers.declare_blockers(game, {})
    helpers.advance_game_to_phase(game, Phase.ENDING, Step.END)
    helpers.resolve_stack(game)
    record(
        "fdn_93",
        "Real attack enables raid at own end step",
        1,
        sum(card.name == "Goblin" for card in game.get_battlefield(player).get_all()),
    )

    game = helpers.behavioral_game()
    player = game.players[0]
    spell = GoblinSurprise(owner=player)
    helpers.fund_mana_cost(player, spell.mana_cost)
    helpers.prefer(player, Decision.mode("Tokens"))
    helpers.cast_card(game, player, spell)
    record(
        "fdn_200",
        "Choose token mode while casting",
        2,
        sum(card.name == "Goblin" for card in game.get_battlefield(player).get_all()),
    )

    game = helpers.behavioral_game()
    player = game.players[0]
    scourge = WildwoodScourge(owner=player)
    helpers.fund_mana_cost(player, scourge.mana_cost)
    player.mana_pool.add(ManaType.COLORLESS, 3)
    helpers.prefer(player, Decision.number(3))
    helpers.cast_card(game, player, scourge)
    record(
        "fdn_236",
        "Choose and pay X=3 before battlefield entry",
        {"on_battlefield": True, "counters": 3, "mana_remaining": 0},
        {
            "on_battlefield": game.get_battlefield(player).contains(scourge),
            "counters": scourge.counters.get("+1/+1", 0),
            "mana_remaining": player.mana_pool.total(),
        },
    )

    game = helpers.behavioral_game()
    player = game.players[0]
    progenitus = helpers.enter_permanent(game, player, Progenitus())
    destroy(game, progenitus)
    helpers.resolve_stack(game)
    record(
        "fdn_244",
        "Destroy replaces departure with library entry",
        {"on_battlefield": False, "in_library": True},
        {
            "on_battlefield": game.get_battlefield(player).contains(progenitus),
            "in_library": game.get_library(player).contains(progenitus),
        },
    )

    game = helpers.behavioral_game()
    player, opponent = game.players
    target = helpers.put_on_battlefield(
        game, player, Creature(name="Protected attacker", base_power=2, base_toughness=2)
    )
    blocker = helpers.put_on_battlefield(
        game,
        opponent,
        Creature(name="Flying blocker", base_power=4, base_toughness=4, keywords=Keyword.FLYING),
    )
    spell = FleetingFlight(owner=player)
    helpers.fund_mana_cost(player, spell.mana_cost)
    helpers.prefer(player, helpers.object_preference(game, target))
    helpers.cast_card(game, player, spell)
    target.summoning_sick = False
    helpers.declare_attackers(game, [target.name])
    helpers.declare_blockers(game, {target.name: [blocker.name]})
    combat_damage_step(game)
    helpers.resolve_stack(game)
    record(
        "fdn_13",
        "Prevent combat damage to the targeted creature",
        True,
        game.get_battlefield(player).contains(target),
    )

    print(json.dumps({"engine": args.engine, "results": results}, indent=2))
    return int(any(not item["matches"] for item in results))


if __name__ == "__main__":
    raise SystemExit(main())
