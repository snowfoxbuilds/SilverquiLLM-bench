"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.fdn.fdn_29.card_impl import ArcaneEpiphany
from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import cast_spell as engine_cast_spell
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Phase, TargetRequirement, Zone
from test_utils import advance_to_phase, create_game, set_board_state


def _wizard(name: str) -> Creature:
    wizard = Creature(name=name, base_power=1, base_toughness=1)
    wizard.subtypes = {"Human", "Wizard"}
    return wizard


def _cast_arcane_epiphany(game, caster_index: int) -> StackObject:
    player = game.players[caster_index]
    spell = next(card for card in game.get_hand(player).get_all() if card.name == "Arcane Epiphany")
    engine_cast_spell(game, player, spell)
    stack_obj = game.stack.peek()
    assert stack_obj is not None
    assert stack_obj.source is spell
    return stack_obj


def _cast_mana_sculpt_targeting(
    game,
    caster_index: int,
    spell: ManaSculpt,
    target: StackObject,
) -> ManaSculpt:
    player = game.players[caster_index]
    player._script.appendleft(target)
    engine_cast_spell(game, player, spell)
    return spell


def _resolve_top_of_stack(game) -> None:
    stack_obj = game.stack.pop()
    stack_obj.on_resolve(game)


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_is_instant_named_and_costed(self) -> None:
        card = ManaSculpt(owner=None)
        assert isinstance(card, Instant)
        assert card.name == "Mana Sculpt"
        assert CardType.INSTANT in card.card_types
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")


class TestManaSculptTargeting:
    """Mana Sculpt should only target spells on the stack."""

    def test_cannot_cast_without_another_spell_on_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ManaSculpt(owner=p1, controller=p1)

        assert card.can_cast(game) is False

    def test_returns_single_stack_spell_target_requirement(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = _wizard("Scholar of Storms")
        target_spell = ArcaneEpiphany(owner=p1, controller=p1)

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            battlefield=[wizard],
            hand=[target_spell],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 2},
        )

        stack_obj = _cast_arcane_epiphany(game, 0)
        requirements = ManaSculpt(owner=p2, controller=p2).get_targets(game)

        assert len(requirements) == 1
        requirement = requirements[0]
        assert isinstance(requirement, TargetRequirement)
        assert requirement.zone == Zone.STACK
        assert requirement.filter_fn(stack_obj) is True

        non_spell = StackObject(source="ability", controller=p1)
        non_spell.is_spell = False
        assert requirement.filter_fn(non_spell) is False


class TestManaSculptResolution:
    """Resolution should counter the target and schedule colorless mana correctly."""

    def test_counters_target_spell_and_moves_it_to_owners_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = ArcaneEpiphany(owner=p1, controller=p1)
        mana_sculpt = ManaSculpt(owner=p2, controller=p2)
        target_wizard = _wizard("Target Wizard")

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            battlefield=[target_wizard],
            hand=[target_spell],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 2},
        )
        set_board_state(
            game,
            1,
            hand=[mana_sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )

        target_obj = _cast_arcane_epiphany(game, 0)
        _cast_mana_sculpt_targeting(game, 1, mana_sculpt, target_obj)
        _resolve_top_of_stack(game)

        assert game.get_graveyard(p1).contains(target_spell)
        assert not p1.zones[Zone.STACK].contains(target_spell)
        assert game.stack.is_empty()

    def test_adds_colorless_at_your_postcombat_main_on_your_turn(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = ArcaneEpiphany(owner=p2, controller=p2)
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        your_wizard = _wizard("Sculptor Adept")
        target_wizard = _wizard("Epiphany Adept")

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            battlefield=[your_wizard],
            hand=[mana_sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        set_board_state(
            game,
            1,
            battlefield=[target_wizard],
            hand=[target_spell],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 2},
        )

        target_obj = _cast_arcane_epiphany(game, 1)
        _cast_mana_sculpt_targeting(game, 0, mana_sculpt, target_obj)
        _resolve_top_of_stack(game)

        assert p1.mana_pool.total() == 0

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 4

    def test_waits_for_its_controllers_next_main_phase_on_opponents_turn(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = ArcaneEpiphany(owner=p1, controller=p1)
        mana_sculpt = ManaSculpt(owner=p2, controller=p2)
        target_wizard = _wizard("Target Wizard")
        your_wizard = _wizard("Countermage")

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            battlefield=[target_wizard],
            hand=[target_spell],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 2},
        )
        set_board_state(
            game,
            1,
            battlefield=[your_wizard],
            hand=[mana_sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )

        target_obj = _cast_arcane_epiphany(game, 0)
        _cast_mana_sculpt_targeting(game, 1, mana_sculpt, target_obj)
        _resolve_top_of_stack(game)

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        assert p2.mana_pool.get(ManaType.COLORLESS) == 0

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        assert game.active_player is p2
        assert p2.mana_pool.get(ManaType.COLORLESS) == 4

    def test_wizard_check_happens_on_resolution_not_on_cast(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = ArcaneEpiphany(owner=p2, controller=p2)
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        your_wizard = _wizard("Temporary Wizard")
        target_wizard = _wizard("Target Wizard")

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            battlefield=[your_wizard],
            hand=[mana_sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        set_board_state(
            game,
            1,
            battlefield=[target_wizard],
            hand=[target_spell],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 2},
        )

        target_obj = _cast_arcane_epiphany(game, 1)
        _cast_mana_sculpt_targeting(game, 0, mana_sculpt, target_obj)
        game.get_battlefield(p1).remove(your_wizard)
        game.get_graveyard(p1).add(your_wizard)
        _resolve_top_of_stack(game)

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
