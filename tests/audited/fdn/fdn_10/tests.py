"""Audited tests for FDN 10 — Divine Resilience."""

from __future__ import annotations

from card_impl import DivineResilience
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestDivineResilienceBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = DivineResilience(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = DivineResilience(owner=None)
        assert card.name == "Divine Resilience"

    def test_mana_cost(self) -> None:
        card = DivineResilience(owner=None)
        assert card.mana_cost == ManaCost.parse("{W}")

    def test_has_kicker_cost(self) -> None:
        card = DivineResilience(owner=None)
        assert card.kicker_cost == ManaCost.parse("{2}{W}")

    def test_not_kicked_by_default(self) -> None:
        card = DivineResilience(owner=None)
        assert card.kicked is False


class TestDivineResilienceResolve:
    """Grant indestructible until end of turn."""

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        c2 = Creature(name="Cat", base_power=1, base_toughness=1, owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(c1)
        bf.add(c2)
        spell = DivineResilience(owner=p1, controller=p1)
        return game, p1, c1, c2, spell

    def test_single_target_gains_indestructible(self) -> None:
        game, p1, c1, c2, spell = self._setup()
        spell.chosen_targets = [c1]
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.INDESTRUCTIBLE in c1.keywords

    def test_unkicked_only_first_target(self) -> None:
        game, p1, c1, c2, spell = self._setup()
        spell.chosen_targets = [c1, c2]
        spell.kicked = False
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.INDESTRUCTIBLE in c1.keywords
        assert Keyword.INDESTRUCTIBLE not in c2.keywords

    def test_kicked_all_targets_gain_indestructible(self) -> None:
        game, p1, c1, c2, spell = self._setup()
        spell.kicked = True
        spell.chosen_targets = [c1, c2]
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.INDESTRUCTIBLE in c1.keywords
        assert Keyword.INDESTRUCTIBLE in c2.keywords

    def test_no_targets_does_not_error(self) -> None:
        game, p1, c1, c2, spell = self._setup()
        spell.chosen_targets = []
        spell.on_resolve(game)  # Should not raise
