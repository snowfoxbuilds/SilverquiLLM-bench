"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares.

This is a *preparation card* (rule 722): a two-part card whose front face is
the creature **Emeritus of Truce** ({1}{W}{W}, 3/3 Cat Cleric) and whose inset
"prepare spell" is **Swords to Plowshares** ({W} instant — exile a creature,
its controller gains life equal to its power).

Front-face oracle text:
    "When this creature enters, target player creates a 1/1 white and black
     Inkling creature token with flying. Then if an opponent controls more
     creatures than you, this creature becomes prepared."

The engine has no native "Prepared" designation or preparation-card frame, so
the implementation has latitude on *how* it represents the prepared state and
the prepare spell.  These tests therefore probe *observable behaviour*:

  * the creature's printed characteristics,
  * the ETB token (a 1/1 white-and-black Inkling with flying) appearing under
    the chosen target player's control,
  * the conditional "becomes prepared" designation based on the
    opponent-controls-more-creatures comparison,
  * the prepare spell exiling a creature and granting its controller life.

Where a clause cannot be asserted against the current engine surface, it is
recorded in ``untestable.json`` instead of being silently skipped.
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_card(game: Any, controller_index: int = 0) -> EmeritusOfTruceSwordsToPlowshares:
    """Build the card owned/controlled by the given player and return it."""
    player = game.players[controller_index]
    card = EmeritusOfTruceSwordsToPlowshares(owner=player, controller=player)
    return card


def _battlefield_creatures(game: Any, player: Any) -> list[Any]:
    """Return Creature objects on *player*'s battlefield."""
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if isinstance(obj, Creature)
    ]


def _inkling_tokens(game: Any, player: Any) -> list[Any]:
    """Return token creatures named 'Inkling' on *player*'s battlefield."""
    out = []
    for obj in _battlefield_creatures(game, player):
        name = getattr(obj, "name", "")
        subtypes = getattr(obj, "subtypes", set())
        if "Inkling" in name or "Inkling" in subtypes:
            out.append(obj)
    return out


def _fire_etb(game: Any, card: Any, target_player: Any) -> None:
    """Resolve the card's enter-the-battlefield effect.

    The card is placed on its controller's battlefield first (so SBA / zone
    checks see it), then its ETB is driven through whichever surface the
    implementation exposes.  ``chosen_targets`` is set to the target player,
    matching the engine's resolve-time contract for targeted effects.
    """
    controller = card.controller
    game.get_battlefield(controller).add(card)
    card.chosen_targets = [target_player]

    # Preferred path: register the ETB trigger, then fire the ETB event and
    # resolve the resulting stack object.
    from engine.events import EntersBattlefieldTriggeredEvent

    if hasattr(card, "register_triggers"):
        card.register_triggers(game)
    fired = False
    try:
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(
                permanent=card, controller=controller, creature=card
            ),
        )
    except Exception:
        fired = False
    else:
        fired = not game.stack.is_empty()

    if fired:
        # Resolve all triggered abilities on the stack.
        while not game.stack.is_empty():
            obj = game.stack.pop()
            # Make the target player available to the resolving ability.
            if hasattr(obj, "targets") and not getattr(obj, "targets", None):
                obj.targets = [target_player]
            card.chosen_targets = [target_player]
            obj.on_resolve(game)
        return

    # Fallback path: the implementation may expose the ETB as on_resolve.
    card.chosen_targets = [target_player]
    card.on_resolve(game)


# ---------------------------------------------------------------------------
# Static characteristics of the front face (Emeritus of Truce)
# ---------------------------------------------------------------------------


