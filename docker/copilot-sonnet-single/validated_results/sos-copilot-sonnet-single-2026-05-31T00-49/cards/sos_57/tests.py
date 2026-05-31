"""Tests for sos_57 — Mana Sculpt."""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestManaSculptProperties:
    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_is_instant(self) -> None:
        card = ManaSculpt(owner=None)
        assert CardType.INSTANT in card.card_types


class TestManaSculptTargeting:
    def test_returns_one_target_requirement(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        reqs = card.get_targets(game)
        assert len(reqs) == 1

    def test_target_zone_is_stack(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        req = card.get_targets(game)[0]
        assert req.zone == Zone.STACK

    def test_target_filter_accepts_stack_object(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        req = card.get_targets(game)[0]
        p1 = game.players[0]
        dummy_source = Instant(name="Dummy", owner=p1)
        so = StackObject(source=dummy_source, controller=p1)
        assert req.filter_fn(so) is True

    def test_target_filter_rejects_non_stack_object(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        req = card.get_targets(game)[0]
        assert req.filter_fn("not a stack object") is False


class TestManaSculptCountering:
    """on_resolve counters the target spell."""

    def _push_spell_to_stack(self, game, spell, caster):
        """Helper: push a spell onto the stack as a StackObject."""
        spell.controller = caster
        spell.owner = caster
        caster.zones[Zone.STACK].add(spell)
        so = StackObject(
            source=spell,
            controller=caster,
            targets=[],
            on_resolve=lambda g: None,
        )
        game.stack.push(so)
        return so

    def test_countered_spell_removed_from_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = Instant(name="Lightning Bolt", owner=p2, controller=p2)
        so = self._push_spell_to_stack(game, target_spell, p2)
        counter = ManaSculpt(owner=p1, controller=p1)
        counter.chosen_targets = [so]
        counter.on_resolve(game)
        # Stack should be empty (the countered spell is gone).
        assert game.stack.is_empty()

    def test_countered_spell_goes_to_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = Instant(name="Lightning Bolt", owner=p2, controller=p2)
        so = self._push_spell_to_stack(game, target_spell, p2)
        counter = ManaSculpt(owner=p1, controller=p1)
        counter.chosen_targets = [so]
        counter.on_resolve(game)
        assert game.get_graveyard(p2).contains(target_spell)

    def test_no_target_is_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        counter = ManaSculpt(owner=p1, controller=p1)
        counter.chosen_targets = []
        counter.on_resolve(game)  # must not raise


class TestManaSculptWizardBonus:
    """If controller controls a Wizard, pending mana is stored."""

    def _push_spell_to_stack(self, game, spell, caster, cmc=3):
        from engine.types import ManaCost as MC
        spell.controller = caster
        spell.owner = caster
        spell.mana_cost = MC(generic=cmc)
        caster.zones[Zone.STACK].add(spell)
        so = StackObject(
            source=spell,
            controller=caster,
            targets=[],
            on_resolve=lambda g: None,
        )
        game.stack.push(so)
        return so

    def test_wizard_present_stores_pending_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = Creature(name="Sage", subtypes={"Wizard"}, base_power=2, base_toughness=2,
                          owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wizard])
        target = Instant(name="Bolt", owner=p2, controller=p2)
        so = self._push_spell_to_stack(game, target, p2, cmc=3)
        counter = ManaSculpt(owner=p1, controller=p1)
        counter.chosen_targets = [so]
        counter.on_resolve(game)
        assert getattr(p1, "_pending_mana_next_main", 0) == 3

    def test_no_wizard_no_pending_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        # No wizard on p1's battlefield.
        target = Instant(name="Bolt", owner=p2, controller=p2)
        so = self._push_spell_to_stack(game, target, p2, cmc=3)
        counter = ManaSculpt(owner=p1, controller=p1)
        counter.chosen_targets = [so]
        counter.on_resolve(game)
        assert getattr(p1, "_pending_mana_next_main", 0) == 0
