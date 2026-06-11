"""Tests for SOS 38 — Banishing Betrayal."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_38.card_impl import BanishingBetrayal
from benchmarks.sos.workspace.engine.card import Artifact, CardImpl, Creature, Enchantment, Instant
from benchmarks.sos.workspace.engine.card import Land
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestBanishingBetrayalProperties:
    """Static card data should match the SOS 38 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(BanishingBetrayal(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = BanishingBetrayal(owner=None)
        assert card.name == "Banishing Betrayal"
        assert card.mana_cost == ManaCost.parse("{1}{U}")


class TestBanishingBetrayalTargeting:
    """Banishing Betrayal should target a nonland permanent on the battlefield."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = BanishingBetrayal(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_nonland_permanents_and_rejects_lands_and_nonpermanents(self) -> None:
        game = create_game()
        req = BanishingBetrayal(owner=None).get_targets(game)[0]
        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        artifact = Artifact(name="Relic")
        enchantment = Enchantment(name="Lesson Plan")
        land = Land(name="Island")
        instant = Instant(name="Study Notes", mana_cost=ManaCost.parse("{U}"))

        assert req.filter_fn(creature) is True
        assert req.filter_fn(artifact) is True
        assert req.filter_fn(enchantment) is True
        assert req.filter_fn(land) is False
        assert req.filter_fn(instant) is False


class TestBanishingBetrayalResolution:
    """Banishing Betrayal should bounce the target and surveil 1."""

    def test_on_resolve_returns_the_target_to_its_owners_hand_and_may_surveil_into_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Borrowed Lecturer",
            owner=p1,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        bottom_card = CardImpl(name="Earlier Lesson", owner=p1, controller=p1)
        top_card = CardImpl(name="Latest Lesson", owner=p1, controller=p1)
        game.get_battlefield(p2).add(target)
        game.get_library(p1).add(bottom_card)
        game.get_library(p1).add(top_card)
        p1._script.append(True)

        spell = BanishingBetrayal(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert not game.get_battlefield(p2).contains(target)
        assert game.get_hand(p1).contains(target)
        assert not game.get_hand(p2).contains(target)
        assert game.get_graveyard(p1).contains(top_card)
        assert game.get_library(p1).top(1) == [bottom_card]

    def test_on_resolve_may_leave_the_surveilled_card_on_top_of_your_library(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Artifact(name="Loaned Relic", owner=p2, controller=p2)
        bottom_card = CardImpl(name="Earlier Lesson", owner=p1, controller=p1)
        top_card = CardImpl(name="Latest Lesson", owner=p1, controller=p1)
        game.get_battlefield(p2).add(target)
        game.get_library(p1).add(bottom_card)
        game.get_library(p1).add(top_card)
        p1._script.append(False)

        spell = BanishingBetrayal(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert game.get_hand(p2).contains(target)
        assert game.get_graveyard(p1).get_all() == []
        assert game.get_library(p1).get_all() == [bottom_card, top_card]
