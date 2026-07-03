"""Tests for SOS 106 — Ancestral Anger."""

from __future__ import annotations

import pytest

from cards.sos.sos_106.card_impl import AncestralAnger
from engine.card import Creature, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state, cast_spell


class TestAncestralAngerProperties:
    """Static card data should match the SOS 106 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(AncestralAnger(owner=None), Sorcery)

    def test_name(self) -> None:
        assert AncestralAnger(owner=None).name == "Ancestral Anger"

    def test_mana_cost(self) -> None:
        assert AncestralAnger(owner=None).mana_cost == ManaCost.parse("{R}")


class TestAncestralAngerTargeting:
    """Ancestral Anger targets a creature."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = AncestralAnger(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = AncestralAnger(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creature(self) -> None:
        game = create_game()
        req = AncestralAnger(owner=None).get_targets(game)[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True


class TestAncestralAngerResolution:
    """on_resolve grants trample and +X/+0 based on graveyard count, then draws."""

    def test_grants_trample(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = AncestralAnger(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)
        assert Keyword.TRAMPLE in bear.keywords

    def test_plus_x_with_no_copies_in_graveyard(self) -> None:
        """With 0 copies in graveyard, X = 1, so creature gets +1/+0."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = AncestralAnger(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)
        # X = 1 + 0 copies in graveyard = 1, so power should be 3
        assert bear.power == 3
        # Toughness unchanged
        assert bear.toughness == 2

    def test_plus_x_with_copies_in_graveyard(self) -> None:
        """With 2 copies in graveyard, X = 3, so creature gets +3/+0."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        # Put 2 copies of Ancestral Anger in the graveyard
        gy_copy1 = AncestralAnger(owner=p1)
        gy_copy2 = AncestralAnger(owner=p1)
        set_board_state(game, 0, graveyard=[gy_copy1, gy_copy2])

        spell = AncestralAnger(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)
        # X = 1 + 2 = 3
        assert bear.power == 5
        assert bear.toughness == 2

    def test_draws_a_card(self) -> None:
        """Resolving Ancestral Anger should draw a card."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        # Put a card in the library so drawing succeeds
        dummy = Creature(name="Dummy", owner=p1, base_power=1, base_toughness=1)
        game.get_library(p1).add(dummy)

        hand_before = len(game.get_hand(p1))
        spell = AncestralAnger(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)
        assert len(game.get_hand(p1)) == hand_before + 1
