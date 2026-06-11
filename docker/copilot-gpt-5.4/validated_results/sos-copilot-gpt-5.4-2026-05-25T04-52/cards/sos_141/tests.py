"""Tests for SOS 141 — Burrog Barrage."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_141.card_impl import BurrogBarrage
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class SetupSpell(Instant):
    """Simple instant used to establish that another spell was cast this turn."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Setup Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        super().__init__(**kwargs)


class TestBurrogBarrageProperties:
    """Static card data should match the SOS 141 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(BurrogBarrage(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = BurrogBarrage(owner=None)

        assert card.name == "Burrog Barrage"
        assert card.mana_cost == ManaCost.parse("{1}{G}")


class TestBurrogBarrageTargeting:
    """Burrog Barrage should target your creature, plus up to one opposing creature."""

    def test_returns_two_battlefield_target_requirements_with_optional_second_target(self) -> None:
        game = create_game()
        reqs = BurrogBarrage(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert isinstance(reqs[0], TargetRequirement)
        assert isinstance(reqs[1], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[1].zone == Zone.BATTLEFIELD
        assert getattr(reqs[1], "min_targets", 1) == 0

    def test_target_filters_accept_your_creature_then_an_opponents_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        reqs = BurrogBarrage(owner=p1, controller=p1).get_targets(game)

        your_creature = Creature(
            name="Helpful Bear",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        opposing_creature = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        non_creature = CardImpl(name="Lecture Notes", owner=p1, controller=p1)

        assert reqs[0].filter_fn(your_creature) is True
        assert reqs[0].filter_fn(opposing_creature) is False
        assert reqs[0].filter_fn(non_creature) is False
        assert reqs[1].filter_fn(your_creature) is False
        assert reqs[1].filter_fn(opposing_creature) is True
        assert reqs[1].filter_fn(non_creature) is False


class TestBurrogBarrageResolution:
    """Burrog Barrage should conditionally boost your creature before it deals damage."""

    def test_without_another_instant_or_sorcery_cast_this_turn_it_deals_unboosted_damage(self) -> None:
        game = create_game()
        p1, p2 = game.players
        attacker = Creature(
            name="Burrog",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        blocker = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=5,
            base_toughness=5,
        )
        set_board_state(game, 0, battlefield=[attacker])
        set_board_state(game, 1, battlefield=[blocker])

        spell = BurrogBarrage(owner=p1, controller=p1)
        spell.chosen_targets = [attacker, blocker]
        spell.on_resolve(game)

        assert attacker.power == 3
        assert attacker.damage_marked == 0
        assert blocker.damage_marked == 3

    def test_after_another_instant_or_sorcery_cast_this_turn_it_gets_plus_one_power_before_dealing_damage(self) -> None:
        game = create_game()
        p1, p2 = game.players
        attacker = Creature(
            name="Burrog",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        blocker = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=6,
            base_toughness=6,
        )
        setup_spell = SetupSpell(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[attacker],
            hand=[setup_spell],
            mana={ManaType.GREEN: 1},
        )
        set_board_state(game, 1, battlefield=[blocker])

        cast_spell_paid(game, p1, setup_spell)
        resolve_top(game)

        spell = BurrogBarrage(owner=p1, controller=p1)
        spell.chosen_targets = [attacker, blocker]
        spell.on_resolve(game)

        assert attacker.power == 4
        assert blocker.damage_marked == 4

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert attacker.power == 3
