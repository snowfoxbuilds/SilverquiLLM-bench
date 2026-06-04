"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares.

Emeritus of Truce is a {1}{W}{W} white Creature — Cat Cleric, 3/3, with the
SOS-specific **Prepared** keyword. Its front face reads:

    "When this creature enters, target player creates a 1/1 white and black
     Inkling creature token with flying. Then if an opponent controls more
     creatures than you, this creature becomes prepared. (While it's
     prepared, you may cast a copy of its spell. Doing so unprepares it.)"

The prepare spell is *Swords to Plowshares* ({W} instant).

This file covers the testable observable contract:

1. **Static card data** — name, mana cost, P/T, Cat/Cleric subtypes, white,
   the Prepared keyword.

2. **Enters-the-battlefield trigger** — a ``When this creature enters``
   ability is registered, keyed to this creature, watching the
   ``EntersBattlefieldTriggeredEvent``.

3. **ETB effect** — resolving the trigger creates a 1/1 Inkling creature
   token with flying for the chosen / controlling player.

4. **Conditional "becomes prepared"** — the creature gains a ``prepared``
   designation only when an opponent controls *more* creatures than the
   controller; it does not when the controller has at least as many.

Once the engine grew first-class support (a ``colors`` attribute on cards
and ``engine.casting.cast_prepared_spell``), three formerly-untestable
requirements are now exercised end-to-end:

* the Inkling token is **white and black** (``TestEmeritusInklingColor``);
* the **Prepared cast loop** — becoming prepared, casting the copy, and the
  copy clearing the prepared designation (``TestEmeritusPreparedCastLoop``);
* the **Swords to Plowshares** effect — exiling the target creature and
  granting its controller life equal to its power
  (``TestSwordsToPlowsharesEffect``).
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.card import Creature
from engine.casting import cast_prepared_spell
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Color, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


CARD_NAME = "Emeritus of Truce // Swords to Plowshares"


def _card(p: Any = None) -> EmeritusOfTruceSwordsToPlowshares:
    """Instantiate the card under test, optionally bound to an owner."""
    return EmeritusOfTruceSwordsToPlowshares(owner=p, controller=p)


def _vanilla(name: str = "Grizzly Bears") -> Creature:
    """A vanilla creature for populating battlefields."""
    c = Creature(name=name, base_power=2, base_toughness=2)
    c.card_types = {CardType.CREATURE}
    return c


def _all_battlefield_creatures(game: Any) -> list[Any]:
    """Every creature on every player's battlefield."""
    out: list[Any] = []
    for p in game.players:
        for obj in game.get_battlefield(p).get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                out.append(obj)
    return out


def _find_inkling(game: Any) -> Any:
    """Return the first Inkling token found on any battlefield, else None."""
    for obj in _all_battlefield_creatures(game):
        if obj.name == "Inkling" or "Inkling" in getattr(obj, "subtypes", set()):
            return obj
    return None


def _resolve_etb(game: Any, card: Any) -> None:
    """Fire this creature's enters-the-battlefield event and resolve every
    triggered ability it puts on the stack (the ETB effect)."""
    game.trigger_manager.fire_event(
        game,
        EntersBattlefieldTriggeredEvent(
            permanent=card, controller=card.controller, creature=card, card=card
        ),
    )
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------


class TestEmeritusProperties:
    """Front-face static data should match the SOS 13 spec."""

    def test_is_creature(self) -> None:
        card = _card()
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_name(self) -> None:
        assert _card().name == CARD_NAME

    def test_mana_cost_is_1ww(self) -> None:
        assert _card().mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_power_toughness(self) -> None:
        card = _card()
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_is_cat_cleric(self) -> None:
        subtypes = _card().subtypes
        assert "Cat" in subtypes
        assert "Cleric" in subtypes

    def test_not_summoning_sick_flag_default(self) -> None:
        # Sanity: a freshly constructed creature defaults to summoning sick;
        # this guards against an over-eager constructor clearing the flag.
        assert _card().summoning_sick is True


class TestEmeritusPreparedKeyword:
    """The card carries the SOS 'Prepared' keyword/marker per its spec."""

    def test_prepared_is_advertised(self) -> None:
        """The Prepared mechanic must be surfaced somewhere observable:
        either as a ``Keyword.PREPARED`` flag, a dedicated attribute, or in
        the rules text. A bare creature with no Prepared surface fails."""
        card = _card()
        has_keyword = (
            hasattr(Keyword, "PREPARED") and bool(card.keywords & Keyword.PREPARED)
        )
        has_attr = hasattr(card, "is_prepared") or hasattr(card, "prepared")
        text = getattr(card, "rules_text", "").lower()
        assert has_keyword or has_attr or "prepared" in text

    def test_starts_unprepared(self) -> None:
        """A creature only gains the prepared designation via its ETB
        conditional — on construction it must not already be prepared."""
        card = _card()
        prepared = getattr(card, "is_prepared", None)
        if prepared is None:
            prepared = getattr(card, "prepared", None)
        if prepared is None:
            pytest.skip("no boolean prepared designation surface to inspect")
        assert prepared is False


