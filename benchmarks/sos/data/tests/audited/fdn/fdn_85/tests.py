"""Audited tests for FDN 85 — Electroduplicate."""

from __future__ import annotations

from card_impl import Electroduplicate
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestElectroduplicateBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = Electroduplicate(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = Electroduplicate(owner=None)
        assert card.name == "Electroduplicate"

    def test_mana_cost(self) -> None:
        card = Electroduplicate(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{R}")

    def test_has_flashback_cost(self) -> None:
        card = Electroduplicate(owner=None)
        assert card.flashback_cost == ManaCost.parse("{2}{R}{R}")


class TestElectroduplicateResolve:
    """Create a token copy with haste and end-step sacrifice."""

    def test_creates_token_on_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = Electroduplicate(owner=p1, controller=p1)
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        card.chosen_targets = [target]
        bf_before = len(list(game.get_battlefield(p1).get_all()))
        card.on_resolve(game)
        bf_after = len(list(game.get_battlefield(p1).get_all()))
        assert bf_after == bf_before + 1

    def test_token_has_same_power_toughness(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = Electroduplicate(owner=p1, controller=p1)
        target = Creature(name="Bear", base_power=3, base_toughness=4, owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        tokens = [c for c in bf if c is not target and getattr(c, "name", "") == "Bear"]
        assert len(tokens) == 1
        assert tokens[0].base_power == 3
        assert tokens[0].base_toughness == 4

    def test_token_has_haste(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = Electroduplicate(owner=p1, controller=p1)
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        tokens = [c for c in bf if c is not target]
        assert len(tokens) == 1
        kw = getattr(tokens[0], "keywords", Keyword(0)) or Keyword(0)
        assert kw & Keyword.HASTE

    def test_fizzles_when_target_is_none(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = Electroduplicate(owner=p1, controller=p1)
        card.chosen_targets = [None]
        bf_before = len(list(game.get_battlefield(p1).get_all()))
        card.on_resolve(game)
        bf_after = len(list(game.get_battlefield(p1).get_all()))
        assert bf_after == bf_before

    def test_token_copies_name(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = Electroduplicate(owner=p1, controller=p1)
        target = Creature(name="Dragon", base_power=5, base_toughness=5, owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        tokens = [c for c in bf if c is not target]
        assert tokens[0].name == "Dragon"
