"""Tests for SOS 115 — Flashback (the card)."""

from __future__ import annotations

import pytest

from cards.sos.sos_115.card_impl import Flashback
from engine.card import Instant, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestFlashbackProperties:
    """Static card data should match spec."""

    def test_is_instant(self) -> None:
        assert isinstance(Flashback(owner=None), Instant)

    def test_name(self) -> None:
        assert Flashback(owner=None).name == "Flashback"

    def test_mana_cost(self) -> None:
        assert Flashback(owner=None).mana_cost == ManaCost.parse("{R}")


class TestFlashbackTargeting:
    """Targets instant or sorcery card in your graveyard."""

    def test_target_zone_is_graveyard(self) -> None:
        game = create_game()
        reqs = Flashback(owner=None).get_targets(game)
        assert len(reqs) >= 1
        assert reqs[0].zone == Zone.GRAVEYARD

    def test_target_accepts_instant_in_graveyard(self) -> None:
        game = create_game()
        reqs = Flashback(owner=None).get_targets(game)
        target = Instant(name="Shock", owner=None)
        target.card_types = {CardType.INSTANT}
        assert reqs[0].filter_fn(target) is True

    def test_target_accepts_sorcery_in_graveyard(self) -> None:
        game = create_game()
        reqs = Flashback(owner=None).get_targets(game)
        target = Sorcery(name="Lava Axe", owner=None)
        target.card_types = {CardType.SORCERY}
        assert reqs[0].filter_fn(target) is True

    def test_target_rejects_creature_in_graveyard(self) -> None:
        from engine.card import Creature
        game = create_game()
        reqs = Flashback(owner=None).get_targets(game)
        target = Creature(name="Bear", owner=None, base_power=2, base_toughness=2)
        target.card_types = {CardType.CREATURE}
        assert reqs[0].filter_fn(target) is False


class TestFlashbackResolution:
    """Grants flashback to target card until end of turn."""

    def test_target_gains_flashback(self) -> None:
        game = create_game()
        p1 = game.players[0]

        target = Instant(name="Shock", owner=p1, controller=p1)
        target.card_types = {CardType.INSTANT}
        target.zone = Zone.GRAVEYARD
        target.mana_cost = ManaCost.parse("{R}")

        spell = Flashback(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert Keyword.FLASHBACK in target.keywords

    def test_flashback_cost_equals_mana_cost(self) -> None:
        """The flashback cost equals the target's mana cost."""
        game = create_game()
        p1 = game.players[0]

        target = Sorcery(name="Divination", owner=p1, controller=p1)
        target.card_types = {CardType.SORCERY}
        target.zone = Zone.GRAVEYARD
        target.mana_cost = ManaCost.parse("{2}{U}")

        spell = Flashback(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.flashback_cost == ManaCost.parse("{2}{U}")

    def test_flashback_granted_until_end_of_turn(self) -> None:
        """The flashback grant is temporary — until end of turn."""
        game = create_game()
        p1 = game.players[0]

        target = Instant(name="Shock", owner=p1, controller=p1)
        target.card_types = {CardType.INSTANT}
        target.zone = Zone.GRAVEYARD
        target.mana_cost = ManaCost.parse("{R}")

        spell = Flashback(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert Keyword.FLASHBACK in target.keywords

        # After end of turn cleanup, flashback should be removed
        target.end_of_turn_cleanup(game)
        assert Keyword.FLASHBACK not in target.keywords
