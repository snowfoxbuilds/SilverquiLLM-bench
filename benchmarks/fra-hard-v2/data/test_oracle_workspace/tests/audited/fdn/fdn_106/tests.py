"""Reference test for FDN 106 — Loot, Exuberant Explorer.

Regression guard for the ``is_tapped`` attribute fix: the ``{4}{G}{G}, {T}``
activated ability taps Loot as part of its cost by setting the engine field
``is_tapped`` (not a stray ``.tapped``), and refuses to activate while already
tapped.
"""

from __future__ import annotations

from cards.fdn.fdn_106.card_impl import LootExuberantExplorer
from engine.types import ManaCost, ManaType
from test_utils import scenario_game as create_game
from test_utils import set_board_state
from engine.card import printed_class


def _setup(tapped=False):
    game = create_game()
    p1 = game.players[0]
    loot = LootExuberantExplorer(owner=p1, controller=p1)
    set_board_state(game, 0, battlefield=[loot], mana={ManaType.GREEN: 6})
    loot.is_tapped = tapped
    return game, p1, loot


class TestLootProperties:
    def test_static_data(self):
        c = LootExuberantExplorer(owner=None)
        assert printed_class(c) is LootExuberantExplorer
        assert c.mana_cost == ManaCost.parse("{2}{G}")
        assert (c.base_power, c.base_toughness) == (1, 4)
        assert {"Beast", "Noble"} <= c.subtypes


class TestLootAbilityCost:
    def test_cost_taps_source_and_pays_mana(self):
        from test_utils import activate_card_ability

        game, p1, loot = _setup()
        loot.summoning_sick = False
        activate_card_ability(game, p1, loot)
        assert loot.is_tapped and p1.mana_pool.total() == 0
        assert len(game.stack) == 1

    def test_cost_rejected_when_already_tapped(self):
        import pytest
        from engine.abilities import AbilityError
        from test_utils import activate_card_ability

        game, p1, loot = _setup(tapped=True)
        loot.summoning_sick = False
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, loot)
        assert p1.mana_pool.total() == 6 and game.stack.is_empty()
