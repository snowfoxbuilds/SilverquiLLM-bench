"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares.

Oracle text (from card_spec.json), front (creature) face:

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's prepared,
    you may cast a copy of its spell. Doing so unprepares it.)

Static data:

    Emeritus of Truce // Swords to Plowshares
    {1}{W}{W} // {W}
    Creature — Cat Cleric // Instant
    3/3, white, mythic, keyword "Prepared".

Behaviour contract derived from the spec
----------------------------------------

* Front face is a white Creature — Cat Cleric, 3/3, mana cost {1}{W}{W}.
* Enters-the-battlefield trigger: a target player (chosen by the
  controller — may be the controller themselves or an opponent) creates a
  1/1 white-and-black Inkling creature token with flying.  The token enters
  under the *targeted* player's control.
* Conditional "becomes prepared": after the token is created, the creature
  becomes prepared **only if** an opponent controls strictly more creatures
  than the controller.  Otherwise it does not become prepared.
* The card is a Preparation card (rule 722): it has a back/prepare "spell"
  half — Swords to Plowshares, an Instant costing {W}.

These tests are written for the TDD red phase: they FAIL against the empty
stub and PASS once the card is implemented correctly.
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine import preparation
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.protection import get_colors
from engine.triggers import TriggerRegistration
from engine.types import CardType, Color, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _vanilla_creature(name: str = "Grizzly Bears") -> Creature:
    """A plain 2/2 creature for filling out board states."""
    return Creature(
        name=name,
        mana_cost=ManaCost.parse("{1}{G}"),
        base_power=2,
        base_toughness=2,
    )


def _resolve_full_stack(game: Any) -> None:
    """Resolve every object currently on the stack, top-down.

    Mirrors ``test_utils._resolve_top_of_stack`` but local so it can be reused
    after manually firing the ETB trigger (whose resolution applies the token
    / prepared effect).
    """
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _inkling_tokens(game: Any, player: Any) -> list[Creature]:
    """Return all Inkling-like token creatures on *player*'s battlefield.

    Detection is intentionally tolerant of the exact representation: any
    battlefield creature flagged ``is_token`` whose name or subtypes mention
    "Inkling" counts.
    """
    result: list[Creature] = []
    for obj in game.get_battlefield(player).get_all():
        if not isinstance(obj, Creature):
            continue
        if not getattr(obj, "is_token", False):
            continue
        name = getattr(obj, "name", "") or ""
        subtypes = getattr(obj, "subtypes", set()) or set()
        if "Inkling" in name or "Inkling" in subtypes:
            result.append(obj)
    return result


def _all_tokens(game: Any, player: Any) -> list[Creature]:
    """Return every token creature on *player*'s battlefield."""
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if isinstance(obj, Creature) and getattr(obj, "is_token", False)
    ]


def _is_prepared(card: Any) -> bool:
    """Best-effort read of the 'prepared' designation on *card*.

    The mechanic is new; the implementation may expose it as ``is_prepared``,
    ``prepared``, or a ``Keyword.PREPARED``-style flag.  We probe the common
    representations so the behavioural tests aren't coupled to one spelling.
    """
    for attr in ("is_prepared", "prepared"):
        val = getattr(card, attr, None)
        if isinstance(val, bool):
            return val
    return False


def _make_etb_card(game: Any, controller_index: int) -> EmeritusOfTruceSwordsToPlowshares:
    """Place the creature on *controller_index*'s battlefield and wire triggers.

    Returns the card with ``register_triggers`` already called.  The ETB event
    is *not* fired here — tests fire it explicitly so they can control the
    target choice first (the engine fires ETB before registration, so the
    self-ETB trigger is exercised by an explicit ``fire_event``).
    """
    p = game.players[controller_index]
    card = EmeritusOfTruceSwordsToPlowshares(owner=p, controller=p)
    set_board_state(game, controller_index, battlefield=[card])
    game.active_player_index = controller_index
    card.register_triggers(game)
    return card


