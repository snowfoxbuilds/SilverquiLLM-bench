"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.casting import cast_spell as engine_cast_spell
from engine.card import Instant
from engine.card import Creature
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Phase, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")


class TestManaSculptTargeting:
    """Mana Sculpt should only target spells on the stack."""

    @staticmethod
    def _put_spell_on_stack(game, controller, *, name: str = "Shock", cost: str = "{R}") -> StackObject:
        spell = Instant(
            name=name,
            mana_cost=ManaCost.parse(cost),
            owner=controller,
            controller=controller,
        )
        controller.zones[Zone.STACK].add(spell)
        stack_obj = StackObject(source=spell, controller=controller, targets=[])
        game.stack.push(stack_obj)
        return stack_obj

    def test_cannot_cast_without_a_spell_on_the_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = ManaSculpt(owner=p1, controller=p1)

        assert card.can_cast(game) is False

    def test_cannot_cast_when_only_a_nonspell_ability_is_on_the_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ability_obj = StackObject(source=object(), controller=p2, targets=[])
        ability_obj.is_spell = False
        game.stack.push(ability_obj)

        card = ManaSculpt(owner=p1, controller=p1)

        assert card.can_cast(game) is False

    def test_get_targets_returns_one_stack_spell_requirement(self) -> None:
        game = create_game()
        p1, p2 = game.players
        self._put_spell_on_stack(game, p2)

        requirements = ManaSculpt(owner=p1, controller=p1).get_targets(game)

        assert isinstance(requirements, list)
        assert len(requirements) == 1
        requirement = requirements[0]
        assert isinstance(requirement, TargetRequirement)
        assert requirement.zone == Zone.STACK
        assert "spell" in requirement.description.lower()

    def test_target_filter_accepts_spell_stack_objects_and_rejects_nonspells(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell_obj = self._put_spell_on_stack(game, p2)
        ability_obj = StackObject(source=object(), controller=p2, targets=[])
        ability_obj.is_spell = False

        requirement = ManaSculpt(owner=p1, controller=p1).get_targets(game)[0]

        assert requirement.filter_fn(spell_obj) is True
        assert requirement.filter_fn(ability_obj) is False


class TestManaSculptResolution:
    """Resolution should counter the chosen spell target."""

    @staticmethod
    def _put_spell_on_stack(game, controller, *, name: str = "Explosive Study", cost: str = "{2}{R}") -> StackObject:
        spell = Instant(
            name=name,
            mana_cost=ManaCost.parse(cost),
            owner=controller,
            controller=controller,
        )
        controller.zones[Zone.STACK].add(spell)
        stack_obj = StackObject(source=spell, controller=controller, targets=[])
        game.stack.push(stack_obj)
        return stack_obj

    def test_chosen_target_is_countered_from_stack_to_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = self._put_spell_on_stack(game, p2)
        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.on_resolve(game)

        assert game.stack.is_empty()
        assert p2.zones[Zone.STACK].contains(target.source) is False
        assert game.get_graveyard(p2).contains(target.source) is True


class TestManaSculptDelayedMana:
    """The Wizard rider should add delayed colorless mana based on mana spent."""

    @staticmethod
    def _wizard(controller) -> Creature:
        wizard = Creature(
            name="Patient Wizard",
            owner=controller,
            controller=controller,
            base_power=1,
            base_toughness=3,
        )
        wizard.card_types = {CardType.CREATURE}
        wizard.subtypes = {"Wizard"}
        return wizard

    @staticmethod
    def _cast_target_spell(game, controller, *, name: str = "Explosive Study", cost: str = "{2}{R}") -> tuple[Instant, StackObject]:
        spell = Instant(
            name=name,
            mana_cost=ManaCost.parse(cost),
            owner=controller,
            controller=controller,
        )
        mana = {ManaType.RED: ManaCost.parse(cost).cmc}
        set_board_state(
            game,
            1 if controller is game.players[1] else 0,
            hand=[spell],
            mana=mana,
        )
        engine_cast_spell(game, controller, spell)
        stack_obj = game.stack.peek()
        assert stack_obj is not None
        return spell, stack_obj

    def test_cast_target_spell_tracks_total_mana_spent_on_card_and_stack_object(self) -> None:
        game = create_game()
        p2 = game.players[1]

        spell, stack_obj = self._cast_target_spell(game, p2)

        assert spell.total_mana_spent == 3
        assert stack_obj.total_mana_spent == 3

    def test_wizard_rider_waits_for_your_next_main_phase_and_adds_matching_colorless_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = self._wizard(p1)
        set_board_state(game, 0, battlefield=[wizard])
        _, target = self._cast_target_spell(game, p2)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(
                player=p2,
                phase=Phase.PRECOMBAT_MAIN,
            ),
        )
        assert game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(
                player=p1,
                phase=Phase.PRECOMBAT_MAIN,
            ),
        )

        assert len(game.stack.objects()) == 1
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_delayed_mana_trigger_happens_only_once(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = self._wizard(p1)
        set_board_state(game, 0, battlefield=[wizard])
        _, target = self._cast_target_spell(game, p2)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(
                player=p1,
                phase=Phase.PRECOMBAT_MAIN,
            ),
        )
        first_trigger = game.stack.pop()
        first_trigger.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(
                player=p1,
                phase=Phase.POSTCOMBAT_MAIN,
            ),
        )

        assert game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_without_a_wizard_no_delayed_colorless_mana_is_created(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _, target = self._cast_target_spell(game, p2)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(
                player=p1,
                phase=Phase.PRECOMBAT_MAIN,
            ),
        )

        assert game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
