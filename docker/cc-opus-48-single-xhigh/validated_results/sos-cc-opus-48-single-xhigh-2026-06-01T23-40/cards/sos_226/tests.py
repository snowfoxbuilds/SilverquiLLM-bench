"""Tests for SOS 226 — Silverquill, the Disputant.

Silverquill, the Disputant is a ``{2}{W}{B}`` Legendary Creature — Elder
Dragon with power/toughness 4/4 and the following abilities:

1. Flying, vigilance (evergreen keywords).
2. "Each instant and sorcery spell you cast has casualty 1. (As you cast that
   spell, you may sacrifice a creature with power 1 or greater. When you do,
   copy the spell and you may choose new targets for the copy.)"

The engine has no native "casualty" mechanic (it is not fired automatically
from ``cast_spell``), and there is no ``SpellCastTriggeredEvent`` fired by the
casting pipeline. Following the established convention for granted abilities
that lack native engine support (see SOS 201's miracle granting and the
``copy_spell`` surface used by FDN 248 Thousand-Year Storm), we test the
*observable card contract*:

* ``CASUALTY_AMOUNT`` — the granted casualty value (1), exposed as a constant.
* ``grants_casualty_to(spell) -> int | None`` — the capability: returns the
  casualty amount for an instant/sorcery the dragon's controller casts and
  ``None`` for anything else. (Mirrors SOS 201's ``grants_miracle_to``.)
* ``offer_casualty(game, stack_obj) -> bool`` — the actual casualty offer:
  given a spell already on the stack (controlled by the dragon's controller),
  optionally sacrifice a controlled creature with power >= 1, and if so push a
  copy of the spell onto the stack (with optionally-new targets). Returns
  whether a copy was made.

These tests target the public card contract and are written before the
implementation (TDD red phase): they import the card and assert real behavior,
so they fail until ``SilverquillTheDisputant`` is implemented.
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery, Land
from engine.casting import cast_spell as engine_cast_spell
from engine.combat import _can_attack, _can_block, declare_attackers_step
from engine.stack import StackObject
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Step,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_instant(name: str = "Bolt", owner=None) -> Instant:
    return Instant(
        name=name,
        mana_cost=ManaCost.parse("{R}"),
        owner=owner,
        controller=owner,
    )


def _make_sorcery(name: str = "Divination", owner=None) -> Sorcery:
    return Sorcery(
        name=name,
        mana_cost=ManaCost.parse("{2}{U}"),
        owner=owner,
        controller=owner,
    )


def _make_creature(name: str, power: int, toughness: int, owner=None) -> Creature:
    return Creature(
        name=name,
        base_power=power,
        base_toughness=toughness,
        owner=owner,
        controller=owner,
    )


def _spell_stack_object(spell: Any, controller: Any, targets=None) -> StackObject:
    """Build a StackObject representing *spell* cast by *controller*.

    Mirrors what ``engine.casting.cast_spell`` would push for a real cast:
    ``is_spell=True`` and the on_resolve callback invokes the card's
    ``on_resolve``.
    """

    def _resolve(g):
        spell.chosen_targets = list(targets or [])
        spell.on_resolve(g)

    return StackObject(
        source=spell,
        controller=controller,
        targets=list(targets or []),
        on_resolve=_resolve,
        is_spell=True,
    )


# ---------------------------------------------------------------------------
# Static characteristics
# ---------------------------------------------------------------------------


class TestSilverquillProperties:
    """Static card data should match the SOS 226 spec."""

    def test_is_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

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

    def test_elder_dragon_subtypes(self) -> None:
        subtypes = SilverquillTheDisputant(owner=None).subtypes
        assert {"Elder", "Dragon"} <= subtypes

    def test_colors_are_white_black(self) -> None:
        """The spec lists colors W and B; cards advertise this via self.colors."""
        colors = set(getattr(SilverquillTheDisputant(owner=None), "colors", []))
        assert colors == {"W", "B"}


# ---------------------------------------------------------------------------
# Flying + vigilance keywords
# ---------------------------------------------------------------------------


class TestSilverquillKeywords:
    """Flying and vigilance keyword flags and their combat-rule consequences."""

    def test_has_flying_and_vigilance(self) -> None:
        kw = SilverquillTheDisputant(owner=None).keywords
        assert Keyword.FLYING in kw
        assert Keyword.VIGILANCE in kw

    def test_ground_creature_cannot_block_flying_silverquill(self) -> None:
        attacker = SilverquillTheDisputant(owner=None)
        ground = Creature(name="Ground Bear", base_power=2, base_toughness=2)
        ground.keywords = Keyword(0)
        ground.is_tapped = False
        assert _can_block(ground, attacker) is False

    def test_flying_creature_can_block_flying_silverquill(self) -> None:
        attacker = SilverquillTheDisputant(owner=None)
        # Guard: the contract is meaningful only if Silverquill actually flies
        # (otherwise a ground blocker could block it too).
        assert Keyword.FLYING in attacker.keywords
        flier = Creature(name="Air Bear", base_power=2, base_toughness=2)
        flier.keywords = Keyword.FLYING
        flier.is_tapped = False
        assert _can_block(flier, attacker) is True

    def test_reach_creature_can_block_flying_silverquill(self) -> None:
        attacker = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in attacker.keywords
        spider = Creature(name="Spider", base_power=1, base_toughness=4)
        spider.keywords = Keyword.REACH
        spider.is_tapped = False
        assert _can_block(spider, attacker) is True

    def test_vigilance_does_not_tap_when_attacking(self) -> None:
        """Vigilance: declaring Silverquill as an attacker leaves it untapped.

        Drives the real ``declare_attackers_step`` so the keyword's
        consequence (no tap) is observed, not just the flag.
        """
        game = create_game(scripts=([None], [None]))
        p1 = game.players[0]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        dragon.summoning_sick = False
        dragon.is_tapped = False
        set_board_state(game, 0, battlefield=[dragon])

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.COMBAT
        game.step = Step.DECLARE_ATTACKERS
        game.combat_state.in_combat = True
        # Script the active player to declare the dragon as the attacker set.
        p1._script.appendleft([dragon])

        declare_attackers_step(game)

        assert dragon.is_attacking is True
        assert dragon.is_tapped is False


# ---------------------------------------------------------------------------
# Casualty granting: "Each instant and sorcery spell you cast has casualty 1"
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyGrant:
    """The granted casualty value and the eligibility capability.

    ``CASUALTY_AMOUNT`` is the constant 1; ``grants_casualty_to(spell)``
    returns that amount for instants/sorceries and ``None`` otherwise.
    """

    def test_casualty_amount_is_one(self) -> None:
        assert SilverquillTheDisputant(owner=None).CASUALTY_AMOUNT == 1

    def test_grants_casualty_to_instant(self) -> None:
        dragon = SilverquillTheDisputant(owner=None)
        assert dragon.grants_casualty_to(_make_instant()) == 1

    def test_grants_casualty_to_sorcery(self) -> None:
        dragon = SilverquillTheDisputant(owner=None)
        assert dragon.grants_casualty_to(_make_sorcery()) == 1

    def test_does_not_grant_casualty_to_creature_spell(self) -> None:
        dragon = SilverquillTheDisputant(owner=None)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        assert dragon.grants_casualty_to(bear) is None

    def test_does_not_grant_casualty_to_land(self) -> None:
        dragon = SilverquillTheDisputant(owner=None)
        assert dragon.grants_casualty_to(Land(name="Plains")) is None


# ---------------------------------------------------------------------------
# Casualty offer: sacrifice a creature with power >= 1, then copy the spell
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyOffer:
    """``offer_casualty(game, stack_obj)`` — the heart of the card.

    When the dragon's controller casts an instant/sorcery and controls a
    creature with power >= 1, they may sacrifice such a creature; if they do,
    a copy of the spell is created (and they may choose new targets for the
    copy). These tests drive that method directly with a spell already
    represented as a StackObject.
    """

    def test_yes_sacrifices_creature_and_copies_spell(self) -> None:
        """Accept: sacrifice a power>=1 creature → a copy of the spell is on the stack."""
        # Scripts: choose_yes_no -> True (pay casualty); choose_card -> fodder;
        # choose_yes_no -> False (don't choose new targets).
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _make_creature("Fodder", 1, 1, owner=p1)
        bolt = _make_instant("Cast Bolt", owner=p1)
        set_board_state(game, 0, battlefield=[dragon, fodder])
        # Spell is already on the stack (as a cast spell would be).
        spell_so = _spell_stack_object(bolt, p1)
        game.stack.push(spell_so)

        # Script the controller's decisions.
        p1._script.append(True)    # choose_yes_no: pay casualty
        p1._script.append(fodder)  # choose_card: which creature to sacrifice
        p1._script.append(False)   # choose_yes_no: keep same targets for copy

        made_copy = dragon.offer_casualty(game, spell_so)

        assert made_copy is True
        # The fodder creature was sacrificed to its owner's graveyard.
        assert game.get_graveyard(p1).contains(fodder)
        assert not game.get_battlefield(p1).contains(fodder)
        # A copy of the spell is now on the stack: two stack objects whose
        # source is the bolt (the original) and a distinct copy of it.
        spell_objs = [so for so in game.stack.objects() if getattr(so, "is_spell", False)]
        assert len(spell_objs) == 2
        sources = [so.source for so in spell_objs]
        assert bolt in sources
        # The copy is a different object than the original spell card.
        copies = [s for s in sources if s is not bolt]
        assert len(copies) == 1
        assert copies[0].name == bolt.name

    def test_no_does_not_sacrifice_and_makes_no_copy(self) -> None:
        """Decline: no creature sacrificed, no copy made."""
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _make_creature("Fodder", 2, 2, owner=p1)
        bolt = _make_instant("Cast Bolt", owner=p1)
        set_board_state(game, 0, battlefield=[dragon, fodder])
        spell_so = _spell_stack_object(bolt, p1)
        game.stack.push(spell_so)

        p1._script.append(False)  # choose_yes_no: decline casualty

        made_copy = dragon.offer_casualty(game, spell_so)

        assert made_copy is False
        # No sacrifice happened.
        assert game.get_battlefield(p1).contains(fodder)
        assert not game.get_graveyard(p1).contains(fodder)
        # Only the original spell is on the stack.
        spell_objs = [so for so in game.stack.objects() if getattr(so, "is_spell", False)]
        assert len(spell_objs) == 1
        assert spell_objs[0].source is bolt

    def test_no_eligible_creature_makes_no_copy_and_does_not_prompt(self) -> None:
        """With no power>=1 creature to sacrifice, casualty cannot be paid.

        The empty script proves no yes/no prompt is issued (a stray prompt
        would raise ScriptExhaustedError). The dragon itself has power 4 but
        sacrificing it would be a legal choice — so to isolate "no eligible
        creature" we use a board where the only other creature has power 0 and
        we exclude the dragon by giving it 0 power is not possible; instead we
        assert the no-op contract when there is genuinely nothing with power>=1
        OTHER than... see test_power_zero_creature_is_not_eligible for the
        zero-power filter. Here we simply confirm that with no creatures at all
        besides nothing eligible, no copy is made.
        """
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        # Only a 0-power creature is available; the dragon is NOT on the
        # battlefield here, so there is no power>=1 creature to sacrifice.
        wall = _make_creature("Wall", 0, 4, owner=p1)
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        bolt = _make_instant("Cast Bolt", owner=p1)
        set_board_state(game, 0, battlefield=[wall])
        spell_so = _spell_stack_object(bolt, p1)
        game.stack.push(spell_so)

        made_copy = dragon.offer_casualty(game, spell_so)

        assert made_copy is False
        # Nothing sacrificed, only the original spell remains.
        assert game.get_battlefield(p1).contains(wall)
        spell_objs = [so for so in game.stack.objects() if getattr(so, "is_spell", False)]
        assert len(spell_objs) == 1
        # No prompt was consumed.
        assert p1.remaining_choices == 0

    def test_power_zero_creature_is_not_a_legal_sacrifice(self) -> None:
        """Only creatures with power 1 or greater may be sacrificed for casualty.

        Board has a 0/4 wall and a 1/1 fodder; the offer must restrict the
        sacrifice choice to the 1/1 (and the dragon, which is 4/4). We accept
        the offer and verify the only-power>=1 fodder is sacrificed.
        """
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        wall = _make_creature("Wall", 0, 4, owner=p1)
        fodder = _make_creature("Fodder", 1, 1, owner=p1)
        bolt = _make_instant("Cast Bolt", owner=p1)
        set_board_state(game, 0, battlefield=[dragon, wall, fodder])
        spell_so = _spell_stack_object(bolt, p1)
        game.stack.push(spell_so)

        captured: dict[str, Any] = {}
        orig_choose_card = p1.choose_card

        def _spy_choose_card(cards, description):
            captured["options"] = list(cards)
            return orig_choose_card(cards, description)

        p1.choose_card = _spy_choose_card  # type: ignore[assignment]

        p1._script.append(True)    # pay casualty
        p1._script.append(fodder)  # sacrifice the 1/1
        p1._script.append(False)   # keep same targets

        dragon.offer_casualty(game, spell_so)

        # The 0-power wall must not be among the legal sacrifice options.
        assert wall not in captured["options"]
        assert fodder in captured["options"]
        assert game.get_graveyard(p1).contains(fodder)
        assert game.get_battlefield(p1).contains(wall)

    def test_copy_can_choose_new_targets(self) -> None:
        """When the controller opts in, the copy uses newly chosen targets.

        The original spell targets opponent A; choosing new targets points the
        copy at opponent B (here, a different creature). The copy's targets
        differ from the original's.
        """
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        p2 = game.players[1]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _make_creature("Fodder", 1, 1, owner=p1)
        original_target = _make_creature("Target A", 2, 2, owner=p2)
        new_target = _make_creature("Target B", 3, 3, owner=p2)
        bolt = _make_instant("Targeted Bolt", owner=p1)
        set_board_state(game, 0, battlefield=[dragon, fodder])
        set_board_state(game, 1, battlefield=[original_target, new_target])

        spell_so = _spell_stack_object(bolt, p1, targets=[original_target])
        game.stack.push(spell_so)

        p1._script.append(True)        # pay casualty
        p1._script.append(fodder)      # sacrifice
        p1._script.append(True)        # choose new targets for the copy
        p1._script.append(new_target)  # the new target

        dragon.offer_casualty(game, spell_so)

        spell_objs = [so for so in game.stack.objects() if getattr(so, "is_spell", False)]
        copies = [so for so in spell_objs if so.source is not bolt]
        assert len(copies) == 1
        copy_so = copies[0]
        # The copy targets the newly chosen creature, not the original.
        assert new_target in copy_so.targets
        assert original_target not in copy_so.targets

    def test_copy_keeps_original_targets_when_declined(self) -> None:
        """Declining the new-targets choice keeps the copy's original targets."""
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        p2 = game.players[1]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _make_creature("Fodder", 1, 1, owner=p1)
        original_target = _make_creature("Target A", 2, 2, owner=p2)
        bolt = _make_instant("Targeted Bolt", owner=p1)
        set_board_state(game, 0, battlefield=[dragon, fodder])
        set_board_state(game, 1, battlefield=[original_target])

        spell_so = _spell_stack_object(bolt, p1, targets=[original_target])
        game.stack.push(spell_so)

        p1._script.append(True)    # pay casualty
        p1._script.append(fodder)  # sacrifice
        p1._script.append(False)   # do NOT choose new targets

        dragon.offer_casualty(game, spell_so)

        spell_objs = [so for so in game.stack.objects() if getattr(so, "is_spell", False)]
        copies = [so for so in spell_objs if so.source is not bolt]
        assert len(copies) == 1
        assert copies[0].targets == [original_target]

    def test_copy_is_marked_as_spell(self) -> None:
        """The pushed copy is a spell on the stack (is_spell=True)."""
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _make_creature("Fodder", 1, 1, owner=p1)
        bolt = _make_instant("Cast Bolt", owner=p1)
        set_board_state(game, 0, battlefield=[dragon, fodder])
        spell_so = _spell_stack_object(bolt, p1)
        game.stack.push(spell_so)

        p1._script.append(True)
        p1._script.append(fodder)
        p1._script.append(False)

        dragon.offer_casualty(game, spell_so)

        copies = [
            so for so in game.stack.objects()
            if getattr(so, "is_spell", False) and so.source is not bolt
        ]
        assert len(copies) == 1
        assert copies[0].is_spell is True
        assert copies[0].controller is p1

    def test_casualty_only_offered_for_controllers_own_spells(self) -> None:
        """Casualty applies to spells *you* cast — not an opponent's spell.

        If the spell on the stack is controlled by the opponent, the dragon's
        controller gets no casualty offer (no prompt, no copy).
        """
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        p2 = game.players[1]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _make_creature("Fodder", 2, 2, owner=p1)
        opp_bolt = _make_instant("Opp Bolt", owner=p2)
        set_board_state(game, 0, battlefield=[dragon, fodder])
        # Opponent's spell on the stack.
        spell_so = _spell_stack_object(opp_bolt, p2)
        game.stack.push(spell_so)

        made_copy = dragon.offer_casualty(game, spell_so)

        assert made_copy is False
        # No sacrifice, only the opponent's spell remains.
        assert game.get_battlefield(p1).contains(fodder)
        spell_objs = [so for so in game.stack.objects() if getattr(so, "is_spell", False)]
        assert len(spell_objs) == 1
        # No prompt issued to the dragon's controller.
        assert p1.remaining_choices == 0

    def test_casualty_not_offered_for_noninstant_sorcery_spell(self) -> None:
        """Casualty only applies to instant/sorcery spells, not creature spells."""
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _make_creature("Fodder", 2, 2, owner=p1)
        creature_spell = _make_creature("Cast Bear", 2, 2, owner=p1)
        set_board_state(game, 0, battlefield=[dragon, fodder])
        spell_so = _spell_stack_object(creature_spell, p1)
        game.stack.push(spell_so)

        made_copy = dragon.offer_casualty(game, spell_so)

        assert made_copy is False
        assert game.get_battlefield(p1).contains(fodder)
        assert p1.remaining_choices == 0


