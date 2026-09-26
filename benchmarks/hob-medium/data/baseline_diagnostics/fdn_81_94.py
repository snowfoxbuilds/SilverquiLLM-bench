"""Intentionally failing diagnostics for excluded frozen-baseline behaviors.

Run this file directly; exit 1 records the known baseline defects. It is not an
Audited Eval suite. Chandra's four old -4 cases injected targets and called its
effect directly. Cerberus's positive case injected a death-history flag. Those
shortcuts hid these failures. Candidate reference suites remain untouched.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

EXCLUDED_CHANDRA_CASES = (
    "test_intent_chooses_the_split",
    "test_baseline_takes_first_offered_lowest",
    "test_each_queried_target_must_get_at_least_one",
    "test_single_target_takes_all_8_without_a_query",
)
EXCLUDED_CERBERUS_SUITE = "fdn_94: no positive printed ability survives canonical play"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("baseline", "oracle"), default="baseline")
    args = parser.parse_args()
    benchmark = Path(__file__).resolve().parents[2]
    workspace = benchmark / (
        "workspace" if args.engine == "baseline" else "data/test_oracle_workspace"
    )
    sys.path.insert(0, str(workspace))
    helper_path = benchmark / "data/test_oracle_workspace/test_utils.py"
    spec = importlib.util.spec_from_file_location("diagnostic_helpers", helper_path)
    helpers = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helpers
    spec.loader.exec_module(helpers)

    from cards.fdn.fdn_81.card_impl import ChandraFlameshaper
    from cards.fdn.fdn_94.card_impl import SlumberingCerberus
    from engine.card import Creature
    from engine.decisions import Decision
    from engine.game import destroy, tap
    from engine.turn import untap_step
    from engine.types import Phase, Step

    failures = []
    game = helpers.behavioral_game()
    player, opponent = game.players
    chandra = helpers.enter_permanent(game, player, ChandraFlameshaper())
    target = helpers.put_on_battlefield(
        game, opponent, Creature(name="Target", base_power=1, base_toughness=12)
    )
    helpers.prefer(player, helpers.object_preference(game, target), Decision.number(8))
    helpers.activate_loyalty_ability(game, player, chandra, 2)
    helpers.resolve_stack(game)
    if (target.damage_marked, chandra.loyalty) != (8, 2):
        failures.append(
            f"Chandra -4: expected damage=8,loyalty=2; observed damage={target.damage_marked},loyalty={chandra.loyalty}"
        )

    game = helpers.behavioral_game()
    player = game.players[0]
    cerberus = helpers.enter_permanent(game, player, SlumberingCerberus())
    victim = helpers.put_on_battlefield(
        game, player, Creature(name="Victim", base_power=1, base_toughness=1)
    )
    tap(game, cerberus)
    destroy(game, victim)
    helpers.advance_game_to_phase(game, Phase.ENDING, Step.END)
    helpers.resolve_stack(game)
    if cerberus.is_tapped:
        failures.append(
            "Cerberus morbid: a creature died; expected untapped at end step, observed tapped"
        )
    tap(game, cerberus)
    untap_step(game)
    if not cerberus.is_tapped:
        failures.append(
            "Cerberus untap: expected to remain tapped during ordinary untap, observed untapped"
        )
    for failure in failures:
        print("KNOWN BASELINE FAILURE:", failure)
    if not failures:
        print(
            "Previously recorded baseline defects no longer reproduced; reconsider the exclusions."
        )
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