def _fire_etb(game: Any, card: Any, target_player: Any) -> None:
    """Fire the creature's ETB event after pointing it at *target_player*.

    Sets ``chosen_targets`` (the resolve-time idiom used by FDN ETB cards) and
    also seeds the controller's script with the target so an implementation
    that asks at resolution time is satisfied either way.
    """
    card.chosen_targets = [target_player]
    controller = card.controller
    if controller is not None and hasattr(controller, "_script"):
        controller._script.extend([target_player, target_player])
    game.trigger_manager.fire_event(
        game, EntersBattlefieldTriggeredEvent(permanent=card, controller=controller)
    )
    _resolve_full_stack(game)


# ---------------------------------------------------------------------------
# Static card data — front (creature) face
# ---------------------------------------------------------------------------


class TestEmeritusProperties:
    """Front-face characteristics must match the SOS 13 spec."""

    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_name_includes_emeritus_of_truce(self) -> None:
        # The front-face name; the implementation may expose either the
        # creature-half name or the combined split name.
        name = EmeritusOfTruceSwordsToPlowshares(owner=None).name
        assert "Emeritus of Truce" in name

    def test_front_face_mana_cost(self) -> None:
        # The castable (creature) half costs {1}{W}{W}.
        cost = EmeritusOfTruceSwordsToPlowshares(owner=None).mana_cost
        assert cost == ManaCost.parse("{1}{W}{W}")

    def test_power_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_is_white(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert get_colors(card) == {Color.WHITE}

    def test_subtypes_cat_cleric(self) -> None:
        subtypes = EmeritusOfTruceSwordsToPlowshares(owner=None).subtypes
        assert "Cat" in subtypes
        assert "Cleric" in subtypes


# ---------------------------------------------------------------------------
# ETB trigger registration
# ---------------------------------------------------------------------------


class TestEmeritusEtbTriggerRegistration:
    """register_triggers wires a self-referencing ETB trigger."""

    def test_registers_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after - before == 1

    def test_trigger_watches_enters_battlefield_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        regs = game.trigger_manager.get_triggers_for_source(card)
        assert len(regs) == 1
        reg = regs[0]
        assert isinstance(reg, TriggerRegistration)
        assert reg.event_type is EntersBattlefieldTriggeredEvent

    def test_trigger_only_fires_for_this_card(self) -> None:
        """A different permanent entering must not fire this card's ETB."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        card.register_triggers(game)

        other = _vanilla_creature("Some Other Bear")
        other.owner = p1
        other.controller = p1
        game.trigger_manager.fire_event(
            game, EntersBattlefieldTriggeredEvent(permanent=other, controller=p1)
        )
        assert game.stack.is_empty()

    def test_trigger_fires_when_this_card_enters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game, EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        )
        assert not game.stack.is_empty()
        assert game.stack.peek().source is card


# ---------------------------------------------------------------------------
# ETB token creation
# ---------------------------------------------------------------------------


class TestEmeritusTokenCreation:
    """target player creates a 1/1 white & black Inkling token with flying."""

    def test_controller_target_gets_one_inkling(self) -> None:
        game = create_game()
        card = _make_etb_card(game, 0)
        p1 = game.players[0]
        before = len(_all_tokens(game, p1))
        _fire_etb(game, card, p1)
        inklings = _inkling_tokens(game, p1)
        assert len(inklings) == 1
        # Exactly one token was created for the chosen player.
        assert len(_all_tokens(game, p1)) == before + 1

    def test_token_is_one_one(self) -> None:
        game = create_game()
        card = _make_etb_card(game, 0)
        p1 = game.players[0]
        _fire_etb(game, card, p1)
        token = _inkling_tokens(game, p1)[0]
        assert token.base_power == 1
        assert token.base_toughness == 1

    def test_token_has_flying(self) -> None:
        game = create_game()
        card = _make_etb_card(game, 0)
        p1 = game.players[0]
        _fire_etb(game, card, p1)
        token = _inkling_tokens(game, p1)[0]
        assert Keyword.FLYING & token.keywords

    def test_token_is_white_and_black(self) -> None:
        game = create_game()
        card = _make_etb_card(game, 0)
        p1 = game.players[0]
        _fire_etb(game, card, p1)
        token = _inkling_tokens(game, p1)[0]
        assert get_colors(token) == {Color.WHITE, Color.BLACK}

    def test_targeting_opponent_creates_token_under_opponent(self) -> None:
        """"target player" may be an opponent; the token enters under that
        targeted player's control, not the controller's."""
        game = create_game()
        card = _make_etb_card(game, 0)
        p1 = game.players[0]
        p2 = game.players[1]
        _fire_etb(game, card, p2)
        # The opponent receives the Inkling.
        assert len(_inkling_tokens(game, p2)) == 1
        # The controller does not get a token in this case.
        assert len(_inkling_tokens(game, p1)) == 0
        token = _inkling_tokens(game, p2)[0]
        assert token.controller is p2

    def test_token_is_a_creature_token(self) -> None:
        game = create_game()
        card = _make_etb_card(game, 0)
        p1 = game.players[0]
        _fire_etb(game, card, p1)
        token = _inkling_tokens(game, p1)[0]
        assert CardType.CREATURE in token.card_types
        assert token.is_token is True


# ---------------------------------------------------------------------------
# Conditional "becomes prepared"
# ---------------------------------------------------------------------------


class TestEmeritusBecomesPrepared:
    """"Then if an opponent controls more creatures than you, this creature
    becomes prepared."

    Each board state below is chosen so the prepared outcome is the same
    whether the implementation evaluates the creature counts *before* or
    *after* the Inkling token is created — by directing the token to the
    player whose count is irrelevant to crossing the threshold.
    """

    @staticmethod
    def _rewire(game: Any, card: Any) -> None:
        """Re-register the self-ETB trigger after set_board_state wipes it."""
        game.trigger_manager.unregister(card)
        card.register_triggers(game)

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        game = create_game()
        card = _make_etb_card(game, 0)
        p1 = game.players[0]
        p2 = game.players[1]
        # Controller controls only Emeritus (1); opponent controls 3.
        set_board_state(game, 0, battlefield=[card])
        set_board_state(
            game,
            1,
            battlefield=[
                _vanilla_creature("Foe A"),
                _vanilla_creature("Foe B"),
                _vanilla_creature("Foe C"),
            ],
        )
        self._rewire(game, card)
        # Send the token to the opponent so the controller's count stays 1.
        # opponent 3-or-4 > you 1 either way -> prepared.
        _fire_etb(game, card, p2)
        assert len(_inkling_tokens(game, p2)) == 1
        assert _is_prepared(card) is True

    def test_not_prepared_when_counts_equal(self) -> None:
        """Opponent must control *strictly more* creatures — an equal count
        does not prepare the creature."""
        game = create_game()
        card = _make_etb_card(game, 0)
        p1 = game.players[0]
        # Controller has Emeritus + one ally (2); opponent has two foes (2).
        set_board_state(game, 0, battlefield=[card, _vanilla_creature("Ally")])
        set_board_state(
            game,
            1,
            battlefield=[_vanilla_creature("Foe A"), _vanilla_creature("Foe B")],
        )
        self._rewire(game, card)
        # Token goes to the controller -> you 3, opponent 2 (and pre-token the
        # counts were equal 2==2). Opponent never has strictly more -> no prep.
        _fire_etb(game, card, p1)
        # Anchor to real ETB execution: the token must have been created, so a
        # passing assertion means the not-prepared branch was actually reached
        # (not that the mechanic is simply unimplemented).
        assert len(_inkling_tokens(game, p1)) == 1
        assert _is_prepared(card) is False

    def test_not_prepared_when_controller_has_more_creatures(self) -> None:
        game = create_game()
        card = _make_etb_card(game, 0)
        p1 = game.players[0]
        p2 = game.players[1]
        # Controller has Emeritus + two allies (3); opponent has nothing.
        set_board_state(
            game,
            0,
            battlefield=[card, _vanilla_creature("Ally A"), _vanilla_creature("Ally B")],
        )
        set_board_state(game, 1, battlefield=[])
        self._rewire(game, card)
        # Token goes to the opponent -> opponent at most 1 vs your 3 -> no prep.
        _fire_etb(game, card, p2)
        assert len(_inkling_tokens(game, p2)) == 1
        assert _is_prepared(card) is False

    def test_not_prepared_when_opponent_has_no_creatures(self) -> None:
        game = create_game()
        card = _make_etb_card(game, 0)
        p1 = game.players[0]
        # Opponent controls nothing; controller controls Emeritus. Token to you.
        _fire_etb(game, card, p1)
        assert len(_inkling_tokens(game, p1)) == 1
        assert _is_prepared(card) is False


# ---------------------------------------------------------------------------
# Preparation-card / back ("Swords to Plowshares") half
# ---------------------------------------------------------------------------


class TestSwordsToPlowsharesHalf:
    """The card is a Preparation card with a back/prepare spell half."""

    def test_prepare_spell_mana_cost_is_w(self) -> None:
        """The prepare ("Swords to Plowshares") half costs {W}.

        The implementation exposes the prepare spell's cost somewhere — try
        the common shapes (a dedicated attribute or a copy/factory) before
        giving up.
        """
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        expected = ManaCost.parse("{W}")
        candidates: list[Any] = []
        for attr in (
            "prepare_mana_cost",
            "back_mana_cost",
            "swords_mana_cost",
        ):
            val = getattr(card, attr, None)
            if isinstance(val, ManaCost):
                candidates.append(val)
        for attr in ("prepare_spell", "back_face", "back_spell", "swords_to_plowshares"):
            half = getattr(card, attr, None)
            if half is not None:
                cost = getattr(half, "mana_cost", None)
                if isinstance(cost, ManaCost):
                    candidates.append(cost)
            if callable(half):
                try:
                    produced = half()
                except TypeError:
                    produced = None
                cost = getattr(produced, "mana_cost", None)
                if isinstance(cost, ManaCost):
                    candidates.append(cost)
        assert candidates, "no prepare-spell cost surface found on the card"
        assert any(c == expected for c in candidates)


# ---------------------------------------------------------------------------
# Extended coverage — engine Preparation framework (engine/preparation.py)
#
# The Implementer built the additive Preparation-card framework, so the three
# items previously deferred in untestable.json are now observable:
#   (1) copy-of-the-prepare-spell-in-exile creation on becoming prepared,
#   (2) cast-from-exile + unprepare-on-cast transition,
#   (3) the Swords to Plowshares back-face effect.
# ---------------------------------------------------------------------------


def _prepared_card_on_battlefield(
    game: Any, controller_index: int = 0
) -> EmeritusOfTruceSwordsToPlowshares:
    """Put an Emeritus on *controller_index*'s battlefield, owned/controlled by
    that player, so ``mark_prepared`` has a real controller to exile to."""
    p = game.players[controller_index]
    card = EmeritusOfTruceSwordsToPlowshares(owner=p, controller=p)
    set_board_state(game, controller_index, battlefield=[card])
    card.owner = p
    card.controller = p
    return card


class TestPreparationCopyInExile:
    """(1) On becoming prepared, the controller creates a {W} Swords to
    Plowshares instant copy in their exile, keyed to the prepared permanent."""

    def test_mark_prepared_sets_designation(self) -> None:
        game = create_game()
        card = _prepared_card_on_battlefield(game, 0)
        assert preparation.is_prepared(card) is False
        preparation.mark_prepared(game, card)
        assert preparation.is_prepared(card) is True

    def test_mark_prepared_returns_exiled_copy(self) -> None:
        game = create_game()
        card = _prepared_card_on_battlefield(game, 0)
        p1 = game.players[0]
        copy = preparation.mark_prepared(game, card)
        assert copy is not None
        # The returned copy is the one sitting in the controller's exile.
        assert game.get_exile(p1).contains(copy)

    def test_exiled_copy_is_swords_to_plowshares_instant(self) -> None:
        game = create_game()
        card = _prepared_card_on_battlefield(game, 0)
        copy = preparation.mark_prepared(game, card)
        assert isinstance(copy, SwordsToPlowshares)
        assert CardType.INSTANT in copy.card_types

    def test_exiled_copy_costs_w(self) -> None:
        game = create_game()
        card = _prepared_card_on_battlefield(game, 0)
        copy = preparation.mark_prepared(game, card)
        assert copy.mana_cost == ManaCost.parse("{W}")

    def test_copy_keyed_to_prepared_permanent(self) -> None:
        game = create_game()
        card = _prepared_card_on_battlefield(game, 0)
        copy = preparation.mark_prepared(game, card)
        # The registry round-trips the permanent -> copy mapping.
        assert preparation.get_prepared_copy(game, card) is copy
        # And the per-game registry is keyed by the prepared permanent's id.
        assert game._prepared_copies[id(card)] is copy

    def test_copy_controlled_by_prepared_controller(self) -> None:
        """The copy is owned and controlled by the prepared permanent's
        controller (so it lands in *that* player's exile)."""
        game = create_game()
        card = _prepared_card_on_battlefield(game, 0)
        p1 = game.players[0]
        p2 = game.players[1]
        copy = preparation.mark_prepared(game, card)
        assert copy.controller is p1
        assert copy.owner is p1
        # The opponent's exile does not receive a copy.
        assert not game.get_exile(p2).contains(copy)

    def test_etb_prepared_branch_creates_exile_copy(self) -> None:
        """Going through the real ETB (opponent has strictly more creatures)
        also produces the exile copy — not just a direct mark_prepared call."""
        game = create_game()
        card = _make_etb_card(game, 0)
        p1 = game.players[0]
        p2 = game.players[1]
        set_board_state(game, 0, battlefield=[card])
        set_board_state(
            game,
            1,
            battlefield=[
                _vanilla_creature("Foe A"),
                _vanilla_creature("Foe B"),
                _vanilla_creature("Foe C"),
            ],
        )
        game.trigger_manager.unregister(card)
        card.register_triggers(game)
        _fire_etb(game, card, p2)
        assert preparation.is_prepared(card) is True
        copy = preparation.get_prepared_copy(game, card)
        assert copy is not None
        assert isinstance(copy, SwordsToPlowshares)
        assert game.get_exile(p1).contains(copy)


class TestPreparationIdempotencyAndUnprepare:
    """(4) Edge cases: mark_prepared idempotency, and unprepare removes the
    exiled copy and clears the designation."""

    def test_mark_prepared_is_idempotent(self) -> None:
        game = create_game()
        card = _prepared_card_on_battlefield(game, 0)
        p1 = game.players[0]
        first = preparation.mark_prepared(game, card)
        # A second mark must not create a duplicate (CR 722.3a) — same copy back.
        second = preparation.mark_prepared(game, card)
        assert second is first
        exile_copies = [
            obj
            for obj in game.get_exile(p1).get_all()
            if isinstance(obj, SwordsToPlowshares)
        ]
        assert len(exile_copies) == 1

    def test_unprepare_clears_designation(self) -> None:
        game = create_game()
        card = _prepared_card_on_battlefield(game, 0)
        preparation.mark_prepared(game, card)
        assert preparation.is_prepared(card) is True
        preparation.unprepare(game, card)
        assert preparation.is_prepared(card) is False

    def test_unprepare_removes_exile_copy(self) -> None:
        game = create_game()
        card = _prepared_card_on_battlefield(game, 0)
        p1 = game.players[0]
        copy = preparation.mark_prepared(game, card)
        assert game.get_exile(p1).contains(copy)
        preparation.unprepare(game, card)
        # The copy only persists while prepared (CR 722.3c).
        assert not game.get_exile(p1).contains(copy)
        assert preparation.get_prepared_copy(game, card) is None


class TestPreparationCastFromExile:
    """(2) The controller casts the exiled copy; doing so unprepares the source
    and moves the copy out of exile onto the stack."""

    def test_cast_from_exile_unprepares_source(self) -> None:
        # Give the controller a creature to target so cast_prepared_copy's
        # target choice succeeds.
        victim = _vanilla_creature("Victim")
        game = create_game(scripts=([victim], []))
        card = _prepared_card_on_battlefield(game, 0)
        p1 = game.players[0]
        # Put the target creature on the battlefield (under the controller).
        set_board_state(game, 0, battlefield=[card, victim])
        card.owner = p1
        card.controller = p1
        copy = preparation.mark_prepared(game, card)
        assert preparation.is_prepared(card) is True

        preparation.cast_prepared_copy(game, p1, copy)
        # Casting the copy clears the prepared designation (CR 722.3c).
        assert preparation.is_prepared(card) is False

    def test_cast_from_exile_moves_copy_off_exile(self) -> None:
        victim = _vanilla_creature("Victim")
        game = create_game(scripts=([victim], []))
        card = _prepared_card_on_battlefield(game, 0)
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[card, victim])
        card.owner = p1
        card.controller = p1
        copy = preparation.mark_prepared(game, card)
        assert game.get_exile(p1).contains(copy)

        preparation.cast_prepared_copy(game, p1, copy)
        # The copy left exile (it is now on the stack).
        assert not game.get_exile(p1).contains(copy)
        assert not game.stack.is_empty()
        assert game.stack.peek().source is copy

    def test_cast_from_exile_clears_registry_entry(self) -> None:
        victim = _vanilla_creature("Victim")
        game = create_game(scripts=([victim], []))
        card = _prepared_card_on_battlefield(game, 0)
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[card, victim])
        card.owner = p1
        card.controller = p1
        copy = preparation.mark_prepared(game, card)

        preparation.cast_prepared_copy(game, p1, copy)
        # The source is no longer tracked as having a prepared copy.
        assert preparation.get_prepared_copy(game, card) is None


