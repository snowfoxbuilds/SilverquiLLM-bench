"""Cross-card reference checks that do not expose other answers to candidates."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path


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
