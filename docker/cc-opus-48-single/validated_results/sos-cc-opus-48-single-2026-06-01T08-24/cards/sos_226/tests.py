"""Tests for SOS 226 — Silverquill, the Disputant.

Silverquill, the Disputant is a {2}{W}{B} Legendary Creature — Elder Dragon,
4/4, with:

1. **Flying** and **Vigilance** keywords.
2. A static ability: "Each instant and sorcery spell you cast has casualty 1.
   (As you cast that spell, you may sacrifice a creature with power 1 or
   greater. When you do, copy the spell and you may choose new targets for the
   copy.)"

The Flying/Vigilance and static-data requirements are verified with hard
assertions. The casualty-granting ability is modeled by the implementation as a
public helper the casting machinery (or a test) can drive, because the base
casting pipeline (``engine/casting.py``) has no casualty hook. We assert against
that helper's observable contract:

* a casualty value of 1 is advertised,
* only the controller's instant / sorcery spells qualify (creatures and the
  opponent's spells do not),
* a creature with power >= 1 is a legal casualty sacrifice (power 0 is not),
* applying casualty sacrifices the chosen creature AND puts a copy of the spell
  on the stack (optionally with new targets).

The deep "as you cast that spell" pipeline integration is recorded in
``untestable.json`` where the engine offers no surface to drive it.

``card_impl.py`` is a stub, so every test here is expected to FAIL until the
card is implemented (TDD red phase).
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.stack import StackObject
from engine.types import (
    CardType,
    Color,
    Keyword,
    ManaCost,
    Supertype,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _instant(name: str = "Test Instant", controller: Any = None) -> Instant:
    """A vanilla instant card with a nonzero mana cost."""
    spell = Instant(name=name, mana_cost=ManaCost.parse("{1}{U}"))
    if controller is not None:
        spell.controller = controller
        spell.owner = controller
    return spell


def _sorcery(name: str = "Test Sorcery", controller: Any = None) -> Sorcery:
    """A vanilla sorcery card with a nonzero mana cost."""
    spell = Sorcery(name=name, mana_cost=ManaCost.parse("{2}{R}"))
    if controller is not None:
        spell.controller = controller
        spell.owner = controller
    return spell


def _creature(name: str = "Grizzly Bears", power: int = 2, controller: Any = None) -> Creature:
    c = Creature(name=name, base_power=power, base_toughness=2)
    c.card_types = {CardType.CREATURE}
    if controller is not None:
        c.controller = controller
        c.owner = controller
    return c


def _spell_stack_object(spell: Any, controller: Any) -> StackObject:
    """Wrap *spell* in a StackObject controlled by *controller*."""
    return StackObject(source=spell, controller=controller, targets=[])


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------


class TestSilverquillProperties:
    """Static card data should match the SOS 226 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(SilverquillTheDisputant(owner=None), Creature)

    def test_name(self) -> None:
        assert SilverquillTheDisputant(owner=None).name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        assert SilverquillTheDisputant(owner=None).mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_power_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in SilverquillTheDisputant(owner=None).supertypes

    def test_is_elder_dragon(self) -> None:
        subtypes = SilverquillTheDisputant(owner=None).subtypes
        assert {"Elder", "Dragon"} <= subtypes

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in SilverquillTheDisputant(owner=None).keywords

    def test_has_vigilance(self) -> None:
        assert Keyword.VIGILANCE in SilverquillTheDisputant(owner=None).keywords

    def test_colors_are_white_and_black(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.colors == {Color.WHITE, Color.BLACK}


# ---------------------------------------------------------------------------
# Casualty value
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyValue:
    """The granted ability is casualty 1 (sacrifice one creature, one copy)."""

    def test_casualty_value_is_one(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert getattr(card, "casualty_value", None) == 1


# ---------------------------------------------------------------------------
# Which spells get casualty (scope of "instant and sorcery spell you cast")
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyScope:
    """Casualty is granted only to the controller's instant & sorcery spells."""

    def test_your_instant_qualifies(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        spell = _instant(controller=p1)
        assert card.grants_casualty_to(game, spell) is True

    def test_your_sorcery_qualifies(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        spell = _sorcery(controller=p1)
        assert card.grants_casualty_to(game, spell) is True

    def test_your_creature_spell_does_not_qualify(self) -> None:
        """A creature spell is neither instant nor sorcery — no casualty."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        creature_spell = _creature(controller=p1)
        assert card.grants_casualty_to(game, creature_spell) is False

    def test_opponent_instant_does_not_qualify(self) -> None:
        """Only spells *you* cast get casualty; an opponent's instant doesn't."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        opp_spell = _instant(controller=p2)
        assert card.grants_casualty_to(game, opp_spell) is False


# ---------------------------------------------------------------------------
# Casualty sacrifice legality (power 1 or greater)
# ---------------------------------------------------------------------------


class TestSilverquillCasualtySacrificeLegality:
    """A creature you control with power >= 1 may be sacrificed for casualty."""

    def test_power_two_creature_is_legal_sacrifice(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.is_valid_casualty_sacrifice(_creature(power=2)) is True

    def test_power_one_creature_is_legal_sacrifice(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.is_valid_casualty_sacrifice(_creature(power=1)) is True

    def test_power_zero_creature_is_not_legal_sacrifice(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.is_valid_casualty_sacrifice(_creature(name="Wall", power=0)) is False

    def test_noncreature_is_not_legal_sacrifice(self) -> None:
        """A non-creature permanent cannot be sacrificed for casualty."""
        from engine.card import Enchantment

        card = SilverquillTheDisputant(owner=None)
        ench = Enchantment(name="Pacifism")
        assert card.is_valid_casualty_sacrifice(ench) is False


# ---------------------------------------------------------------------------
# Applying casualty: sacrifice + copy the spell
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyResolution:
    """Paying casualty sacrifices the creature and copies the spell."""

    def test_sacrifice_moves_creature_to_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _creature(name="Fodder", power=1, controller=p1)
        set_board_state(game, 0, battlefield=[card, fodder])

        spell = _instant(controller=p1)
        stack_obj = _spell_stack_object(spell, p1)
        game.stack.push(stack_obj)

        card.apply_casualty(game, stack_obj, fodder)

        # The sacrificed creature leaves the battlefield for the graveyard.
        assert not game.get_battlefield(p1).contains(fodder)
        assert game.get_graveyard(p1).contains(fodder)

    def test_copy_is_added_to_the_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _creature(name="Fodder", power=1, controller=p1)
        set_board_state(game, 0, battlefield=[card, fodder])

        spell = _instant(controller=p1)
        stack_obj = _spell_stack_object(spell, p1)
        game.stack.push(stack_obj)
        before = len(game.stack)

        card.apply_casualty(game, stack_obj, fodder)

        # Casualty 1 places exactly one copy of the spell on the stack.
        assert len(game.stack) == before + 1

    def test_copy_is_a_distinct_object_from_original(self) -> None:
        """The copy must be an independent stack object, not the original."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _creature(name="Fodder", power=1, controller=p1)
        set_board_state(game, 0, battlefield=[card, fodder])

        spell = _instant(controller=p1)
        stack_obj = _spell_stack_object(spell, p1)
        game.stack.push(stack_obj)

        card.apply_casualty(game, stack_obj, fodder)

        top = game.stack.peek()
        assert top is not stack_obj
        # The copy reproduces the same underlying spell (by name), as a
        # separate source object.
        assert top.source is not spell
        assert getattr(top.source, "name", None) == spell.name

    def test_copy_can_choose_new_targets(self) -> None:
        """"you may choose new targets for the copy" — when new targets are
        supplied, the copy carries them rather than the original's targets."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _creature(name="Fodder", power=1, controller=p1)
        original_target = _creature(name="OrigTarget", controller=p2)
        new_target = _creature(name="NewTarget", controller=p2)
        set_board_state(game, 0, battlefield=[card, fodder])
        set_board_state(game, 1, battlefield=[original_target, new_target])

        spell = _instant(controller=p1)
        stack_obj = _spell_stack_object(spell, p1)
        stack_obj.targets = [original_target]
        game.stack.push(stack_obj)

        card.apply_casualty(game, stack_obj, fodder, new_targets=[new_target])

        top = game.stack.peek()
        assert top.targets == [new_target]

    def test_copy_controlled_by_caster(self) -> None:
        """The copy is controlled by the spell's controller (you)."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _creature(name="Fodder", power=1, controller=p1)
        set_board_state(game, 0, battlefield=[card, fodder])

        spell = _sorcery(controller=p1)
        stack_obj = _spell_stack_object(spell, p1)
        game.stack.push(stack_obj)

        card.apply_casualty(game, stack_obj, fodder)

        top = game.stack.peek()
        assert top.controller is p1
