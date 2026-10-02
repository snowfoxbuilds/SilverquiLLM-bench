"""Cross-card reference checks that do not expose other answers to candidates."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1] / "benchmarks/fra-hard/data/test_oracle_workspace"


def run_oracle(program):
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(program)], cwd=WORKSPACE,
        env={**os.environ, "PYTHONPATH": str(WORKSPACE)}, capture_output=True, text=True,
        timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_uldaros_remaining_budget_excludes_glamdring_adventure():
    workspace = Path(__file__).resolve().parents[1] / "benchmarks/fra-hard/data/test_oracle_workspace"
    program = textwrap.dedent("""
        import importlib.util
        from pathlib import Path
        from engine.card import Creature
        from engine.decisions import Decision
        from engine.types import ManaCost, ManaType, Zone
        from test_utils import behavioral_game, cast_card, prefer

        def load(relative, name):
            spec = importlib.util.spec_from_file_location(name, Path(relative))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

        Uldaros = load('cards/fra/fra_159/card_impl.py', 'uldaros').UldarosTheorix
        Glamdring = load('cards/hob/hob_174/card_impl.py', 'glamdring').GlamdringFoehammer
        game = behavioral_game()
        player = game.players[0]
        expensive = Creature(name='Spend four', mana_cost=ManaCost(generic=4),
                             base_power=3, base_toughness=3, owner=player)
        equipment = Glamdring(owner=player)
        player.zones[Zone.GRAVEYARD].add(expensive)
        player.zones[Zone.GRAVEYARD].add(equipment)
        prefer(player, Decision.obj(name='Spend four'),
               Decision.obj(name='Glamdring, Foe-hammer'), Decision.yes())
        player.mana_pool.add(ManaType.COLORLESS, 3)
        player.mana_pool.add(ManaType.BLUE, 1)
        player.mana_pool.add(ManaType.BLACK, 2)
        cast_card(game, player, Uldaros())
        battlefield = game.get_battlefield(player).get_all()
        copies = [card for card in battlefield if getattr(card, 'is_token', False)]
        assert {card.name for card in copies} == {'Spend four', 'Glamdring, Foe-hammer'}
        assert sum(card.mana_cost.cmc for card in copies) == 6
        assert len(game.get_library(player).get_all()) == 40
        assert player.zones[Zone.EXILE].contains(expensive)
        assert player.zones[Zone.EXILE].contains(equipment)
    """)
    result = subprocess.run(
        [sys.executable, "-c", program], cwd=workspace,
        env={**os.environ, "PYTHONPATH": str(workspace)}, capture_output=True, text=True,
        timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("destination", ["GRAVEYARD", "HAND"])
def test_bilbo_adventure_departure_uses_the_cast_face(destination):
    run_oracle(f"""
        from cards.hob.hob_33.card_impl import BilboThiefintheNight
        from cards.hob.hob_174.card_impl import GlamdringFoehammer
        from engine.casting import CastingError, cast_spell
        from engine.combat import declare_attackers_step
        from engine.decisions import Decision
        from engine.stack import move_spell_off_stack, resolve_top_of_stack
        from engine.types import ManaType, Phase, Step, Zone
        from test_utils import behavioral_game, enter_permanent, object_preference, prefer

        game = behavioral_game()
        player = game.players[0]
        bilbo = enter_permanent(game, player, BilboThiefintheNight())
        bilbo.summoning_sick = False
        sword = GlamdringFoehammer(owner=player)
        player.zones[Zone.GRAVEYARD].add(sword)
        player.mana_pool.add(ManaType.COLORLESS, 2)
        player.mana_pool.add(ManaType.BLUE, 1)
        prefer(player, object_preference(game, sword), Decision.yes())
        game.phase, game.step = Phase.COMBAT, Step.DECLARE_ATTACKERS
        declare_attackers_step(game, [bilbo])
        resolve_top_of_stack(game)
        pending = game.stack.peek()
        assert pending.source is sword and sword.name == 'Gleam of Death'
        assert player.mana_pool.total() == 0
        move_spell_off_stack(game, pending, Zone.{destination})
        expected = Zone.EXILE if {destination!r} == 'GRAVEYARD' else Zone.HAND
        assert player.zones[expected].contains(sword)
        assert sword.name == 'Glamdring, Foe-hammer'
        if expected == Zone.EXILE:
            game.phase, game.step = Phase.PRECOMBAT_MAIN, None
            player.mana_pool.add(ManaType.COLORLESS, 2)
            prefer(player, Decision.no())
            try:
                cast_spell(game, player, sword)
            except CastingError:
                pass
            else:
                raise AssertionError('A countered Adventure must not grant permission')
    """)
