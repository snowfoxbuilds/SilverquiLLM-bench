"""Audited tests for FDN 120 — Fiendish Panda.

"When this creature dies, return another target non-Bear creature card with
mana value less than or equal to this creature's power from your graveyard to
the battlefield." Its power is read as it last existed on the battlefield
(rule 603.10a), separately for each time it died.
"""

from __future__ import annotations

from cards.fdn.fdn_3.card_impl import ArmasaurGuide
from cards.fdn.fdn_18.card_impl import InspiringPaladin
from cards.fdn.fdn_120.card_impl import FiendishPanda, FiendishPandaAbility2
from cards.fdn.fdn_175.card_impl import HerosDownfall
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_223.card_impl import GiantGrowth
from engine.types import Zone
from test_interface import ManaType, Phase, Side, card, create_game

from table import Table, moves, off_stack, on_stack


def _cast(t, spell, *, choices, then=(), returning=()):
    """Player 0 casts ``spell``, and both players pass, so it resolves; the
    Panda's dies trigger, if it goes on the stack, targets ``returning``."""
    t.act(0, spell, choices=choices, then=[moves(spell, Zone.STACK)])
    t.pass_(0, choices=list(returning))
    t.pass_(1, then=[moves(spell, Zone.GRAVEYARD), *then])


def _panda_returns(t, panda, returned):
    """The Panda's dies trigger resolves and returns ``returned``."""
    t.pass_(0, choices=[returned])
    t.pass_(1, then=[off_stack(FiendishPandaAbility2), moves(returned, Zone.BATTLEFIELD)])


class TestFiendishPandaDies:
    def test_returns_a_creature_card_with_mana_value_up_to_its_power(self) -> None:
        """The 3/2 Panda, killed by Burst Lightning, returns Inspiring Paladin
        (mana value 3)."""
        panda, bolt, paladin = card(FiendishPanda), card(BurstLightning), card(InspiringPaladin)
        game = create_game(
            Side(hand=[bolt], battlefield=[panda], graveyard=[paladin], mana={ManaType.RED: 1}),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _cast(t, bolt, choices=[panda], then=[moves(panda, Zone.GRAVEYARD), on_stack(FiendishPandaAbility2, 0)],
              returning=[paladin])
        _panda_returns(t, panda, paladin)
        t.run()

    def test_uses_its_power_as_it_died(self) -> None:
        """Giant Growth makes the Panda a 6/5 before Hero's Downfall destroys
        it: its power as it died, 6, returns Armasaur Guide (mana value 5),
        which the 3 power of the card in the graveyard would not."""
        panda, growth, downfall, guide = card(FiendishPanda), card(GiantGrowth), card(HerosDownfall), card(ArmasaurGuide)
        game = create_game(
            Side(hand=[growth, downfall], battlefield=[panda], graveyard=[guide],
                 mana={ManaType.GREEN: 1, ManaType.BLACK: 3}),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _cast(t, growth, choices=[panda])
        _cast(t, downfall, choices=[panda], then=[moves(panda, Zone.GRAVEYARD), on_stack(FiendishPandaAbility2, 0)],
              returning=[guide])
        _panda_returns(t, panda, guide)
        t.run()
