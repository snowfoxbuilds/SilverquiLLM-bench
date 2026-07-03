"""Tests for SOS 153 — Lumaret's Favor."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_153.card_impl import LumaretsFavor
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestLumaretsFavorProperties:
    """Static card data should match the SOS 153 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(LumaretsFavor(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = LumaretsFavor(owner=None)

        assert card.name == "Lumaret's Favor"
        assert card.mana_cost == ManaCost.parse("{1}{G}")


class TestLumaretsFavorTargeting:
    """Lumaret's Favor should target a single creature on the battlefield."""

    def test_returns_a_single_target_requirement(self) -> None:
        game = create_game()
        reqs = LumaretsFavor(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = LumaretsFavor(owner=None).get_targets(game)[0]

        assert req.zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = LumaretsFavor(owner=None).get_targets(game)[0]

        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        non_creature = Creature(name="Not a Creature")
        non_creature.card_types = set()

        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_creature) is False


class TestLumaretsFavorResolution:
    """Lumaret's Favor should grant +2/+4 until end of turn."""

    def test_no_target_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]

        LumaretsFavor(owner=p1, controller=p1).on_resolve(game)

    def test_chosen_target_gets_plus_two_plus_four_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Helpful Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[target])
        spell = LumaretsFavor(owner=p1, controller=p1)
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert target.power == 4
        assert target.toughness == 6

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert target.power == 2
        assert target.toughness == 2


class TestLumaretsFavorInfusion:
    """Lumaret's Favor should copy itself on cast if you gained life this turn."""

    def test_casting_without_life_gain_does_not_create_a_copy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Solo Target",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = LumaretsFavor(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[target],
            hand=[spell],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )
        p1._script.append(target)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell

        resolve_top(game)

        assert target.power == 4
        assert target.toughness == 6

    def test_if_you_gained_life_this_turn_casting_it_creates_a_copy_that_can_choose_a_new_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        original_target = Creature(
            name="Original Target",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        copied_target = Creature(
            name="Copied Target",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = LumaretsFavor(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[original_target, copied_target],
            hand=[spell],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )
        p1.life_gained_this_turn = 1
        p1._script.extend([original_target, True, copied_target])

        cast_spell_paid(game, p1, spell)

        stack_objects = game.stack.objects()
        assert len(stack_objects) == 2
        assert stack_objects[0].source.name == "Lumaret's Favor"
        assert stack_objects[1].source.name == "Lumaret's Favor"
        assert stack_objects[0].targets == [copied_target]
        assert stack_objects[1].targets == [original_target]

        resolve_top(game)
        resolve_top(game)

        assert original_target.power == 4
        assert original_target.toughness == 6
        assert copied_target.power == 4
        assert copied_target.toughness == 6