# ---------------------------------------------------------------------------
# Integration: casting an instant while the dragon is in play
# ---------------------------------------------------------------------------


class TestSilverquillCastingIntegration:
    """End-to-end: the casualty offer composes with the REAL cast pipeline.

    A real ``engine.casting.cast_spell`` puts the instant on the stack as a
    spell StackObject (``is_spell=True``). We then drive the documented
    ``offer_casualty`` surface against *that* real StackObject, proving the
    casualty offer + ``copy_spell`` works on top of an actually-cast spell
    (not a hand-built StackObject). Whether the card additionally wires this
    offer to fire *automatically* during ``cast_spell`` depends on an engine
    hook that is not yet present — see untestable.json.
    """

    def test_offer_casualty_on_really_cast_spell(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _make_creature("Fodder", 1, 1, owner=p1)
        bolt = _make_instant("Integration Bolt", owner=p1)
        set_board_state(
            game,
            0,
            battlefield=[dragon, fodder],
            hand=[bolt],
            mana={ManaType.RED: 1},
        )
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        # Cast the instant for real (no casualty wiring assumed here).
        engine_cast_spell(game, p1, bolt)
        # Locate the real StackObject the engine pushed for this spell.
        cast_so = next(
            so for so in game.stack.objects()
            if getattr(so, "is_spell", False) and so.source is bolt
        )
        assert cast_so.controller is p1

        # Now drive the granted casualty offer against the genuine cast spell.
        p1._script.append(True)    # pay casualty
        p1._script.append(fodder)  # sacrifice
        p1._script.append(False)   # keep same targets

        made_copy = dragon.offer_casualty(game, cast_so)

        assert made_copy is True
        # The fodder is gone and a copy of the bolt exists alongside the original.
        assert game.get_graveyard(p1).contains(fodder)
        spell_objs = [so for so in game.stack.objects() if getattr(so, "is_spell", False)]
        sources = [so.source for so in spell_objs]
        assert bolt in sources
        # original + copy
        assert len(spell_objs) == 2


# ---------------------------------------------------------------------------
# Auto-fire: the casualty offer fires AUTOMATICALLY during engine cast_spell
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyAutoFire:
    """The engine ``cast_spell`` hook fires casualty automatically.

    These tests drive the REAL ``engine.casting.cast_spell`` (no manual
    ``offer_casualty`` call) and verify the additive, fully-gated cast hook:

    * with Silverquill on the caster's battlefield and a power>=1 creature to
      sacrifice, accepting the casualty offer (via the player script) sacrifices
      the creature and pushes exactly one distinct spell copy — all without any
      manual call;
    * with no casualty-granting permanent in play, the hook is a complete no-op
      (no sacrifice, no copy, and crucially NO prompt — proven by an exhausted
      script that would raise ``ScriptExhaustedError`` if a prompt were issued);
    * declining the casualty offer at cast time leaves the spell on the stack
      with no copy and no sacrifice.

    This is the requirement previously recorded as untestable (automatic
    at-cast wiring); it is now covered against the implemented engine hook.
    """

    @staticmethod
    def _setup_main_phase(game, player_index: int) -> None:
        game.active_player_index = player_index
        game.priority_player_index = player_index
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

    def test_cast_spell_auto_fires_casualty_and_makes_one_copy(self) -> None:
        """Accept path: casting an instant through cast_spell auto-sacrifices
        the fodder and leaves exactly one distinct copy on the stack — no
        manual ``offer_casualty`` call anywhere in this test."""
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _make_creature("Fodder", 1, 1, owner=p1)
        bolt = _make_instant("Auto Bolt", owner=p1)
        set_board_state(
            game,
            0,
            battlefield=[dragon, fodder],
            hand=[bolt],
            mana={ManaType.RED: 1},
        )
        self._setup_main_phase(game, 0)

        # The casualty offer fires DURING cast_spell, so the decisions must be
        # scripted ahead of the cast: pay -> sacrifice the fodder -> keep targets.
        p1._script.append(True)    # choose_yes_no: pay casualty
        p1._script.append(fodder)  # choose_card: which creature to sacrifice
        p1._script.append(False)   # choose_yes_no: keep same targets for copy

        engine_cast_spell(game, p1, bolt)

        # The fodder was sacrificed by the auto-fired offer.
        assert game.get_graveyard(p1).contains(fodder)
        assert not game.get_battlefield(p1).contains(fodder)

        # Original spell + exactly one distinct copy on the stack.
        spell_objs = [so for so in game.stack.objects() if getattr(so, "is_spell", False)]
        assert len(spell_objs) == 2
        sources = [so.source for so in spell_objs]
        assert bolt in sources
        copies = [so for so in spell_objs if so.source is not bolt]
        assert len(copies) == 1
        copy_so = copies[0]
        assert copy_so.is_spell is True
        assert copy_so.controller is p1
        assert copy_so.source.name == bolt.name
        # The script was fully consumed by the auto-fired offer.
        assert p1.remaining_choices == 0

    def test_cast_spell_no_grantor_does_not_prompt_or_copy(self) -> None:
        """No-grantor regression: with NO casualty-granting permanent in play,
        casting an instant produces no sacrifice, no copy, and issues no
        casualty prompt (an exhausted script would raise if prompted)."""
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        # A power>=1 creature exists, but nothing grants casualty (no dragon).
        bear = _make_creature("Bear", 2, 2, owner=p1)
        bolt = _make_instant("Plain Bolt", owner=p1)
        set_board_state(
            game,
            0,
            battlefield=[bear],
            hand=[bolt],
            mana={ManaType.RED: 1},
        )
        self._setup_main_phase(game, 0)

        # Deliberately leave the script EMPTY: if the hook issued any prompt,
        # the DeterministicPlayer would raise ScriptExhaustedError.
        engine_cast_spell(game, p1, bolt)

        # No sacrifice happened.
        assert game.get_battlefield(p1).contains(bear)
        assert not game.get_graveyard(p1).contains(bear)
        # Only the original spell is on the stack — no copy.
        spell_objs = [so for so in game.stack.objects() if getattr(so, "is_spell", False)]
        assert len(spell_objs) == 1
        assert spell_objs[0].source is bolt
        # No prompt was issued.
        assert p1.remaining_choices == 0

    def test_cast_spell_decline_casualty_leaves_no_copy(self) -> None:
        """Decline-at-cast: Silverquill is in play, but the controller declines
        the casualty offer (choose_yes_no -> False), so the spell stays on the
        stack with no copy and no sacrifice."""
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _make_creature("Fodder", 2, 2, owner=p1)
        bolt = _make_instant("Decline Bolt", owner=p1)
        set_board_state(
            game,
            0,
            battlefield=[dragon, fodder],
            hand=[bolt],
            mana={ManaType.RED: 1},
        )
        self._setup_main_phase(game, 0)

        p1._script.append(False)  # choose_yes_no: decline casualty

        engine_cast_spell(game, p1, bolt)

        # Nothing sacrificed.
        assert game.get_battlefield(p1).contains(fodder)
        assert not game.get_graveyard(p1).contains(fodder)
        # Only the original spell on the stack.
        spell_objs = [so for so in game.stack.objects() if getattr(so, "is_spell", False)]
        assert len(spell_objs) == 1
        assert spell_objs[0].source is bolt
        # The single decline answer was consumed; nothing left over.
        assert p1.remaining_choices == 0
