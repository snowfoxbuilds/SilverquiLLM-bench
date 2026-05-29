"""Tests for Mana Sculpt (sos_57)."""

from __future__ import annotations

import pytest
from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestManaSculptProperties:
    """Static card properties."""

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)
        assert CardType.INSTANT in ManaSculpt(owner=None).card_types

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")


class TestManaSculptCastability:
    """can_cast() requires a spell on the stack."""

    def _push_spell(self, game, card):
        """Push a dummy spell stack object."""
        from engine.stack import StackObject
        sobj = StackObject(source=card, controller=game.players[0])
        game.stack.push(sobj)
        return sobj

    def test_cannot_cast_with_empty_stack(self) -> None:
        game = create_game()
        sculpt = ManaSculpt(owner=game.players[0], controller=game.players[0])
        assert sculpt.can_cast(game) is False

    def test_can_cast_when_spell_on_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt(owner=p1, controller=p1)
        target_spell = Sorcery(name="Divination", owner=p1, controller=p1)
        self._push_spell(game, target_spell)
        assert sculpt.can_cast(game) is True


class TestManaSculptTargeting:
    """get_targets() returns a spell-on-stack target."""

    def test_returns_one_target_requirement(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt(owner=p1, controller=p1)
        from engine.stack import StackObject
        sobj = StackObject(source=Sorcery(name="Test"), controller=p1)
        game.stack.push(sobj)
        reqs = sculpt.get_targets(game)
        assert len(reqs) == 1

    def test_target_filter_accepts_stack_objects(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt(owner=p1, controller=p1)
        from engine.stack import StackObject
        sobj = StackObject(source=Sorcery(name="Test"), controller=p1)
        game.stack.push(sobj)
        req = sculpt.get_targets(game)[0]
        assert req.filter_fn(sobj) is True


class TestManaSculptCounterspell:
    """on_resolve() counters the target spell."""

    def _push_spell_obj(self, game, controller, card):
        from engine.stack import StackObject
        zone = controller.zones[Zone.STACK]
        zone.add(card)
        sobj = StackObject(source=card, controller=controller)
        game.stack.push(sobj)
        return sobj

    def test_counters_target_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        sculpt = ManaSculpt(owner=p1, controller=p1)

        target_card = Sorcery(name="Divination", owner=p2, controller=p2,
                               mana_cost=ManaCost.parse("{2}{U}"))
        sobj = self._push_spell_obj(game, p2, target_card)
        sculpt.chosen_targets = [sobj]
        sculpt.on_resolve(game)

        # Spell removed from stack
        assert len(game.stack) == 0
        # Spell in graveyard
        assert target_card in p2.zones[Zone.GRAVEYARD].get_all()

    def test_no_wizard_no_mana_bonus(self) -> None:
        game = create_game()
        p1, p2 = game.players
        sculpt = ManaSculpt(owner=p1, controller=p1)

        target_card = Sorcery(name="Divination", owner=p2, controller=p2,
                               mana_cost=ManaCost.parse("{2}{U}"))
        sobj = self._push_spell_obj(game, p2, target_card)
        sculpt.chosen_targets = [sobj]

        mana_before = p1.mana_pool.total()
        sculpt.on_resolve(game)
        # No Wizard → no mana added
        assert p1.mana_pool.total() == mana_before

    def test_wizard_adds_colorless_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        sculpt = ManaSculpt(owner=p1, controller=p1)

        # Put a Wizard on p1's battlefield
        wizard = Creature(name="Teferi", base_power=2, base_toughness=2,
                          owner=p1, controller=p1)
        wizard.subtypes = {"Wizard"}
        set_board_state(game, 0, battlefield=[wizard])

        # Target spell with CMC 3
        target_card = Sorcery(name="Divination", owner=p2, controller=p2,
                               mana_cost=ManaCost.parse("{2}{U}"))
        sobj = self._push_spell_obj(game, p2, target_card)
        sculpt.chosen_targets = [sobj]

        sculpt.on_resolve(game)
        # Wizard present → add {C} equal to CMC (3)
        assert p1.mana_pool.get(ManaType.COLORLESS) >= 3
