"""Audited tests for FDN 43 — Inspiration from Beyond."""

from __future__ import annotations

from card_impl import InspirationFromBeyond
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestInspirationFromBeyondBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = InspirationFromBeyond(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = InspirationFromBeyond(owner=None)
        assert card.name == "Inspiration from Beyond"

    def test_mana_cost(self) -> None:
        card = InspirationFromBeyond(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{U}")


class TestInspirationFromBeyondResolve:
    """Mill 3, then return an instant or sorcery from graveyard to hand."""

    def test_mills_three_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InspirationFromBeyond(owner=p1, controller=p1)
        for i in range(5):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        card.on_resolve(game)
        gy_cards = list(p1.zones[Zone.GRAVEYARD].get_all())
        # 3 milled + potentially 0 returned (no instants/sorceries milled)
        assert len(gy_cards) == 3

    def test_returns_instant_from_graveyard_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InspirationFromBeyond(owner=p1, controller=p1)
        # Put an instant in graveyard before resolve
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"), owner=p1)
        p1.zones[Zone.GRAVEYARD].add(bolt)
        # Add library cards (creatures only)
        for i in range(5):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        # Script: choose the bolt
        p1._script.append(bolt)
        card.on_resolve(game)
        hand_cards = list(p1.zones[Zone.HAND].get_all())
        assert bolt in hand_cards

    def test_returns_sorcery_from_graveyard_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InspirationFromBeyond(owner=p1, controller=p1)
        sorc = Sorcery(name="Divination", mana_cost=ManaCost.parse("{2}{U}"), owner=p1)
        p1.zones[Zone.GRAVEYARD].add(sorc)
        for i in range(5):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        p1._script.append(sorc)
        card.on_resolve(game)
        hand_cards = list(p1.zones[Zone.HAND].get_all())
        assert sorc in hand_cards

    def test_no_eligible_targets_in_graveyard(self) -> None:
        """If no instant/sorcery in graveyard after mill, nothing returned."""
        game = create_game()
        p1 = game.players[0]
        card = InspirationFromBeyond(owner=p1, controller=p1)
        for i in range(5):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        card.on_resolve(game)
        hand_cards = list(p1.zones[Zone.HAND].get_all())
        assert len(hand_cards) == 0

    def test_mills_fewer_if_library_small(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InspirationFromBeyond(owner=p1, controller=p1)
        c = Creature(name="Only", base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(c)
        card.on_resolve(game)
        gy_cards = list(p1.zones[Zone.GRAVEYARD].get_all())
        assert len(gy_cards) == 1

    def test_empty_library_no_crash(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InspirationFromBeyond(owner=p1, controller=p1)
        card.on_resolve(game)  # Should not raise

    def test_milled_instant_can_be_returned(self) -> None:
        """An instant milled this resolution can be the target to return."""
        game = create_game()
        p1 = game.players[0]
        card = InspirationFromBeyond(owner=p1, controller=p1)
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"), owner=p1)
        # Put bolt on top of library (end of list)
        p1.zones[Zone.LIBRARY].add(bolt)
        # Add 2 more on top
        for i in range(2):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        p1._script.append(bolt)
        card.on_resolve(game)
        hand_cards = list(p1.zones[Zone.HAND].get_all())
        assert bolt in hand_cards
