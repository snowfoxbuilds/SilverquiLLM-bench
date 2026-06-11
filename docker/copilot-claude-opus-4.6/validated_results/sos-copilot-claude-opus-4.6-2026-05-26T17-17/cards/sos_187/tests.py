"""Tests for SOS 187 — Essenceknit Scholar.

Essenceknit Scholar is a {B}{B/G}{G} Creature — Dryad Warlock (3/1):
"When this creature enters, create a 1/1 black and green Pest creature token
with \"Whenever this token attacks, you gain 1 life.\"
At the beginning of your end step, if a creature died under your control this turn, draw a card."
"""

from __future__ import annotations

from cards.sos.sos_187.card_impl import EssenceknitScholar
from engine.card import Creature
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestEssenceknitScholarProperties:
    """Static card data should match the SOS 187 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(EssenceknitScholar(owner=None), Creature)

    def test_name(self) -> None:
        assert EssenceknitScholar(owner=None).name == "Essenceknit Scholar"

    def test_mana_cost(self) -> None:
        assert EssenceknitScholar(owner=None).mana_cost == ManaCost.parse("{B}{B/G}{G}")

    def test_power_toughness(self) -> None:
        card = EssenceknitScholar(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 1


class TestEssenceknitScholarETB:
    """When this creature enters, create a 1/1 Pest token."""

    def test_creates_pest_token_on_enter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        scholar = EssenceknitScholar(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[scholar])

        # Trigger ETB
        scholar.on_enter_battlefield(game)

        bf = game.get_battlefield(p1).get_all()
        pests = [c for c in bf if getattr(c, "name", "") == "Pest" or "Pest" in getattr(c, "name", "")]
        assert len(pests) >= 1

    def test_pest_token_is_1_1(self) -> None:
        game = create_game()
        p1 = game.players[0]
        scholar = EssenceknitScholar(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[scholar])

        scholar.on_enter_battlefield(game)

        bf = game.get_battlefield(p1).get_all()
        pests = [c for c in bf if "Pest" in getattr(c, "name", "")]
        assert len(pests) >= 1
        pest = pests[0]
        assert pest.base_power == 1
        assert pest.base_toughness == 1


class TestEssenceknitScholarEndStep:
    """At end step, if a creature died under your control this turn, draw a card."""

    def test_draws_card_if_creature_died(self) -> None:
        game = create_game()
        p1 = game.players[0]
        scholar = EssenceknitScholar(owner=p1, controller=p1)
        from engine.card import CardImpl
        lib_cards = [CardImpl(name=f"Card {i}", owner=p1) for i in range(5)]
        set_board_state(game, 0, battlefield=[scholar], hand=[], library=lib_cards)

        # Simulate a creature dying this turn
        game.creatures_died_this_turn = game.creatures_died_this_turn if hasattr(game, "creatures_died_this_turn") else []
        if hasattr(game, "creatures_died_this_turn"):
            game.creatures_died_this_turn.append((p1, "SomeCreature"))
        elif hasattr(game, "died_this_turn"):
            game.died_this_turn[p1] = True

        scholar.on_end_step(game)

        hand = game.get_hand(p1).get_all()
        assert len(hand) >= 1

    def test_no_draw_if_no_creature_died(self) -> None:
        game = create_game()
        p1 = game.players[0]
        scholar = EssenceknitScholar(owner=p1, controller=p1)
        from engine.card import CardImpl
        lib_cards = [CardImpl(name=f"Card {i}", owner=p1) for i in range(5)]
        set_board_state(game, 0, battlefield=[scholar], hand=[], library=lib_cards)

        scholar.on_end_step(game)

        hand = game.get_hand(p1).get_all()
        assert len(hand) == 0
