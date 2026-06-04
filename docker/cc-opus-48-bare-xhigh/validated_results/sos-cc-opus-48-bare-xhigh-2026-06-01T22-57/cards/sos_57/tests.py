"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


def _wizard(name: str = "Wiz") -> Creature:
    c = Creature(name=name, base_power=1, base_toughness=1, subtypes={"Wizard"})
    c.card_types = {CardType.CREATURE}
    return c


class TestProperties:
    def test_basics(self) -> None:
        c = ManaSculpt(owner=None)
        assert c.name == "Mana Sculpt"
        assert c.mana_cost == ManaCost.parse("{1}{U}{U}")
        assert isinstance(c, Instant)


class TestCanCast:
    def test_requires_spell_on_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        sculpt = ManaSculpt(owner=p1, controller=p1)
        # Empty stack — cannot cast.
        assert sculpt.can_cast(game) is False
        # A spell on the stack makes it castable.
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        bolt.owner = p2
        bolt.controller = p2
        game.stack.push(StackObject(source=bolt, controller=p2))
        assert sculpt.can_cast(game) is True


class TestResolve:
    def _push_target(self, game, controller, cost: str = "{R}"):
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse(cost))
        bolt.owner = controller
        bolt.controller = controller
        obj = StackObject(source=bolt, controller=controller)
        game.stack.push(obj)
        return bolt, obj

    def test_counter_no_wizard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        sculpt = ManaSculpt(owner=p1, controller=p1)
        bolt, obj = self._push_target(game, p2)
        sculpt.chosen_targets = [obj]
        sculpt.on_resolve(game)
        # Spell countered — off the stack and into its owner's graveyard.
        assert obj not in game.stack.objects()
        assert bolt in p2.zones[Zone.GRAVEYARD].get_all()
        # No Wizard → no delayed mana.
        assert p1.mana_pool.total() == 0

    def test_counter_with_wizard_schedules_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])
        sculpt = ManaSculpt(owner=p1, controller=p1)
        bolt, obj = self._push_target(game, p2, cost="{3}{R}")  # cmc 4
        sculpt.chosen_targets = [obj]
        sculpt.on_resolve(game)
        assert bolt in p2.zones[Zone.GRAVEYARD].get_all()
        # No mana yet — it is deferred to the next main phase.
        assert p1.mana_pool.total() == 0
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, precombat=True)
        )
        # The delayed-mana trigger uses a mana ability that resolves immediately.
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 4

    def test_no_target_is_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = []
        # Should not raise.
        sculpt.on_resolve(game)
        assert p1.mana_pool.total() == 0