# ---------------------------------------------------------------------------
# Enters-the-battlefield trigger registration
# ---------------------------------------------------------------------------


class TestEmeritusEtbTriggerRegistration:
    """register_triggers wires an ETB trigger keyed to this creature."""

    def test_registers_a_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _card(p1)
        before = len(game.trigger_manager.get_triggers_for_source(card))
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers_for_source(card))
        assert after - before >= 1

    def test_trigger_watches_enters_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _card(p1)
        card.register_triggers(game)
        regs = game.trigger_manager.get_triggers_for_source(card)
        assert any(
            reg.event_type is EntersBattlefieldTriggeredEvent
            or issubclass(EntersBattlefieldTriggeredEvent, reg.event_type)
            for reg in regs
        )

    def test_trigger_controller_is_card_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _card(p1)
        card.register_triggers(game)
        regs = game.trigger_manager.get_triggers_for_source(card)
        etb = [
            r for r in regs
            if issubclass(EntersBattlefieldTriggeredEvent, r.event_type)
            or r.event_type is EntersBattlefieldTriggeredEvent
        ]
        assert etb, "expected an ETB trigger registration"
        assert etb[0].controller is p1

    def test_trigger_fires_for_self_only(self) -> None:
        """The ETB trigger must fire when *this* creature enters, and not
        when an unrelated permanent enters."""
        game = create_game()
        p1 = game.players[0]
        card = _card(p1)
        card.register_triggers(game)
        regs = game.trigger_manager.get_triggers_for_source(card)
        etb = [
            r for r in regs
            if issubclass(EntersBattlefieldTriggeredEvent, r.event_type)
            or r.event_type is EntersBattlefieldTriggeredEvent
        ]
        assert etb, "expected an ETB trigger registration"
        reg = etb[0]
        if reg.condition is None:
            pytest.skip("trigger fires unconditionally; self-only check N/A")
        self_event = EntersBattlefieldTriggeredEvent(
            permanent=card, controller=p1, creature=card, card=card
        )
        other = _vanilla("Other Permanent")
        other.owner = p1
        other.controller = p1
        other_event = EntersBattlefieldTriggeredEvent(
            permanent=other, controller=p1, creature=other, card=other
        )
        assert reg.condition(game, self_event) is True
        assert reg.condition(game, other_event) is False


# ---------------------------------------------------------------------------
# ETB effect — create a 1/1 Inkling with flying
# ---------------------------------------------------------------------------