class TestSwordsToPlowsharesEffect:
    """(3) Resolving the prepare spell exiles the target creature and gives its
    controller life equal to the creature's power."""

    def test_resolved_swords_exiles_target_creature(self) -> None:
        victim = _vanilla_creature("Victim")  # 2/2
        game = create_game(scripts=([victim], []))
        card = _prepared_card_on_battlefield(game, 0)
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[card, victim])
        card.owner = p1
        card.controller = p1
        copy = preparation.mark_prepared(game, card)

        preparation.cast_prepared_copy(game, p1, copy)
        _resolve_full_stack(game)

        # The creature is off the battlefield and in its owner's exile.
        assert not game.get_battlefield(p1).contains(victim)
        assert game.get_exile(p1).contains(victim)

    def test_resolved_swords_controller_gains_life_equal_to_power(self) -> None:
        victim = _vanilla_creature("Victim")  # base power 2
        game = create_game(scripts=([victim], []))
        card = _prepared_card_on_battlefield(game, 0)
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[card, victim], life=20)
        card.owner = p1
        card.controller = p1
        copy = preparation.mark_prepared(game, card)
        life_before = p1.life

        preparation.cast_prepared_copy(game, p1, copy)
        _resolve_full_stack(game)

        # Its controller (p1, who controls the 2-power Victim) gains 2 life.
        assert p1.life == life_before + 2

    def test_swords_life_goes_to_targets_controller_not_caster(self) -> None:
        """"Its controller gains life" — the life goes to the target creature's
        controller, which may be an opponent, not the spell's caster."""
        foe_creature = _vanilla_creature("Foe Bear")  # power 2, controlled by p2
        game = create_game(scripts=([foe_creature], []))
        card = _prepared_card_on_battlefield(game, 0)
        p1 = game.players[0]
        p2 = game.players[1]
        set_board_state(game, 0, battlefield=[card], life=20)
        set_board_state(game, 1, battlefield=[foe_creature], life=20)
        foe_creature.owner = p2
        foe_creature.controller = p2
        copy = preparation.mark_prepared(game, card)
        p1_life_before = p1.life
        p2_life_before = p2.life

        # p1 casts the copy targeting the opponent's creature.
        preparation.cast_prepared_copy(game, p1, copy)
        _resolve_full_stack(game)

        # The creature is exiled to its owner's (p2) exile.
        assert not game.get_battlefield(p2).contains(foe_creature)
        assert game.get_exile(p2).contains(foe_creature)
        # Its controller (p2) gains the life, not the caster (p1).
        assert p2.life == p2_life_before + 2
        assert p1.life == p1_life_before


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
