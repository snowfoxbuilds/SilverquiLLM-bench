"""Audited tests for FDN 187 — Zombify."""

from __future__ import annotations

from card_impl import Zombify
from engine.card import CardImpl, Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from tests.test_utils import create_game


class TestZombifyBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = Zombify(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = Zombify(owner=None)
        assert card.name == "Zombify"

    def test_mana_cost(self) -> None:
        card = Zombify(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{B}")


class TestZombifyResolve:
    """Return target creature card from your graveyard to the battlefield."""

    def test_returns_creature_to_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(creature)
        spell = Zombify(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        assert game.get_battlefield(p1).contains(creature) or game.get_battlefield(game.players[1]).contains(creature)

    def test_fizzles_if_no_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = Zombify(owner=p1, controller=p1)
        spell.chosen_targets = [None]
        # Should not raise
        spell.on_resolve(game)

    def test_does_not_return_noncreature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        noncreature = CardImpl(name="Spell", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        noncreature.card_types = {CardType.SORCERY}
        p1.zones[Zone.GRAVEYARD].add(noncreature)
        spell = Zombify(owner=p1, controller=p1)
        spell.chosen_targets = [noncreature]
        spell.on_resolve(game)
        assert not game.get_battlefield(p1).contains(noncreature)
