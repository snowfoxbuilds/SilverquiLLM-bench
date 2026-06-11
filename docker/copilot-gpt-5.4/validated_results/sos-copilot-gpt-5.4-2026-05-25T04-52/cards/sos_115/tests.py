"""Tests for SOS 115 — Flashback."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_115.card_impl import Flashback
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class PracticeSpark(Instant):
    """Simple instant that can be granted flashback temporarily."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Practice Spark")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)


class LectureNotes(Sorcery):
    """Simple sorcery that can be granted flashback temporarily."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Lecture Notes")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        super().__init__(**kwargs)


class TestFlashbackProperties:
    """Static card data should match the SOS 115 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(Flashback(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = Flashback(owner=None)
        assert card.name == "Flashback"
        assert card.mana_cost == ManaCost.parse("{R}")


class TestFlashbackTargeting:
    """Flashback should target an instant or sorcery card in your graveyard."""

    def test_returns_single_graveyard_target_requirement(self) -> None:
        game = create_game()
        reqs = Flashback(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.GRAVEYARD

    def test_target_filter_accepts_only_your_instant_or_sorcery_cards_in_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        your_instant = PracticeSpark(owner=p1, controller=p1)
        your_sorcery = LectureNotes(owner=p1, controller=p1)
        your_creature = Creature(owner=p1, controller=p1, name="Study Bear", base_power=2, base_toughness=2)
        opponent_instant = PracticeSpark(owner=p2, controller=p2)
        game.get_graveyard(p1).add(your_instant)
        game.get_graveyard(p1).add(your_sorcery)
        game.get_graveyard(p1).add(your_creature)
        game.get_graveyard(p2).add(opponent_instant)

        req = Flashback(owner=p1, controller=p1).get_targets(game)[0]

        assert req.filter_fn(your_instant) is True
        assert req.filter_fn(your_sorcery) is True
        assert req.filter_fn(your_creature) is False
        assert req.filter_fn(opponent_instant) is False


class TestFlashbackResolution:
    """Flashback should temporarily grant printed-cost graveyard casting."""

    def test_target_card_gains_flashback_equal_to_its_mana_cost_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = LectureNotes(owner=p1, controller=p1)
        game.get_graveyard(p1).add(target)

        card = Flashback(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.on_resolve(game)

        assert target.flashback_cost == target.mana_cost

    def test_granted_flashback_allows_graveyard_cast_and_exiles_on_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        target = LectureNotes(owner=p1, controller=p1)
        game.get_graveyard(p1).add(target)
        p1.mana_pool.add(ManaType.RED, 2)

        card = Flashback(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)

        cast_spell_paid(game, p1, target, from_zone=Zone.GRAVEYARD)
        assert game.stack.peek().source is target

        resolve_top(game)

        assert game.get_exile(p1).contains(target)

    def test_granted_flashback_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = LectureNotes(owner=p1, controller=p1)
        game.get_graveyard(p1).add(target)

        card = Flashback(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)
        assert target.flashback_cost == target.mana_cost

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert not hasattr(target, "flashback_cost") or target.flashback_cost is None
