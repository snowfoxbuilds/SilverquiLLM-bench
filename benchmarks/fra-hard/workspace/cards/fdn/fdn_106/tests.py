"""Reference test for FDN 106 — Loot, Exuberant Explorer.

Regression guard for the ``is_tapped`` attribute fix: the ``{4}{G}{G}, {T}``
activated ability taps Loot as part of its cost by setting the engine field
``is_tapped`` (not a stray ``.tapped``), and refuses to activate while already
tapped.
"""

from __future__ import annotations

from cards.fdn.fdn_106.card_impl import LootExuberantExplorer
from engine.types import ManaCost, ManaType
from test_utils import create_game, set_board_state


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
        assert c.name == "Loot, Exuberant Explorer"
        assert c.mana_cost == ManaCost.parse("{2}{G}")
        assert (c.base_power, c.base_toughness) == (1, 4)
        assert {"Beast", "Noble"} <= c.subtypes

    def test_has_one_activated_ability(self):
        c = LootExuberantExplorer(owner=None)
        abilities = c.get_activated_abilities()
        assert len(abilities) == 1


class TestLootAbilityCost:
    def test_cost_taps_source_and_pays_mana(self):
        game, p1, loot = _setup()
        ability = loot.get_activated_abilities()[0]
        assert ability.cost(game, loot) is True
        assert loot.is_tapped is True          # {T} cost tapped it
        assert p1.mana_pool.total() == 0        # {4}{G}{G} == 6 paid

    def test_cost_rejected_when_already_tapped(self):
        game, p1, loot = _setup(tapped=True)
        ability = loot.get_activated_abilities()[0]
        assert ability.cost(game, loot) is False
        assert p1.mana_pool.total() == 6        # nothing spent