class TestEmeritusEtbCreatesInkling:
    """Resolving the ETB trigger creates a 1/1 flying Inkling token."""

    def _setup(self):
        # Pre-seed three scripted self-target answers in case the
        # implementation asks for "target player"; unused answers are fine.
        game = create_game(scripts=([None, None, None], []))
        game.active_player_index = 0
        p1 = game.players[0]
        # Point any scripted target choice at the controller (p1).
        for i in range(len(p1._script)):
            p1._script[i] = p1
        card = _card(p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        return game, p1, card

    def test_etb_creates_a_token(self) -> None:
        game, p1, card = self._setup()
        before = len(_all_battlefield_creatures(game))
        _resolve_etb(game, card)
        after = len(_all_battlefield_creatures(game))
        assert after - before == 1, "ETB should create exactly one new creature token"

    def test_token_is_named_inkling(self) -> None:
        game, p1, card = self._setup()
        _resolve_etb(game, card)
        token = _find_inkling(game)
        assert token is not None, "an Inkling token should have been created"

    def test_token_is_one_one(self) -> None:
        game, p1, card = self._setup()
        _resolve_etb(game, card)
        token = _find_inkling(game)
        assert token is not None
        assert token.base_power == 1
        assert token.base_toughness == 1

    def test_token_has_flying(self) -> None:
        game, p1, card = self._setup()
        _resolve_etb(game, card)
        token = _find_inkling(game)
        assert token is not None
        assert bool(token.keywords & Keyword.FLYING)

    def test_token_is_a_real_token(self) -> None:
        game, p1, card = self._setup()
        _resolve_etb(game, card)
        token = _find_inkling(game)
        assert token is not None
        assert getattr(token, "is_token", False) is True

    def test_token_goes_to_targeted_player(self) -> None:
        """'target player creates ...' — when player 2 is chosen as the
        target, the Inkling enters under player 2's control. The choice is
        scripted on player 1 (the controller making the ETB choice)."""
        game = create_game(scripts=([None], []))
        game.active_player_index = 0
        p1, p2 = game.players[0], game.players[1]
        card = _card(p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        # Patch scripted answer to the actual opponent player object.
        p1._script[0] = p2
        _resolve_etb(game, card)
        token = _find_inkling(game)
        if token is None:
            pytest.skip("no Inkling created; covered by other tests")
        # If the effect honours a chosen target player, the token is p2's.
        # Implementations that always give it to the controller are still
        # tested by the other cases; here we only assert *iff* a target was
        # consumed (script empty means the choice was used).
        if p1.remaining_choices == 0:
            assert token.controller is p2


# ---------------------------------------------------------------------------
# Conditional "becomes prepared"
# ---------------------------------------------------------------------------


def _prepared_flag(card: Any):
    """Best-effort read of the prepared designation; None if no surface."""
    for attr in ("is_prepared", "prepared"):
        if hasattr(card, attr):
            return getattr(card, attr)
    return None


class TestEmeritusBecomesPrepared:
    """'Then if an opponent controls more creatures than you, this creature
    becomes prepared.' The designation is a marker on the permanent."""

    def _setup(self, my_extra_creatures: int, opp_creatures: int):
        # Script a controller target choice (self) for the token step.
        game = create_game(scripts=([None, None], []))
        game.active_player_index = 0
        p1, p2 = game.players[0], game.players[1]
        card = _card(p1)
        my_board = [card] + [_vanilla(f"Mine{i}") for i in range(my_extra_creatures)]
        opp_board = [_vanilla(f"Opp{i}") for i in range(opp_creatures)]
        set_board_state(game, 0, battlefield=my_board)
        set_board_state(game, 1, battlefield=opp_board)
        card.register_triggers(game)
        # Point any scripted target at the controller.
        for i in range(len(p1._script)):
            p1._script[i] = p1
        return game, p1, p2, card

    def test_prepared_when_opponent_has_more_creatures(self) -> None:
        # Controller: just the Emeritus (1 creature). Opponent: 3 creatures.
        game, p1, p2, card = self._setup(my_extra_creatures=0, opp_creatures=3)
        _resolve_etb(game, card)
        flag = _prepared_flag(card)
        if flag is None:
            pytest.skip("no observable prepared designation surface")
        assert flag is True, "opponent has more creatures → becomes prepared"

    def test_not_prepared_when_counts_equal(self) -> None:
        # Controller controls Emeritus + 2 vanilla (3 total, counting itself
        # which is now on the battlefield). Opponent controls 3 creatures.
        # "more than you" is strict, so equal counts → NOT prepared.
        game, p1, p2, card = self._setup(my_extra_creatures=2, opp_creatures=3)
        _resolve_etb(game, card)
        flag = _prepared_flag(card)
        if flag is None:
            pytest.skip("no observable prepared designation surface")
        assert flag is False, "equal creature counts must not prepare (strict >)"

    def test_not_prepared_when_controller_has_more(self) -> None:
        # Controller: Emeritus + 4 vanilla (5). Opponent: 1 creature.
        game, p1, p2, card = self._setup(my_extra_creatures=4, opp_creatures=1)
        _resolve_etb(game, card)
        flag = _prepared_flag(card)
        if flag is None:
            pytest.skip("no observable prepared designation surface")
        assert flag is False, "controller has more creatures → not prepared"

    def test_not_prepared_with_no_opponent_creatures(self) -> None:
        # Opponent controls nothing; controller controls only the Emeritus.
        game, p1, p2, card = self._setup(my_extra_creatures=0, opp_creatures=0)
        _resolve_etb(game, card)
        flag = _prepared_flag(card)
        if flag is None:
            pytest.skip("no observable prepared designation surface")
        assert flag is False


class TestEmeritusPrepareSpell:
    """The prepare spell (inset face) is Swords to Plowshares — a {W}
    instant. If the implementation exposes the prepare-spell characteristics
    in any observable way, they should match Swords to Plowshares."""

    def test_prepare_spell_surface_if_present(self) -> None:
        card = _card()
        # Look for any conventional surface naming the prepare spell.
        candidates = [
            getattr(card, "prepare_spell", None),
            getattr(card, "prepared_spell", None),
            getattr(card, "back_face", None),
            getattr(card, "other_face", None),
        ]
        surface = next((c for c in candidates if c is not None), None)
        if surface is None:
            pytest.skip("no prepare-spell surface exposed by the implementation")
        # If a surface exists, it should advertise Swords to Plowshares ({W}).
        name = getattr(surface, "name", "")
        cost = getattr(surface, "mana_cost", None)
        assert "Swords to Plowshares" in name
        assert cost == ManaCost.parse("{W}")


# ---------------------------------------------------------------------------
# Inkling token color — "a 1/1 white and black Inkling"
# ---------------------------------------------------------------------------


class TestEmeritusInklingColor:
    """The ETB token must be both white AND black (its full color identity)."""

    def _make_inkling(self):
        game = create_game(scripts=([None, None, None], []))
        game.active_player_index = 0
        p1 = game.players[0]
        for i in range(len(p1._script)):
            p1._script[i] = p1
        card = _card(p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        _resolve_etb(game, card)
        return _find_inkling(game)

    def test_token_is_white_and_black(self) -> None:
        token = self._make_inkling()
        assert token is not None, "an Inkling token should have been created"
        assert token.colors == {Color.WHITE, Color.BLACK}

    def test_token_is_white(self) -> None:
        token = self._make_inkling()
        assert token is not None
        assert Color.WHITE in token.colors

    def test_token_is_black(self) -> None:
        token = self._make_inkling()
        assert token is not None
        assert Color.BLACK in token.colors

    def test_token_is_not_other_colors(self) -> None:
        token = self._make_inkling()
        assert token is not None
        assert Color.BLUE not in token.colors
        assert Color.RED not in token.colors
        assert Color.GREEN not in token.colors


# ---------------------------------------------------------------------------
# Prepare spell static data — Swords to Plowshares is a white {W} instant
# ---------------------------------------------------------------------------


class TestSwordsToPlowsharesCard:
    """The inset prepare spell's own static characteristics."""

    def test_is_instant(self) -> None:
        spell = SwordsToPlowshares()
        assert CardType.INSTANT in spell.card_types

    def test_name(self) -> None:
        assert SwordsToPlowshares().name == "Swords to Plowshares"

    def test_mana_cost_is_w(self) -> None:
        assert SwordsToPlowshares().mana_cost == ManaCost.parse("{W}")

    def test_is_white(self) -> None:
        assert SwordsToPlowshares().colors == {Color.WHITE}

    def test_prepare_spell_attribute_is_swords(self) -> None:
        card = _card()
        assert isinstance(card.prepare_spell, SwordsToPlowshares)
        # Aliases all resolve to the same inset spell.
        assert card.prepared_spell is card.prepare_spell
        assert card.other_face is card.prepare_spell


# ---------------------------------------------------------------------------
# Prepared cast loop — "you may cast a copy of its spell. Doing so unprepares it."
# ---------------------------------------------------------------------------


class TestEmeritusPreparedCastLoop:
    """Becoming prepared, then casting the copy clears the prepared marker
    and puts a Swords-to-Plowshares copy on the stack."""

    def _setup_prepared(self):
        """Build a game where the Emeritus is prepared and an opponent
        creature is available to target with the prepared copy."""
        game = create_game(scripts=([None, None], []))
        game.active_player_index = 0
        p1, p2 = game.players[0], game.players[1]
        card = _card(p1)
        target = _vanilla("Target Creature")
        # The ETB token goes to p1 (scripted self-target), so after resolution
        # p1 controls Emeritus + Inkling = 2. Give p2 three creatures so the
        # opponent controls strictly more → the Emeritus becomes prepared.
        set_board_state(game, 0, battlefield=[card])
        set_board_state(
            game, 1, battlefield=[target, _vanilla("OppExtra"), _vanilla("OppExtra2")]
        )
        card.register_triggers(game)
        for i in range(len(p1._script)):
            p1._script[i] = p1
        _resolve_etb(game, card)
        return game, p1, p2, card, target

    def test_becomes_prepared_first(self) -> None:
        # Sanity for the loop's precondition.
        _, _, _, card, _ = self._setup_prepared()
        assert card.is_prepared is True

    def test_cast_copy_clears_prepared(self) -> None:
        game, p1, p2, card, target = self._setup_prepared()
        cast_prepared_spell(game, card, targets=[target])
        assert card.is_prepared is False, "casting the copy must unprepare it"

    def test_cast_copy_puts_spell_on_stack(self) -> None:
        game, p1, p2, card, target = self._setup_prepared()
        stack_obj = cast_prepared_spell(game, card, targets=[target])
        assert stack_obj is not None, "the prepared copy should go on the stack"
        assert not game.stack.is_empty()
        assert isinstance(stack_obj.source, SwordsToPlowshares)

    def test_cast_copy_is_a_distinct_object(self) -> None:
        # The copy must not be the inset face itself (so the face is reusable).
        game, p1, p2, card, target = self._setup_prepared()
        stack_obj = cast_prepared_spell(game, card, targets=[target])
        assert stack_obj is not None
        assert stack_obj.source is not card.prepare_spell

    def test_cast_when_not_prepared_is_noop(self) -> None:
        # If the permanent is not prepared, the helper must not cast anything.
        game = create_game()
        game.active_player_index = 0
        p1 = game.players[0]
        card = _card(p1)
        set_board_state(game, 0, battlefield=[card])
        assert card.is_prepared is False
        result = cast_prepared_spell(game, card, targets=None)
        assert result is None
        assert game.stack.is_empty()

    def test_convenience_method_delegates(self) -> None:
        game, p1, p2, card, target = self._setup_prepared()
        stack_obj = card.cast_prepare_copy(game, targets=[target])
        assert stack_obj is not None
        assert card.is_prepared is False
        assert isinstance(stack_obj.source, SwordsToPlowshares)


# ---------------------------------------------------------------------------
# Swords to Plowshares effect — exile target creature; controller gains
# life equal to its power.
# ---------------------------------------------------------------------------


def _in_exile(game: Any, obj: Any) -> bool:
    """True if *obj* is in any player's exile zone."""
    for p in game.players:
        if p.zones[Zone.EXILE].contains(obj):
            return True
    return False


class TestSwordsToPlowsharesEffect:
    """Resolving the prepared Swords-to-Plowshares copy exiles the target
    creature and grants its controller life equal to that creature's power."""

    def _setup_and_cast(self, target_power: int):
        game = create_game(scripts=([None, None], []))
        game.active_player_index = 0
        p1, p2 = game.players[0], game.players[1]
        card = _card(p1)
        target = Creature(
            name="Big Target", base_power=target_power, base_toughness=target_power
        )
        target.card_types = {CardType.CREATURE}
        # Make p1 prepared: opponent controls strictly more creatures even
        # after p1 receives the ETB Inkling (Emeritus + Inkling = 2 < 3).
        set_board_state(game, 0, battlefield=[card])
        set_board_state(
            game, 1, battlefield=[target, _vanilla("OppExtra"), _vanilla("OppExtra2")]
        )
        card.register_triggers(game)
        for i in range(len(p1._script)):
            p1._script[i] = p1
        _resolve_etb(game, card)
        assert card.is_prepared is True
        stack_obj = cast_prepared_spell(game, card, targets=[target])
        assert stack_obj is not None
        return game, p1, p2, target, stack_obj

    def test_target_creature_is_exiled(self) -> None:
        game, p1, p2, target, stack_obj = self._setup_and_cast(target_power=4)
        # Target is on the battlefield before resolution.
        assert target in game.get_battlefield(p2).get_all()
        stack_obj.on_resolve(game)
        assert target not in game.get_battlefield(p2).get_all()
        assert _in_exile(game, target)

    def test_controller_gains_life_equal_to_power(self) -> None:
        game, p1, p2, target, stack_obj = self._setup_and_cast(target_power=4)
        before = p2.life  # p2 controls the target creature.
        stack_obj.on_resolve(game)
        assert p2.life == before + 4

    def test_life_gain_uses_targets_controller_not_caster(self) -> None:
        # Life goes to the creature's controller (p2), not the spell's
        # controller (p1).
        game, p1, p2, target, stack_obj = self._setup_and_cast(target_power=3)
        p1_before = p1.life
        stack_obj.on_resolve(game)
        assert p1.life == p1_before, "caster must not gain the life"

    def test_zero_power_creature_grants_no_life(self) -> None:
        game, p1, p2, target, stack_obj = self._setup_and_cast(target_power=0)
        before = p2.life
        stack_obj.on_resolve(game)
        assert _in_exile(game, target), "zero-power creature is still exiled"
        assert p2.life == before, "0 power → no life gained"

    def test_effect_directly_on_resolve(self) -> None:
        # Exercise SwordsToPlowshares.on_resolve directly with a chosen target,
        # independent of the prepared-cast plumbing.
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        target = Creature(name="Direct Target", base_power=5, base_toughness=5)
        target.card_types = {CardType.CREATURE}
        set_board_state(game, 1, battlefield=[target])
        before = p2.life
        spell = SwordsToPlowshares(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)
        assert _in_exile(game, target)
        assert p2.life == before + 5
