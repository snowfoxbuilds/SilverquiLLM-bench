"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.casting import CastingError, cast_spell as cast_spell_to_stack, resolve_top
from engine.stack import StackObject
from engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from test_utils import create_game, set_board_state


def _wizard(name: str = "Campus Wizard") -> Creature:
    return Creature(
        name=name,
        base_power=2,
        base_toughness=2,
        subtypes={"Human", "Wizard"},
    )


def _set_precombat_main(game) -> None:
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _advance_to_postcombat_main(game) -> None:
    while (game.phase, game.step) != (Phase.POSTCOMBAT_MAIN, None):
        game.advance_phase()


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")


class TestManaSculptTargeting:
    """Mana Sculpt should only be castable when it can target a spell."""

    def test_cannot_cast_without_another_spell_on_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ManaSculpt(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        _set_precombat_main(game)

        with pytest.raises(CastingError):
            cast_spell_to_stack(game, p1, card)

    def test_targets_only_spells_on_the_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = Instant(
            name="Target Spell",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{R}"),
        )
        spell_on_stack = StackObject(source=target_spell, controller=p2)
        ability_on_stack = StackObject(source="Triggered ability", controller=p2)
        ability_on_stack.is_spell = False
        game.stack.push(spell_on_stack)

        reqs = ManaSculpt(owner=p1, controller=p1).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.STACK
        assert reqs[0].filter_fn(spell_on_stack) is True
        assert reqs[0].filter_fn(ability_on_stack) is False


class TestManaSculptResolution:
    """Resolution should counter the spell and conditionally schedule mana."""

    def test_on_resolve_counters_target_spell_into_owners_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = Instant(
            name="Opposing Spell",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{1}{R}"),
        )
        target_on_stack = StackObject(source=target_spell, controller=p2)
        game.stack.push(target_on_stack)
        p2.zones[Zone.STACK].add(target_spell)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target_on_stack]

        card.on_resolve(game)

        assert game.stack.is_empty()
        assert p2.zones[Zone.GRAVEYARD].contains(target_spell)
        assert not p2.zones[Zone.STACK].contains(target_spell)

    def test_with_wizard_adds_colorless_equal_to_countered_spell_mana_spent_at_next_main_phase(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wizard = _wizard()
        target_spell = Sorcery(name="Big Spell", mana_cost=ManaCost.parse("{2}{R}"))
        card = ManaSculpt(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[wizard],
            hand=[target_spell, card],
            mana={
                ManaType.RED: 1,
                ManaType.BLUE: 2,
                ManaType.COLORLESS: 3,
            },
        )
        _set_precombat_main(game)

        cast_spell_to_stack(game, p1, target_spell)
        target_on_stack = game.stack.peek()
        assert target_on_stack is not None

        p1._script.append(target_on_stack)
        cast_spell_to_stack(game, p1, card)
        resolve_top(game)

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(target_spell)
        assert game.get_graveyard(p1).contains(card)
        assert p1.mana_pool.total() == 0

        game.get_battlefield(p1).remove(wizard)
        game.get_graveyard(p1).add(wizard)
        _advance_to_postcombat_main(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3
        assert p1.mana_pool.total() == 3

    def test_without_wizard_does_not_add_colorless_at_next_main_phase(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target_spell = Sorcery(name="Big Spell", mana_cost=ManaCost.parse("{2}{R}"))
        card = ManaSculpt(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[target_spell, card],
            mana={
                ManaType.RED: 1,
                ManaType.BLUE: 2,
                ManaType.COLORLESS: 3,
            },
        )
        _set_precombat_main(game)

        cast_spell_to_stack(game, p1, target_spell)
        target_on_stack = game.stack.peek()
        assert target_on_stack is not None

        p1._script.append(target_on_stack)
        cast_spell_to_stack(game, p1, card)
        resolve_top(game)
        _advance_to_postcombat_main(game)

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(target_spell)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
        assert p1.mana_pool.total() == 0
