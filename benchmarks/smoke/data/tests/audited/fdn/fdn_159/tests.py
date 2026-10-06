"""Reference test for FDN 159 — Mocking Sprite.

Exercises the cost-reduction primitive: "Instant and sorcery spells you cast
cost {1} less to cast" is now a real reduction sourced from a battlefield
permanent (``spell_cost_reduction``), consulted by ``get_cost_reduction``'s
battlefield sweep — not the historical dead marker. The tests show it by
what a single mana can cast while Mocking Sprite is on the battlefield.
"""

from __future__ import annotations

from cards.fdn.fdn_149.card_impl import YouthfulValkyrie
from cards.fdn.fdn_159.card_impl import MockingSprite
from cards.fdn.fdn_165.card_impl import ThinkTwice
from cards.fdn.fdn_274.card_impl import Island
from engine.card import printed_class
from engine.types import Keyword, ManaCost
from test_interface import ManaType, Phase, Side, Zone, card, create_game

from silverquillm.table import Table, moves


class TestMockingSpriteProperties:
    def test_name_and_cost(self) -> None:
        card = MockingSprite(owner=None)
        assert printed_class(card) is MockingSprite
        assert card.mana_cost == ManaCost.parse("{2}{U}")
        assert (card.base_power, card.base_toughness) == (2, 1)

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in MockingSprite(owner=None).keywords


class TestMockingSpriteCostReduction:
    def test_reduces_own_controllers_instant(self) -> None:
        """Think Twice ({1}{U}) costs {U}: a pool of one {U} casts it."""
        think = card(ThinkTwice)
        drawn = card(Island)
        game = create_game(
            Side(battlefield=[MockingSprite], hand=[think], library=[drawn], mana={ManaType.BLUE: 1}),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, think, then=[moves(think, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(think, Zone.GRAVEYARD), moves(drawn, Zone.HAND)])
        t.run()

    def test_does_not_reduce_creatures(self) -> None:
        """Youthful Valkyrie ({1}{W}) still costs two: one {W} cannot cast it."""
        valkyrie = card(YouthfulValkyrie)
        game = create_game(
            Side(battlefield=[MockingSprite], hand=[valkyrie], mana={ManaType.WHITE: 1}),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act_illegal(0, valkyrie)
        t.run()

    def test_does_not_reduce_opponents_spells(self) -> None:
        """Player 1's Think Twice still costs {1}{U} while player 0 controls
        Mocking Sprite: one {U} cannot cast it."""
        think = card(ThinkTwice)
        game = create_game(
            Side(battlefield=[MockingSprite]),
            Side(hand=[think], library=[card(Island)], mana={ManaType.BLUE: 1}),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.pass_(0)
        t.act_illegal(1, think)
        t.run()
