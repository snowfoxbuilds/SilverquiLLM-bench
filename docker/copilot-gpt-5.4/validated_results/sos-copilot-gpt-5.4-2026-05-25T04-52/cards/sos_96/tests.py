"""Tests for SOS 96 — Rabid Attack."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_96.card_impl import RabidAttack
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.game import destroy
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestRabidAttackProperties:
    """Static card data should match the SOS 96 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(RabidAttack(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = RabidAttack(owner=None)
        assert card.name == "Rabid Attack"
        assert card.mana_cost == ManaCost.parse("{1}{B}")


class TestRabidAttackTargeting:
    """Rabid Attack should target any number of creatures you control."""

    def test_returns_a_single_battlefield_target_requirement_with_any_number_support(self) -> None:
        game = create_game()
        p1 = game.players[0]
        reqs = RabidAttack(owner=p1, controller=p1).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert getattr(reqs[0], "min_targets", 1) == 0
        assert getattr(reqs[0], "max_targets", 1) >= 2
        assert getattr(reqs[0], "distinct_targets", False) is True

    def test_target_filter_accepts_your_creatures_and_rejects_opponents_and_noncreatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        req = RabidAttack(owner=p1, controller=p1).get_targets(game)[0]
        your_creature = Creature(
            name="Your Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opposing_creature = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        non_creature = CardImpl(name="Lecture Notes", owner=p1, controller=p1)

        assert req.filter_fn(your_creature) is True
        assert req.filter_fn(opposing_creature) is False
        assert req.filter_fn(non_creature) is False


class TestRabidAttackResolution:
    """Rabid Attack should boost chosen creatures and grant a death trigger."""

    def test_on_resolve_gives_each_targeted_creature_plus_one_power_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        attacker = Creature(
            name="Attacker",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        backup = Creature(
            name="Backup",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        observer = Creature(
            name="Observer",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=4,
        )
        set_board_state(game, 0, battlefield=[attacker, backup, observer])

        spell = RabidAttack(owner=p1, controller=p1)
        spell.chosen_targets = [attacker, backup]
        spell.on_resolve(game)

        assert attacker.power == 3
        assert attacker.toughness == 2
        assert backup.power == 4
        assert backup.toughness == 3
        assert observer.power == 1
        assert observer.toughness == 4

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert attacker.power == 2
        assert backup.power == 3
        assert observer.power == 1

    def test_targeted_creature_that_dies_this_turn_draws_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        doomed = Creature(
            name="Doomed Assistant",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        drawn = CardImpl(name="Replacement Lesson", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[doomed])
        game.get_library(p1).add(drawn)

        spell = RabidAttack(owner=p1, controller=p1)
        spell.chosen_targets = [doomed]
        spell.on_resolve(game)

        destroy(game, doomed)

        assert len(game.stack) == 1

        resolve_top(game)

        assert game.get_hand(p1).contains(drawn)
        assert game.get_graveyard(p1).contains(doomed)
