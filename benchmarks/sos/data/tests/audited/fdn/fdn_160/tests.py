"""Audited tests for FDN 160 — An Offer You Can't Refuse."""

from __future__ import annotations

import importlib.util
from pathlib import Path

# The conftest name-mangling turns "Can't" → "CanT" which doesn't
# match the impl class "AnOfferYouCantRefuse".  Direct-load the implementation.
_impl_path = Path(__file__).resolve().parent.parent.parent.parent.parent / "cards" / "fdn" / "fdn_160" / "card_impl.py"
_spec = importlib.util.spec_from_file_location("_fdn160_impl", _impl_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
AnOfferYouCantRefuse = _mod.AnOfferYouCantRefuse
from engine.card import CardImpl, Creature, Instant
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game


class TestAnOfferYouCantRefuseBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = AnOfferYouCantRefuse(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = AnOfferYouCantRefuse(owner=None)
        assert card.name == "An Offer You Can't Refuse"

    def test_mana_cost(self) -> None:
        card = AnOfferYouCantRefuse(owner=None)
        assert card.mana_cost == ManaCost.parse("{U}")

    def test_cmc_is_1(self) -> None:
        card = AnOfferYouCantRefuse(owner=None)
        assert card.mana_cost.cmc == 1


class TestAnOfferYouCantRefuseResolve:
    """Counter target noncreature spell. Its controller creates two Treasures."""

    def test_counters_noncreature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        from engine.stack import StackObject
        target_card = Instant(name="Lightning Bolt", mana_cost=ManaCost.parse("{R}"), owner=p2)
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)
        p2.zones[Zone.STACK].add(target_card)
        offer = AnOfferYouCantRefuse(owner=p1, controller=p1)
        offer.chosen_targets = [stack_obj]
        offer.on_resolve(game)
        # The spell should be countered (removed from stack)
        assert game.stack.is_empty()

    def test_countered_spell_goes_to_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        from engine.stack import StackObject
        target_card = Instant(name="Lightning Bolt", mana_cost=ManaCost.parse("{R}"), owner=p2)
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)
        p2.zones[Zone.STACK].add(target_card)
        offer = AnOfferYouCantRefuse(owner=p1, controller=p1)
        offer.chosen_targets = [stack_obj]
        offer.on_resolve(game)
        gy_names = [getattr(c, "name", "") for c in p2.zones[Zone.GRAVEYARD].get_all()]
        assert "Lightning Bolt" in gy_names

    def test_creates_two_treasure_tokens(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        from engine.stack import StackObject
        target_card = Instant(name="Lightning Bolt", mana_cost=ManaCost.parse("{R}"), owner=p2)
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)
        p2.zones[Zone.STACK].add(target_card)
        offer = AnOfferYouCantRefuse(owner=p1, controller=p1)
        offer.chosen_targets = [stack_obj]
        offer.on_resolve(game)
        bf = list(game.get_battlefield(p2).get_all())
        treasures = [c for c in bf if "Treasure" in getattr(c, "subtypes", set()) or getattr(c, "name", "") == "Treasure"]
        assert len(treasures) == 2

    def test_no_target_does_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        offer = AnOfferYouCantRefuse(owner=p1, controller=p1)
        offer.chosen_targets = [None]
        offer.on_resolve(game)  # Should not raise
