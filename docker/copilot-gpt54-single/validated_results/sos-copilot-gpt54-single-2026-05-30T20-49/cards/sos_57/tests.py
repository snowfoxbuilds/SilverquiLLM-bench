"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.casting import cast_spell
from engine.card import Creature, Instant
from engine.stack import StackObject
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import advance_to_phase, create_game, set_board_state


def _wizard(owner) -> Creature:
    return Creature(
        name="Patient Wizard",
        owner=owner,
        controller=owner,
        subtypes={"Wizard"},
        base_power=1,
        base_toughness=3,
    )


def _setup_counter_scenario(*, control_wizard: bool):
    game = create_game()
    p1 = game.players[0]
    p2 = game.players[1]
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None

    mana_sculpt = ManaSculpt(owner=p1, controller=p1)
    target_spell = Instant(
        name="Volcanic Lesson",
        owner=p2,
        controller=p2,
        mana_cost=ManaCost.parse("{2}{R}"),
    )

    battlefield = [_wizard(p1)] if control_wizard else []
    set_board_state(
        game,
        0,
        battlefield=battlefield,
        hand=[mana_sculpt],
        mana={ManaType.BLUE: 3},
    )
    set_board_state(
        game,
        1,
        hand=[target_spell],
        mana={ManaType.RED: 3},
    )

    cast_spell(game, p2, target_spell)
    target_obj = game.stack.peek()
    assert target_obj is not None
    assert target_obj.source is target_spell

    p1.choose_target = lambda options, requirement: target_obj
    cast_spell(game, p1, mana_sculpt)
    mana_sculpt_obj = game.stack.pop()
    assert mana_sculpt_obj.source is mana_sculpt
    mana_sculpt_obj.on_resolve(game)

    return game, p1, p2, mana_sculpt, target_spell


class TestManaSculptProperties:
    """Static characteristics should match the card spec."""

    def test_is_blue_instant_named_mana_sculpt_with_correct_cost(self) -> None:
        card = ManaSculpt(owner=None)
        assert isinstance(card, Instant)
        assert card.name == "Mana Sculpt"
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")


class TestManaSculptCastingLegality:
    """Casting should require another spell to target."""

    def test_cannot_cast_without_a_spell_on_the_stack(self) -> None:
        game = create_game()
        assert ManaSculpt(owner=game.players[0], controller=game.players[0]).can_cast(game) is False

    def test_can_cast_when_a_spell_is_on_the_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target_obj = StackObject(
            source=Instant(name="Target Spell", owner=p2, controller=p2),
            controller=p2,
            is_spell=True,
        )
        game.stack.push(target_obj)

        assert ManaSculpt(owner=p1, controller=p1).can_cast(game) is True


class TestManaSculptTargeting:
    """Target declaration should advertise a single spell target on the stack."""

    def test_returns_one_stack_target_requirement_for_spells_only(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        requirement = ManaSculpt(owner=p1, controller=p1).get_targets(game)[0]
        spell_obj = StackObject(
            source=Instant(name="Spell", owner=p2, controller=p2),
            controller=p2,
            is_spell=True,
        )
        ability_obj = StackObject(source=object(), controller=p2, is_spell=False)

        assert len(ManaSculpt(owner=p1, controller=p1).get_targets(game)) == 1
        assert requirement.zone == Zone.STACK
        assert "target spell" in requirement.description.lower()
        assert requirement.filter_fn(spell_obj) is True
        assert requirement.filter_fn(ability_obj) is False


class TestManaSculptResolution:
    """Resolution should counter the target and conditionally delay colorless mana."""

    def test_counters_the_chosen_spell_and_moves_it_to_its_owners_graveyard(self) -> None:
        game, p1, p2, _, target_spell = _setup_counter_scenario(control_wizard=False)

        assert game.get_graveyard(p2).contains(target_spell)
        assert not game.get_hand(p2).contains(target_spell)
        assert not any(obj.source is target_spell for obj in game.stack.objects())
        assert p1.mana_pool.total() == 0

    def test_with_a_wizard_it_adds_no_mana_immediately_on_resolution(self) -> None:
        game, p1, _, _, _ = _setup_counter_scenario(control_wizard=True)

        assert p1.mana_pool.total() == 0

    def test_with_a_wizard_it_adds_colorless_equal_to_mana_spent_at_your_next_main_phase(self) -> None:
        game, p1, _, _, _ = _setup_counter_scenario(control_wizard=True)

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3
        assert p1.mana_pool.total() == 3

    def test_without_a_wizard_it_adds_no_mana_at_your_next_main_phase(self) -> None:
        game, p1, _, _, _ = _setup_counter_scenario(control_wizard=False)

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.total() == 0
