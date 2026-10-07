"""Reference test for FDN 231 — Reclamation Sage.

"When this creature enters, you may destroy target artifact or enchantment."
The enters ability is a triggered ability: its target is chosen as it goes
on the stack (rule 603.3d), and whether to destroy it is decided as it
resolves. Player 0 casts the Sage from three green mana in their main phase;
the scripts answer both questions, so an engine that asks only one of them
reaches the same board.
"""

from __future__ import annotations

from cards.fdn.fdn_116.card_impl import AnthemOfChampions
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_231.card_impl import ReclamationSage, ReclamationSageAbility1
from cards.fdn.fdn_249.card_impl import AdventuringGear
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import Decision, ManaType, Phase, Side, Zone, card, create_game

from silverquillm.table import Table, moves, off_stack, on_stack


def _sage_enters(theirs, target_choices, resolve_choices, *, fallback=()):
    """Player 0 casts the Sage with ``theirs`` on player 1's battlefield; its
    trigger takes its target from ``target_choices`` — or ``fallback`` once
    the engine has rejected one of them — and resolves with
    ``resolve_choices``."""
    sage = card(ReclamationSage)
    game = create_game(
        Side(hand=[sage], mana={ManaType.GREEN: 3}),
        Side(battlefield=list(theirs)),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, sage, then=[moves(sage, Zone.STACK)])
    if fallback:
        t.pass_(0, branches=[list(target_choices), list(fallback)])
    else:
        t.pass_(0, choices=target_choices)
    t.pass_(1, then=[moves(sage, Zone.BATTLEFIELD), on_stack(ReclamationSageAbility1, 0)])
    t.pass_(0, choices=resolve_choices)
    return t


class TestReclamationSageProperties:
    def test_static_data(self):
        sage = ReclamationSage(owner=None)
        assert printed_class(sage) is ReclamationSage
        assert sage.mana_cost == ManaCost.parse("{2}{G}")
        assert (sage.base_power, sage.base_toughness) == (2, 1)
        assert {"Elf", "Shaman"} <= sage.subtypes


class TestReclamationSageETB:
    def test_destroys_target_artifact(self):
        gear = card(AdventuringGear)
        t = _sage_enters([gear], [gear], [Decision.yes()])
        t.pass_(1, then=[off_stack(ReclamationSageAbility1), moves(gear, Zone.GRAVEYARD)])
        t.run()

    def test_destroys_target_enchantment(self):
        anthem = card(AnthemOfChampions)
        t = _sage_enters([anthem], [anthem], [Decision.yes()])
        t.pass_(1, then=[off_stack(ReclamationSageAbility1), moves(anthem, Zone.GRAVEYARD)])
        t.run()

    def test_option_set_only_artifacts_and_enchantments(self):
        """Player 0 would rather target Savannah Lions, but a creature is not
        an artifact or enchantment — not offered, or offered and rejected — so
        the Gear is destroyed."""
        lions, gear = card(SavannahLions), card(AdventuringGear)
        t = _sage_enters([lions, gear], [lions, gear], [Decision.yes()], fallback=[gear])
        t.pass_(1, then=[off_stack(ReclamationSageAbility1), moves(gear, Zone.GRAVEYARD)])
        t.run()

    def test_may_decline_even_with_legal_target(self):
        """Player 0 declines to destroy the only artifact: it stays."""
        gear = card(AdventuringGear)
        t = _sage_enters([gear], [], [Decision.no()])
        t.pass_(1, then=[off_stack(ReclamationSageAbility1)], note="the Gear is not destroyed")
        t.run()
