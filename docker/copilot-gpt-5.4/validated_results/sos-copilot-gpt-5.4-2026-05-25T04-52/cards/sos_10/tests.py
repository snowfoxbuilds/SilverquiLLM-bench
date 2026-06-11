"""Tests for SOS 10 — Dig Site Inventory."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_10.card_impl import DigSiteInventory
from benchmarks.sos.workspace.engine.casting import (
    CastingError,
    cast_spell as cast_spell_paid,
    cast_spell_free,
    resolve_top,
)
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import (
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    TargetRequirement,
    Zone,
)
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestDigSiteInventoryProperties:
    """Static card data should match the SOS 10 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(DigSiteInventory(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = DigSiteInventory(owner=None)
        assert card.name == "Dig Site Inventory"
        assert card.mana_cost == ManaCost.parse("{W}")


class TestDigSiteInventoryTargeting:
    """The spell should target a creature you control on the battlefield."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = DigSiteInventory(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_your_creature_and_rejects_opponents_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        req = DigSiteInventory(owner=p1, controller=p1).get_targets(game)[0]

        your_creature = Creature(
            name="My Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opponent_creature = Creature(
            name="Enemy Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        assert req.filter_fn(your_creature) is True
        assert req.filter_fn(opponent_creature) is False


class TestDigSiteInventoryResolution:
    """The spell should add a counter and grant temporary vigilance."""

    def test_puts_a_counter_on_target_and_grants_vigilance(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Helpful Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p1).add(target)

        card = DigSiteInventory(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)

        assert target.plus_one_counters == 1
        assert Keyword.VIGILANCE in target.keywords

    def test_granted_vigilance_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Temporary Sentry",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p1).add(target)

        card = DigSiteInventory(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)
        assert Keyword.VIGILANCE in target.keywords

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert Keyword.VIGILANCE not in target.keywords

    def test_graveyard_cast_uses_flashback_style_exile_on_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Catalogued Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = DigSiteInventory(owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        game.get_graveyard(p1).add(spell)
        p1._script.append(target)

        cast_spell_free(game, p1, spell, Zone.GRAVEYARD, exile_on_resolve=True)
        resolve_top(game)

        assert game.get_exile(p1).contains(spell)
        assert target.plus_one_counters == 1
        assert Keyword.VIGILANCE in target.keywords

    def test_paid_flashback_cast_from_graveyard_requires_mana_payment(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        target = Creature(
            name="Catalogued Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = DigSiteInventory(owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        game.get_graveyard(p1).add(spell)
        p1._script.append(target)

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell_paid(game, p1, spell, from_zone=Zone.GRAVEYARD)

        assert game.get_graveyard(p1).contains(spell)

    def test_paid_flashback_cast_from_graveyard_exiles_on_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        target = Creature(
            name="Catalogued Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = DigSiteInventory(owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        game.get_graveyard(p1).add(spell)
        p1.mana_pool.add(ManaType.WHITE, 1)
        p1._script.append(target)

        cast_spell_paid(game, p1, spell, from_zone=Zone.GRAVEYARD)

        assert game.stack.peek().source is spell
        assert not game.get_graveyard(p1).contains(spell)
        assert p1.mana_pool.get(ManaType.WHITE) == 0

        resolve_top(game)

        assert game.get_exile(p1).contains(spell)
        assert target.plus_one_counters == 1
        assert Keyword.VIGILANCE in target.keywords
