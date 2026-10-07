"""Known-Best checks moved out of fdn_165's FDN Audited Tests: no FDN effect casts an instant or sorcery from a graveyard except by flashback,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_165.card_impl import ThinkTwice
from cards.fdn.fdn_274.card_impl import Island
from engine.card import Creature
from engine.casting import cast_spell_free
from engine.stack import resolve_top_of_stack
from engine.types import Zone
from test_interface import ManaType, Phase, Side, card, create_game
from test_utils import create_game as legacy_create_game
from test_utils import set_board_state

from table import Table, moves


def _library_card(name: str = "Blank"):
    return Creature(name=name, base_power=1, base_toughness=1)


class TestThinkTwiceFlashbackExile:
    @staticmethod
    def _flashback():
        """Player 0 casts Think Twice from the graveyard for {2}{U}; it draws
        the Island and is exiled."""
        think, drawn = card(ThinkTwice), card(Island)
        game = create_game(
            Side(graveyard=[think], library=[drawn], mana={ManaType.BLUE: 1, ManaType.COLORLESS: 2}),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, think, then=[moves(think, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(drawn, Zone.HAND), moves(think, Zone.EXILE)])
        return t

    def test_graveyard_cast_without_flashback_mode_keeps_graveyard(self) -> None:
        """Flashback is an explicit cast mode, never inferred: Think Twice
        free-cast from the graveyard WITHOUT selecting flashback still draws
        but returns to the graveyard — no silent exile."""
        game = legacy_create_game()
        p1 = game.players[0]
        card = ThinkTwice(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[card])
        game.get_library(p1).add(_library_card())

        cast_spell_free(game, p1, card, Zone.GRAVEYARD)
        resolve_top_of_stack(game)

        assert game.get_graveyard(p1).contains(card)
        assert not game.get_exile(p1).contains(card)
