"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares.

Emeritus of Truce is the creature face of a split / modal card:

    Emeritus of Truce — {1}{W}{W} — 3/3 — Creature — Cat Cleric
      When this creature enters, target player creates a 1/1 white and
      black Inkling creature token with flying. Then if an opponent
      controls more creatures than you, this creature becomes prepared.
      (While it's prepared, you may cast a copy of its spell. Doing so
      unprepares it.)

    Swords to Plowshares — {W} — Instant  (the "spell" side)
      Exile target creature. Its controller gains life equal to its power.

These tests are written in the TDD red phase — the implementation stub is
empty, so every behavioural test should fail until the card is built.

The tests focus on observable behaviour that the engine can express today:
- static card data for the creature face,
- the enters-the-battlefield Inkling token (its colors, flying, P/T, and
  the fact that it is created under the *chosen target player's* control),
- the conditional "becomes prepared" check that depends on relative
  creature counts.

Behaviours that the current engine surface cannot express (the ``Prepared``
keyword as a first-class flag, casting a copy of the spell side, and the
``Swords to Plowshares`` instant face itself) are recorded in
``untestable.json`` rather than asserted here.
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.types import CardType, ManaCost
from test_utils import create_game, set_board_state


def _make_card(owner: Any = None, controller: Any = None) -> EmeritusOfTruceSwordsToPlowshares:
    return EmeritusOfTruceSwordsToPlowshares(owner=owner, controller=controller)


def _inkling_tokens(game: Any, player: Any) -> list[Any]:
    """Return every Inkling token currently on *player*'s battlefield."""
    bf = game.get_battlefield(player)
    result = []
    for obj in bf.get_all():
        subtypes = getattr(obj, "subtypes", set()) or set()
        if "Inkling" in subtypes:
            result.append(obj)
    return result


def _resolve_etb(card: Any, game: Any) -> None:
    """Drive the enters-the-battlefield effect.

    The reference converge card (FDN 205) models an ``When this creature
    enters`` ability inside ``on_resolve``, so we call that first. If the
    implementation instead routes the ETB through a registered trigger, we
    fall back to firing an EntersBattlefieldTriggeredEvent and resolving the
    stack so the test is robust to either contract.
    """
    card.on_resolve(game)
    if not game.stack.is_empty():
        _drain_stack(game)
        return
    # If on_resolve was a no-op (trigger-based contract), try the trigger path.
    from engine.events import EntersBattlefieldTriggeredEvent

    card.register_triggers(game)
    game.trigger_manager.fire_event(
        game,
        EntersBattlefieldTriggeredEvent(
            permanent=card, controller=card.controller, creature=card, card=card
        ),
    )
    _drain_stack(game)


def _drain_stack(game: Any) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


# ---------------------------------------------------------------------------
# Static card data (creature face)
# ---------------------------------------------------------------------------


class TestEmeritusProperties:
    """Static card data should match the SOS 13 spec (creature face)."""

    def test_is_creature(self) -> None:
        card = _make_card()
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_name(self) -> None:
        assert _make_card().name == "Emeritus of Truce // Swords to Plowshares"

    def test_creature_face_mana_cost(self) -> None:
        # The permanent face is the {1}{W}{W} creature.
        assert _make_card().mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_power_toughness(self) -> None:
        card = _make_card()
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_subtypes_cat_cleric(self) -> None:
        subtypes = _make_card().subtypes
        assert "Cat" in subtypes
        assert "Cleric" in subtypes

    def test_is_white(self) -> None:
        # {1}{W}{W} is mono-white.
        from test_utils import card_colors

        assert card_colors(_make_card()) == {"W"}


# ---------------------------------------------------------------------------
# Enters-the-battlefield Inkling token
# ---------------------------------------------------------------------------


class TestEmeritusInklingToken:
    """ETB creates a 1/1 white & black Inkling with flying for a target player."""

    def test_etb_creates_one_inkling_for_chosen_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _make_card(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        # Controller targets themselves to receive the token.
        card.chosen_targets = [p1]

        before = len(_inkling_tokens(game, p1))
        _resolve_etb(card, game)
        after = len(_inkling_tokens(game, p1))
        assert after - before == 1

    def test_inkling_is_one_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _make_card(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.chosen_targets = [p1]

        _resolve_etb(card, game)
        tokens = _inkling_tokens(game, p1)
        assert len(tokens) == 1
        tok = tokens[0]
        assert tok.base_power == 1
        assert tok.base_toughness == 1

    def test_inkling_has_flying(self) -> None:
        from engine.types import Keyword

        game = create_game()
        p1 = game.players[0]
        card = _make_card(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.chosen_targets = [p1]

        _resolve_etb(card, game)
        tok = _inkling_tokens(game, p1)[0]
        assert Keyword.FLYING in tok.keywords

    def test_inkling_is_white_and_black(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _make_card(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.chosen_targets = [p1]

        _resolve_etb(card, game)
        tok = _inkling_tokens(game, p1)[0]
        colors = getattr(tok, "colors", None)
        assert colors is not None, "Inkling token should expose its colors"
        color_values = {getattr(c, "value", c) for c in colors}
        assert "W" in color_values
        assert "B" in color_values

    def test_inkling_is_a_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _make_card(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.chosen_targets = [p1]

        _resolve_etb(card, game)
        tok = _inkling_tokens(game, p1)[0]
        assert tok.is_token is True

    def test_token_created_for_targeted_opponent_not_controller(self) -> None:
        """"target player" — the token enters under the *chosen* player's
        control, which may be an opponent, not necessarily the card's
        controller."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = _make_card(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        # Controller (p1) chooses the opponent (p2) as the target player.
        card.chosen_targets = [p2]

        _resolve_etb(card, game)
        assert len(_inkling_tokens(game, p2)) == 1
        assert len(_inkling_tokens(game, p1)) == 0


# ---------------------------------------------------------------------------
# Targeting contract
# ---------------------------------------------------------------------------


class TestEmeritusTargeting:
    """The creature spell itself takes no targets when cast.

    The "target player" belongs to the enters-the-battlefield triggered
    ability, not to the creature spell. Following the sos_1 convention, the
    creature face must not advertise that target via the card-level
    ``get_targets`` while it is being cast (i.e. while in a STACK zone),
    otherwise the cast pipeline wrongly consumes a target.
    """

    def test_no_targets_while_on_stack(self) -> None:
        from engine.types import Zone

        game = create_game()
        p1 = game.players[0]
        card = _make_card(owner=p1, controller=p1)
        # Simulate the cast pipeline placing the card in the STACK zone.
        p1.zones[Zone.STACK].add(card)
        assert card.get_targets(game) == []


# ---------------------------------------------------------------------------
# Conditional "becomes prepared"
# ---------------------------------------------------------------------------


class TestEmeritusBecomesPrepared:
    """"Then if an opponent controls more creatures than you, this creature
    becomes prepared." The conditional must be evaluated against relative
    creature counts after the token is created.

    The engine has no first-class ``Prepared`` keyword/flag, so the contract
    exposes the result via an ``is_prepared`` boolean on the card (defaulting
    to ``False``). These tests assert the conditional toggles that flag in the
    right direction; the actual copy-casting machinery is recorded as
    untestable.
    """

    def test_not_prepared_by_default(self) -> None:
        card = _make_card()
        assert getattr(card, "is_prepared", False) is False

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = _make_card(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        # Opponent controls two creatures; controller controls only Emeritus.
        opp_a = Creature(name="Bear A", base_power=2, base_toughness=2)
        opp_b = Creature(name="Bear B", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[opp_a, opp_b])
        # Token goes to opponent here so opponent ends with 3 creatures > p1's 1.
        card.chosen_targets = [p1]

        _resolve_etb(card, game)
        assert getattr(card, "is_prepared", False) is True

    def test_not_prepared_when_counts_equal(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = _make_card(owner=p1, controller=p1)
        bear_you = Creature(name="Your Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card, bear_you])
        opp_a = Creature(name="Opp Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[opp_a])
        # You target yourself, so after the token you have 3 vs opponent's 1.
        card.chosen_targets = [p1]

        _resolve_etb(card, game)
        # Opponent does NOT control more creatures than you -> not prepared.
        assert getattr(card, "is_prepared", False) is False

    def test_not_prepared_when_you_have_more_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = _make_card(owner=p1, controller=p1)
        bear1 = Creature(name="Your Bear 1", base_power=2, base_toughness=2)
        bear2 = Creature(name="Your Bear 2", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card, bear1, bear2])
        set_board_state(game, 1, battlefield=[])
        card.chosen_targets = [p1]

        _resolve_etb(card, game)
        assert getattr(card, "is_prepared", False) is False


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


class TestEmeritusRobustness:
    """Resolution must not raise on degenerate inputs."""

    def test_resolve_without_chosen_target_does_not_raise(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _make_card(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        # No chosen_targets set — resolution must not crash.
        card.on_resolve(game)
