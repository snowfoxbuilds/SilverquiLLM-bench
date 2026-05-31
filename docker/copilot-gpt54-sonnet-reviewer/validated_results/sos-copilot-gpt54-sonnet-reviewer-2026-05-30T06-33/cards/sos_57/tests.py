"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import CardImpl, Creature, Instant
from engine.casting import cast_spell as engine_cast_spell
from engine.stack import StackObject
from engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from test_utils import advance_to_phase, create_game, set_board_state

ORACLE_TEXT = (
    "Counter target spell. If you control a Wizard, add an amount of {C} equal "
    "to the amount of mana spent to cast that spell at the beginning of your "
    "next main phase."
)


class DummySpell(Instant):
    """Simple instant used as a spell target for Mana Sculpt."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Test Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        super().__init__(**kwargs)


class ReducedDummySpell(Instant):
    """Spell with a cost reduction so tests can assert actual mana spent."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Reduced Test Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        super().__init__(**kwargs)

    def cost_reduction(self, game) -> int:
        return 2


def _put_spell_on_stack(game, controller, card) -> StackObject:
    card.owner = controller
    card.controller = controller
    controller.zones[Zone.STACK].add(card)
    stack_obj = StackObject(source=card, controller=controller)
    game.stack.push(stack_obj)
    return stack_obj


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_rules_text(self) -> None:
        assert ManaSculpt(owner=None).rules_text == ORACLE_TEXT


class TestManaSculptCastingAndTargeting:
    """Mana Sculpt can only target spells already on the stack."""

    def test_can_only_be_cast_if_another_spell_is_on_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ManaSculpt(owner=p1, controller=p1)

        assert card.can_cast(game) is False

        _put_spell_on_stack(game, p2, DummySpell(owner=p2, controller=p2))

        assert card.can_cast(game) is True

    def test_get_targets_returns_one_stack_spell_requirement(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _put_spell_on_stack(game, p2, DummySpell(owner=p2, controller=p2))

        reqs = ManaSculpt(owner=p1, controller=p1).get_targets(game)

        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.STACK
        assert reqs[0].description == "target spell"

    def test_target_filter_accepts_spell_stack_objects_and_rejects_nonspells(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _put_spell_on_stack(game, p2, DummySpell(owner=p2, controller=p2))
        req = ManaSculpt(owner=p1, controller=p1).get_targets(game)[0]

        spell_obj = StackObject(source=DummySpell(owner=p2, controller=p2), controller=p2)
        ability_obj = StackObject(source=CardImpl(name="Test Ability Source"), controller=p2)
        ability_obj.is_spell = False

        assert req.filter_fn(spell_obj) is True
        assert req.filter_fn(ability_obj) is False


class TestManaSculptResolution:
    """Resolution should counter the chosen spell and handle the Wizard rider timing."""

    def test_casting_in_response_targets_spell_on_stack_and_counters_it(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = DummySpell(owner=p2, controller=p2)
        target_stack_obj = _put_spell_on_stack(game, p2, target_spell)
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[mana_sculpt],
            mana={ManaType.COLORLESS: 1, ManaType.BLUE: 2},
        )
        p1._script.appendleft(target_stack_obj)

        engine_cast_spell(game, p1, mana_sculpt)
        game.stack.pop().on_resolve(game)

        assert game.get_graveyard(p1).contains(mana_sculpt)
        assert game.get_graveyard(p2).contains(target_spell)
        assert not p2.zones[Zone.STACK].contains(target_spell)
        assert game.stack.is_empty()

    def test_controlling_a_wizard_still_waits_until_next_main_phase_to_add_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = Creature(
            name="Test Wizard",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=3,
            subtypes={"Wizard"},
        )
        target_spell = DummySpell(owner=p2, controller=p2)
        target_stack_obj = _put_spell_on_stack(game, p2, target_spell)
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[wizard],
            hand=[mana_sculpt],
            mana={ManaType.COLORLESS: 4, ManaType.BLUE: 2},
        )
        p1._script.appendleft(target_stack_obj)

        engine_cast_spell(game, p1, mana_sculpt)
        game.stack.pop().on_resolve(game)

        assert game.get_graveyard(p2).contains(target_spell)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_wizard_rider_adds_colorless_equal_to_mana_actually_spent_at_next_main_phase(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = Creature(
            name="Test Wizard",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=3,
            subtypes={"Wizard"},
        )
        target_spell = ReducedDummySpell(owner=p2, controller=p2)
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        set_board_state(
            game,
            0,
            battlefield=[wizard],
            hand=[mana_sculpt],
            mana={ManaType.COLORLESS: 1, ManaType.BLUE: 2},
        )
        set_board_state(
            game,
            1,
            hand=[target_spell],
            mana={ManaType.COLORLESS: 4},
        )

        engine_cast_spell(game, p2, target_spell)
        target_stack_obj = game.stack.peek()

        assert target_spell.mana_spent_total == 2
        assert target_stack_obj is not None

        p1._script.appendleft(target_stack_obj)
        engine_cast_spell(game, p1, mana_sculpt)
        game.stack.pop().on_resolve(game)

        assert p1.mana_pool.total() == 0
        assert game.stack.is_empty()

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.total() == 0
        assert not game.stack.is_empty()

        game.stack.pop().on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 2
        assert game.stack.is_empty()

    def test_without_a_wizard_no_delayed_mana_trigger_is_created_for_the_next_main_phase(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = DummySpell(owner=p2, controller=p2)
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        set_board_state(
            game,
            0,
            hand=[mana_sculpt],
            mana={ManaType.COLORLESS: 1, ManaType.BLUE: 2},
        )
        set_board_state(
            game,
            1,
            hand=[target_spell],
            mana={ManaType.COLORLESS: 3},
        )

        engine_cast_spell(game, p2, target_spell)
        target_stack_obj = game.stack.peek()
        assert target_stack_obj is not None

        p1._script.appendleft(target_stack_obj)
        engine_cast_spell(game, p1, mana_sculpt)
        game.stack.pop().on_resolve(game)

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.total() == 0
        assert game.stack.is_empty()
