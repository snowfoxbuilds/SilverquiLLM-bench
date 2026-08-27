"""Reference tests for FDN 107 — Mossborn Hydra.

Mossborn Hydra is a 0/0 that "enters with a +1/+1 counter on it" (rule 614.1c).
Under the enters-with-counters primitive that counter is on it *as* it enters,
so it is a 1/1 the moment it reaches the battlefield and never a transient 0/0
that dies to the 0-toughness state-based action. The Landfall trigger then
doubles the counters from a nonzero base.
"""

from __future__ import annotations

from cards.fdn.fdn_107.card_impl import MossbornHydra
from engine.card import Creature
from engine.types import CardType, ManaCost, Zone
from engine.zones import move_to_zone
from test_utils import create_game, resolve_stack, set_board_state


class TestMossbornHydraProperties:
    def test_name_and_cost(self) -> None:
        card = MossbornHydra(owner=None)
        assert card.name == "Mossborn Hydra"
        assert card.mana_cost == ManaCost.parse("{2}{G}")
        assert card.base_power == 0
        assert card.base_toughness == 0


class TestMossbornHydraEntersWithCounter:
    def test_enters_as_one_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MossbornHydra(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card])
        move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)
        # The +1/+1 counter is present as it enters — a 1/1, never a 0/0.
        assert card.plus_one_counters == 1
        assert card.power == 1
        assert card.toughness == 1

    def test_landfall_doubles_from_nonzero_base(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MossbornHydra(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card])
        move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)
        assert card.plus_one_counters == 1

        # A land entering under our control doubles the counters (1 -> 2).
        land = Creature(name="Forest-ish", card_types={CardType.LAND},
                        owner=p1, controller=p1)
        set_board_state(game, 0, hand=[land])
        move_to_zone(game, land, Zone.HAND, Zone.BATTLEFIELD)
        # The landfall trigger goes on the stack — settle it.
        resolve_stack(game)
        assert card.plus_one_counters == 2
