"""Reference tests for FDN 107 — Mossborn Hydra.

Mossborn Hydra is a 0/0 that "enters with a +1/+1 counter on it" (rule 614.1c).
That counter is on it *as* it enters, so it is a 1/1 the moment it reaches the
battlefield and never a transient 0/0 that dies to the 0-toughness state-based
action. The Landfall trigger then doubles the counters from a nonzero base.
Both show in play: the cast Hydra stays on the battlefield, and on the next
turn it attacks for its counters.
"""

from __future__ import annotations

from cards.fdn.fdn_107.card_impl import MossbornHydra, MossbornHydraAbility3
from cards.fdn.fdn_280.card_impl import Forest
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from silverquillm.table import Table, life, moves, off_stack, on_stack, taps


class TestMossbornHydraProperties:
    def test_name_and_cost(self) -> None:
        card = MossbornHydra(owner=None)
        assert printed_class(card) is MossbornHydra
        assert card.mana_cost == ManaCost.parse("{2}{G}")
        assert card.base_power == 0
        assert card.base_toughness == 0


def _cast_hydra(*, land=None):
    """Player 0 casts Mossborn Hydra in their first main phase; it resolves."""
    hydra = card(MossbornHydra)
    hand = [hydra] + ([land] if land else [])
    game = create_game(
        Side(hand=hand, library=[Forest], mana={ManaType.GREEN: 3}),
        Side(library=[Forest]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, hydra, then=[moves(hydra, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(hydra, Zone.BATTLEFIELD)], note="it enters as a 1/1 and survives")
    return t, hydra


def _attack_unblocked(t, hydra, damage):
    """Player 0's next turn: the Hydra attacks and is not blocked."""
    t.pass_to(Step.UPKEEP, 1)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, hydra, then=[taps(hydra)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, 20 - damage)], note=f"the Hydra deals {damage}")


class TestMossbornHydraEntersWithCounter:
    def test_enters_as_one_one(self) -> None:
        t, hydra = _cast_hydra()
        _attack_unblocked(t, hydra, 1)
        t.run()

    def test_landfall_doubles_from_nonzero_base(self) -> None:
        forest = card(Forest)
        t, hydra = _cast_hydra(land=forest)
        t.act(0, forest, then=[moves(forest, Zone.BATTLEFIELD), on_stack(MossbornHydraAbility3, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(MossbornHydraAbility3)], note="its one counter doubles to two")
        _attack_unblocked(t, hydra, 2)
        t.run()
