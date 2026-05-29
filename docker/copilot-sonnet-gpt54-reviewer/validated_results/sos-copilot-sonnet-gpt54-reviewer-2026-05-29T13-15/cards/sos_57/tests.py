"""Tests for sos_57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.stack import StackObject
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


def _make_wizard(name: str = "Test Wizard", owner=None) -> Creature:
    c = Creature(
        name=name, subtypes={"Wizard"}, base_power=2, base_toughness=2,
        owner=owner, controller=owner,
    )
    return c


class TestManaSculptProperties:
    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)


class TestManaSculptCounterSpell:
    """Counter target spell."""

    def _push_spell_on_stack(self, game, card, player):
        """Push a StackObject for card onto the stack."""
        stack_obj = StackObject(
            source=card,
            controller=player,
            on_resolve=lambda g: None,
        )
        game.stack.push(stack_obj)
        return stack_obj

    def test_countered_spell_leaves_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        # Put a spell on the stack
        target_card = Instant(name="Target Instant", owner=p2, controller=p2)
        target_so = self._push_spell_on_stack(game, target_card, p2)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_so]
        spell.on_resolve(game)

        # Stack should be empty now (target spell was countered)
        assert game.stack.is_empty()

    def test_countered_spell_source_goes_to_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_card = Instant(name="Target Instant", owner=p2, controller=p2)
        # Put the card in p2's stack zone to simulate it was cast
        p2.zones[Zone.STACK].add(target_card)
        target_so = StackObject(
            source=target_card, controller=p2, on_resolve=lambda g: None
        )
        game.stack.push(target_so)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_so]
        spell.on_resolve(game)

        gy = game.get_graveyard(p2)
        assert gy.contains(target_card)

    def test_no_target_is_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.on_resolve(game)  # should not raise


class TestManaSculptManaRefund:
    """If controller has a Wizard, add {C} equal to countered spell's CMC next main phase."""

    def _push_spell(self, game, card, player):
        player.zones[Zone.STACK].add(card)
        so = StackObject(source=card, controller=player, on_resolve=lambda g: None)
        game.stack.push(so)
        return so

    def test_no_wizard_no_pending_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        # p1 has no Wizards
        target = Instant(
            name="Counterable",
            mana_cost=ManaCost.parse("{3}"),
            owner=p2, controller=p2,
        )
        so = self._push_spell(game, target, p2)
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [so]
        spell.on_resolve(game)
        # No pending mana should be stored
        assert getattr(spell, "_pending_mana", 0) == 0

    def test_wizard_stores_pending_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = _make_wizard(owner=p1)
        game.get_battlefield(p1).add(wizard)

        target = Instant(
            name="Counterable",
            mana_cost=ManaCost.parse("{3}"),
            owner=p2, controller=p2,
        )
        so = self._push_spell(game, target, p2)
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [so]
        spell.on_resolve(game)
        assert spell._pending_mana == 3

    def test_wizard_registers_main_phase_trigger(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = _make_wizard(owner=p1)
        game.get_battlefield(p1).add(wizard)

        target = Instant(
            name="Counterable",
            mana_cost=ManaCost.parse("{2}{U}"),
            owner=p2, controller=p2,
        )
        so = self._push_spell(game, target, p2)
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [so]
        before = len(game.trigger_manager.get_triggers())
        spell.on_resolve(game)
        after = len(game.trigger_manager.get_triggers())
        # A trigger should have been registered for next main phase
        assert after > before

    def test_mana_added_when_main_phase_trigger_fires(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = _make_wizard(owner=p1)
        game.get_battlefield(p1).add(wizard)

        target = Instant(
            name="Counterable",
            mana_cost=ManaCost.parse("{3}"),
            owner=p2, controller=p2,
        )
        so = self._push_spell(game, target, p2)
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [so]
        spell.on_resolve(game)

        # Manually fire the main phase event
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        initial_pool = p1.mana_pool.get(__import__("engine.types", fromlist=["ManaType"]).ManaType.COLORLESS)
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, is_precombat=True),
        )
        # Resolve the trigger
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        from engine.types import ManaType
        after_pool = p1.mana_pool.get(ManaType.COLORLESS)
        assert after_pool - initial_pool == 3
