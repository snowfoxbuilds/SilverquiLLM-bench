"""Reference test for FDN 159 — Mocking Sprite.

Exercises the cost-reduction primitive: "Instant and sorcery spells you cast
cost {1} less to cast" is now a real reduction sourced from a battlefield
permanent (``spell_cost_reduction``), consulted by ``get_cost_reduction``'s
battlefield sweep — not the historical dead marker.
"""

from __future__ import annotations

from cards.fdn.fdn_159.card_impl import MockingSprite
from engine.card import Creature, Instant
from engine.casting import get_cost_reduction
from engine.types import Keyword, ManaCost
from test_utils import create_game, set_board_state


class TestMockingSpriteProperties:
    def test_name_and_cost(self) -> None:
        card = MockingSprite(owner=None)
        assert card.name == "Mocking Sprite"
        assert card.mana_cost == ManaCost.parse("{2}{U}")
        assert (card.base_power, card.base_toughness) == (2, 1)

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in MockingSprite(owner=None).keywords


class TestMockingSpriteCostReduction:
    def test_reduces_own_controllers_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sprite = MockingSprite(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[sprite])

        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{2}{R}"), owner=p1, controller=p1)
        assert sprite.spell_cost_reduction(game, bolt, p1) == 1
        # Consulted by the battlefield sweep in get_cost_reduction.
        assert get_cost_reduction(game, bolt, p1) == 1

    def test_does_not_reduce_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sprite = MockingSprite(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[sprite])

        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{1}{G}"),
                        base_power=2, base_toughness=2, owner=p1, controller=p1)
        assert sprite.spell_cost_reduction(game, bear, p1) == 0

    def test_does_not_reduce_opponents_spells(self) -> None:
        game = create_game()
        p1, p2 = game.players
        sprite = MockingSprite(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[sprite])

        their_bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{2}{R}"),
                             owner=p2, controller=p2)
        assert sprite.spell_cost_reduction(game, their_bolt, p2) == 0
        assert get_cost_reduction(game, their_bolt, p2) == 0
