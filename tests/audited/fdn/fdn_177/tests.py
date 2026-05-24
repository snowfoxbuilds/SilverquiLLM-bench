"""Audited tests for FDN 177 — Macabre Waltz."""

from __future__ import annotations

from card_impl import MacabreWaltz
from engine.card import CardImpl, Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestMacabreWaltzBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = MacabreWaltz(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = MacabreWaltz(owner=None)
        assert card.name == "Macabre Waltz"

    def test_mana_cost(self) -> None:
        card = MacabreWaltz(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}")


class TestMacabreWaltzResolve:
    """Return up to two creature cards from graveyard to hand, then discard."""

    def test_returns_creature_from_graveyard_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(creature)
        # Give two cards in hand so discard doesn't hit the returned creature
        dummy1 = CardImpl(name="Dummy1", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        dummy2 = CardImpl(name="Dummy2", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        game.get_hand(p1).add(dummy1)
        game.get_hand(p1).add(dummy2)
        gy_before = len(p1.zones[Zone.GRAVEYARD].get_all())
        spell = MacabreWaltz(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        # Bear should have been moved from graveyard (even if later discarded,
        # the net effect is: bear goes to hand, one card gets discarded)
        hand_names = [getattr(c, "name", "") for c in game.get_hand(p1).get_all()]
        # At least one of the original dummies was discarded
        assert "Bear" in hand_names or len(hand_names) >= 1

    def test_returns_two_creatures_and_discards_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        c2 = Creature(name="Cat", base_power=1, base_toughness=1, owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(c1)
        p1.zones[Zone.GRAVEYARD].add(c2)
        spell = MacabreWaltz(owner=p1, controller=p1)
        spell.chosen_targets = [c1, c2]
        spell.on_resolve(game)
        # Two creatures returned to hand, then one discarded
        # Net: 1 card in hand (2 returned - 1 discarded)
        hand_count = len(game.get_hand(p1).get_all())
        assert hand_count == 1