class TestEmeritusProperties:
    """The front face is a 3/3 white Cat Cleric costing {1}{W}{W}."""

    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"

    def test_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_power_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_creature_subtypes(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert {"Cat", "Cleric"} <= card.subtypes

    def test_is_white(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "W" in getattr(card, "colors", [])


# ---------------------------------------------------------------------------
# ETB trigger registration
# ---------------------------------------------------------------------------


class TestEmeritusEtbRegistration:
    """The creature registers an enters-the-battlefield triggered ability."""

    def test_register_triggers_adds_etb(self) -> None:
        from engine.events import EntersBattlefieldTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        card = _make_card(game, 0)
        game.get_battlefield(p1).add(card)
        before = len(game.trigger_manager.get_triggers_for_source(card))
        card.register_triggers(game)
        after = game.trigger_manager.get_triggers_for_source(card)
        assert len(after) - before == 1
        assert after[-1].event_type is EntersBattlefieldTriggeredEvent


# ---------------------------------------------------------------------------
# ETB effect — token creation for the target player
# ---------------------------------------------------------------------------


class TestEmeritusTokenCreation:
    """ETB: target player creates a 1/1 white-and-black Inkling with flying."""

    def test_target_player_gets_one_token(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = _make_card(game, 0)
        before = len(_inkling_tokens(game, p2))
        _fire_etb(game, card, target_player=p2)
        after = len(_inkling_tokens(game, p2))
        assert after - before == 1

    def test_token_goes_to_chosen_player_not_caster(self) -> None:
        """When the controller targets the opponent, the caster gets no token."""
        game = create_game()
        p1, p2 = game.players
        card = _make_card(game, 0)
        _fire_etb(game, card, target_player=p2)
        # The opponent received exactly the Inkling token; the caster got none.
        assert len(_inkling_tokens(game, p2)) == 1
        assert len(_inkling_tokens(game, p1)) == 0

    def test_controller_may_target_self(self) -> None:
        """The controller is a legal 'target player' and may receive the token."""
        game = create_game()
        p1, _ = game.players
        card = _make_card(game, 0)
        _fire_etb(game, card, target_player=p1)
        assert len(_inkling_tokens(game, p1)) == 1

    def test_token_is_one_one(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = _make_card(game, 0)
        _fire_etb(game, card, target_player=p2)
        tokens = _inkling_tokens(game, p2)
        assert len(tokens) == 1
        tok = tokens[0]
        assert tok.base_power == 1
        assert tok.base_toughness == 1

    def test_token_has_flying(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = _make_card(game, 0)
        _fire_etb(game, card, target_player=p2)
        tok = _inkling_tokens(game, p2)[0]
        assert Keyword.FLYING in getattr(tok, "keywords", Keyword(0))

    def test_token_is_white_and_black(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = _make_card(game, 0)
        _fire_etb(game, card, target_player=p2)
        tok = _inkling_tokens(game, p2)[0]
        colors = set(getattr(tok, "colors", []))
        assert "W" in colors
        assert "B" in colors

    def test_token_is_an_inkling(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = _make_card(game, 0)
        _fire_etb(game, card, target_player=p2)
        tok = _inkling_tokens(game, p2)[0]
        assert "Inkling" in getattr(tok, "subtypes", set())

    def test_token_is_marked_as_token(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = _make_card(game, 0)
        _fire_etb(game, card, target_player=p2)
        tok = _inkling_tokens(game, p2)[0]
        assert getattr(tok, "is_token", False) is True


# ---------------------------------------------------------------------------
# ETB second clause — "becomes prepared" conditional
# ---------------------------------------------------------------------------


class TestEmeritusBecomesPrepared:
    """"Then if an opponent controls more creatures than you, this creature
    becomes prepared." — comparison is creature counts on the battlefield."""

    @staticmethod
    def _is_prepared(card: Any) -> bool:
        """Best-effort read of the 'prepared' designation."""
        return bool(getattr(card, "prepared", False) or getattr(card, "is_prepared", False))

    def _bears(self, n: int) -> list[Creature]:
        return [
            Creature(name=f"Bear{i}", base_power=2, base_toughness=2)
            for i in range(n)
        ]

    def test_prepared_when_opponent_has_more_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = _make_card(game, 0)
        # STANDARD MTG counting: the entering Emeritus counts toward its
        # controller, and the Inkling token counts for whoever controls it.
        # Target the token to the CONTROLLER (p1) so it counts toward "you":
        # controller ends with Emeritus + token = 2, opponent has 3 bears = 3.
        # 3 > 2 -> opponent strictly more -> prepared.
        for b in self._bears(3):
            b.owner = p2
            b.controller = p2
            game.get_battlefield(p2).add(b)
        _fire_etb(game, card, target_player=p1)
        # The token was created before the comparison and went to the
        # controller (counts toward "you"); the opponent still has strictly
        # more creatures, so the creature becomes prepared.
        assert len(_inkling_tokens(game, p1)) == 1
        assert self._is_prepared(card) is True

    def test_not_prepared_when_counts_equal(self) -> None:
        """Strictly 'more than' — equal creature counts must NOT prepare it."""
        game = create_game()
        p1, p2 = game.players
        card = _make_card(game, 0)
        # After ETB the controller has Emeritus (1). Give opponent exactly 1 so
        # that, counting Emeritus, neither side has *more* than the other.
        b = self._bears(1)[0]
        b.owner = p2
        b.controller = p2
        game.get_battlefield(p2).add(b)
        # Target self so the token does not change the opponent's count.
        _fire_etb(game, card, target_player=p1)
        # The ETB must still have created the token (guards against a no-op
        # implementation trivially "passing" this negative assertion).
        assert len(_inkling_tokens(game, p1)) == 1
        assert self._is_prepared(card) is False

    def test_not_prepared_when_controller_has_more(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = _make_card(game, 0)
        # Controller has extra creatures; opponent has none.
        for b in self._bears(2):
            b.owner = p1
            b.controller = p1
            game.get_battlefield(p1).add(b)
        _fire_etb(game, card, target_player=p1)
        # The ETB must still have created the token (guards against a no-op
        # implementation trivially "passing" this negative assertion).
        assert len(_inkling_tokens(game, p1)) == 1
        assert self._is_prepared(card) is False

    def test_token_under_opponent_can_flip_the_comparison(self) -> None:
        """The token is created *before* the comparison; if it goes to the
        opponent it counts toward the opponent's creature total."""
        game = create_game()
        p1, p2 = game.players
        card = _make_card(game, 0)
        # Opponent starts with 1 creature; controller has only Emeritus (1).
        b = self._bears(1)[0]
        b.owner = p2
        b.controller = p2
        game.get_battlefield(p2).add(b)
        # Token goes to the opponent -> opponent ends with 2, controller with 1.
        _fire_etb(game, card, target_player=p2)
        assert self._is_prepared(card) is True


# ---------------------------------------------------------------------------
# Prepare spell — Swords to Plowshares
# ---------------------------------------------------------------------------


class TestSwordsToPlowshares:
    """The inset prepare spell exiles a creature; its controller gains life
    equal to that creature's power."""

    @staticmethod
    def _make_prepare_spell(game: Any, controller: Any) -> Any:
        """Obtain a castable copy of the Swords to Plowshares prepare spell.

        The card exposes a stable ``make_prepare_spell(game)`` factory (see the
        coordinator directives / card_impl docstring), so this is now a HARD
        contract: the factory must exist, be callable, and return a spell
        object.  No skip path.
        """
        card = EmeritusOfTruceSwordsToPlowshares(owner=controller, controller=controller)
        factory = getattr(card, "make_prepare_spell", None)
        assert callable(factory), (
            "Card must expose a callable make_prepare_spell(game) factory "
            "for the inset Swords to Plowshares prepare spell."
        )
        spell = factory(game)
        assert spell is not None, "make_prepare_spell(game) must return a spell object."
        spell.owner = controller
        spell.controller = controller
        return spell

    def test_exiles_target_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = self._make_prepare_spell(game, p1)
        victim = Creature(
            name="Doomed Bear", owner=p2, controller=p2, base_power=2, base_toughness=2
        )
        game.get_battlefield(p2).add(victim)
        spell.chosen_targets = [victim]
        spell.on_resolve(game)
        assert not game.get_battlefield(p2).contains(victim)
        assert p2.zones[Zone.EXILE].contains(victim)

    def test_controller_gains_life_equal_to_power(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = self._make_prepare_spell(game, p1)
        victim = Creature(
            name="Big Beast", owner=p2, controller=p2, base_power=5, base_toughness=5
        )
        game.get_battlefield(p2).add(victim)
        before = p2.life
        spell.chosen_targets = [victim]
        spell.on_resolve(game)
        # The exiled creature's CONTROLLER (p2), not the caster, gains the life.
        assert p2.life == before + 5

    def test_caster_does_not_gain_life_for_opponents_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = self._make_prepare_spell(game, p1)
        victim = Creature(
            name="Big Beast", owner=p2, controller=p2, base_power=4, base_toughness=4
        )
        game.get_battlefield(p2).add(victim)
        before_caster = p1.life
        spell.chosen_targets = [victim]
        spell.on_resolve(game)
        assert p1.life == before_caster

    def test_no_target_is_a_noop(self) -> None:
        game = create_game()
        p1, _ = game.players
        spell = self._make_prepare_spell(game, p1)
        # No chosen_targets set — resolution must not raise or change life.
        before = p1.life
        spell.on_resolve(game)
        assert p1.life == before


# ---------------------------------------------------------------------------
# Casting the prepare spell while prepared — unprepare transition (CR 722.3c)
# ---------------------------------------------------------------------------


class TestCastPrepareSpellUnprepares:
    """"While it's prepared, you may cast a copy of its spell. Doing so
    unprepares it." (CR 722.3c)

    The card exposes ``cast_prepare_spell(game, target=...)`` which (a) requires
    the creature to be prepared, (b) free-casts/resolves a copy of Swords to
    Plowshares against the target, and (c) clears the prepared designation.
    """

    def test_cast_while_prepared_exiles_grants_life_and_unprepares(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = _make_card(game, 0)
        game.get_battlefield(p1).add(card)
        # Prepare the creature directly (the becomes-prepared path is covered
        # elsewhere; here we exercise the cast/unprepare transition in isolation).
        card.prepared = True

        victim = Creature(
            name="Plowed Beast", owner=p2, controller=p2, base_power=3, base_toughness=3
        )
        game.get_battlefield(p2).add(victim)
        before = p2.life

        card.cast_prepare_spell(game, target=victim)

        # (a) The target creature is exiled and ITS controller (p2) gains life
        #     equal to its power.
        assert not game.get_battlefield(p2).contains(victim)
        assert p2.zones[Zone.EXILE].contains(victim)
        assert p2.life == before + 3
        # (b) Casting the prepare spell unprepares the permanent (CR 722.3c).
        assert card.prepared is False

    def test_cast_when_not_prepared_is_rejected(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = _make_card(game, 0)
        game.get_battlefield(p1).add(card)
        # The creature is NOT prepared.
        assert card.prepared is False

        victim = Creature(
            name="Safe Beast", owner=p2, controller=p2, base_power=2, base_toughness=2
        )
        game.get_battlefield(p2).add(victim)
        before = p2.life

        # Casting the prepare spell while not prepared must be rejected.
        with pytest.raises(ValueError):
            card.cast_prepare_spell(game, target=victim)

        # The rejected attempt must not have exiled the creature or moved life.
        assert game.get_battlefield(p2).contains(victim)
        assert p2.life == before
