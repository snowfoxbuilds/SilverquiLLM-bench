"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import cast_spell as engine_cast_spell
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Phase, Step, TargetRequirement, Zone
from test_utils import advance_to_phase, create_game, set_board_state


def _wizard(name: str = "Apprentice Wizard") -> Creature:
    return Creature(
        name=name,
        subtypes={"Wizard"},
        base_power=1,
        base_toughness=1,
    )


def _put_four_mana_instant_on_stack(game):
    p2 = game.players[1]
    target_spell = Instant(
        name="Volcanic Torrent",
        owner=p2,
        controller=p2,
        mana_cost=ManaCost.parse("{3}{R}"),
    )
    set_board_state(
        game,
        1,
        hand=[target_spell],
        mana={ManaType.RED: 1, ManaType.COLORLESS: 3},
    )
    engine_cast_spell(game, p2, target_spell)
    target_obj = game.stack.peek()
    assert target_obj is not None
    return target_spell, target_obj


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_name_mana_cost_rules_text_and_is_instant(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")
        assert card.rules_text == (
            "Counter target spell. If you control a Wizard, add an amount of "
            "{C} equal to the amount of mana spent to cast that spell at the "
            "beginning of your next main phase."
        )
        assert isinstance(card, Instant)
        assert CardType.INSTANT in card.card_types


class TestManaSculptTargeting:
    """Targeting should be limited to spells on the stack."""

    def test_get_targets_returns_single_spell_on_stack_requirement(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell_obj = StackObject(source=Instant(name="Shock"), controller=p2)
        ability_obj = StackObject(source="Triggered ability", controller=p1)
        ability_obj.is_spell = False
        game.stack.push(ability_obj)
        game.stack.push(spell_obj)

        reqs = ManaSculpt(owner=p1).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].description == "target spell"
        assert reqs[0].zone == Zone.STACK
        assert reqs[0].filter_fn(spell_obj) is True
        assert reqs[0].filter_fn(ability_obj) is False

    def test_can_cast_requires_another_spell_on_the_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ManaSculpt(owner=p1, controller=p1)

        assert card.can_cast(game) is False

        game.stack.push(StackObject(source=Instant(name="Shock"), controller=p2))
        assert card.can_cast(game) is True


class TestManaSculptResolution:
    """Resolution should counter the spell, then conditionally schedule mana."""

    def test_countered_spell_goes_to_its_owners_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[mana_sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        target_spell, target_obj = _put_four_mana_instant_on_stack(game)
        p1.choose_target = lambda options, requirement: target_obj

        engine_cast_spell(game, p1, mana_sculpt)
        mana_sculpt_on_stack = game.stack.pop()
        mana_sculpt_on_stack.on_resolve(game)

        assert game.stack.is_empty()
        assert game.get_graveyard(p2).contains(target_spell)
        assert game.get_graveyard(p1).contains(mana_sculpt)

    def test_controlling_a_wizard_adds_colorless_at_your_next_main_phase(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[_wizard()],
            hand=[mana_sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        target_spell, target_obj = _put_four_mana_instant_on_stack(game)
        p1.choose_target = lambda options, requirement: target_obj

        engine_cast_spell(game, p1, mana_sculpt)
        mana_sculpt_on_stack = game.stack.pop()
        mana_sculpt_on_stack.on_resolve(game)

        assert p1.mana_pool.total() == 0

        advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
        assert p1.mana_pool.total() == 0

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 4
        assert target_spell in game.get_graveyard(game.players[1]).get_all()

    def test_opponents_wizard_does_not_enable_the_delayed_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[mana_sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        set_board_state(game, 1, battlefield=[_wizard("Enemy Wizard")])
        _target_spell, target_obj = _put_four_mana_instant_on_stack(game)
        p1.choose_target = lambda options, requirement: target_obj

        engine_cast_spell(game, p1, mana_sculpt)
        mana_sculpt_on_stack = game.stack.pop()
        mana_sculpt_on_stack.on_resolve(game)
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.total() == 0
