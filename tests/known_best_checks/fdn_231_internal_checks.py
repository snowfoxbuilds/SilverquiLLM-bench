"""Known-Best checks moved out of fdn_231's FDN Audited Tests: #169: Known-Best's
Reclamation Sage models "you may" as an optional target, so with no legal target
its trigger still goes on the stack where a rules-correct engine removes it,
so they drive the engine directly and guard the Known-Best engine without being
graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_231.card_impl import ReclamationSage
from engine.card import Creature
from engine.types import ManaType
from test_utils import cast_spell, create_game, set_board_state


def test_you_may_castable_with_no_legal_target():
    game = create_game()
    p1, p2 = game.players
    sage = ReclamationSage(owner=p1, controller=p1)
    bear = Creature(name="Bear", base_power=2, base_toughness=2)
    set_board_state(game, 0, hand=[sage], mana={ManaType.GREEN: 3})
    set_board_state(game, 1, battlefield=[bear])  # no artifact/enchantment
    cast_spell(game, 0, ReclamationSage)
    assert game.get_battlefield(p1).contains(sage)
    assert game.get_battlefield(p2).contains(bear)  # nothing destroyed
