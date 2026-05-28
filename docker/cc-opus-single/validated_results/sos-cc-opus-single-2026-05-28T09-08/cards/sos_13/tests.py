"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares.

Emeritus of Truce is a {1}{W}{W} Creature — Cat Cleric (3/3) with Prepared.

Oracle text:
  When this creature enters, target player creates a 1/1 white and black
  Inkling creature token with flying. Then if an opponent controls more
  creatures than you, this creature becomes prepared.
  (While it's prepared, you may cast a copy of its spell. Doing so
  unprepares it.)

The prepare spell is Swords to Plowshares ({W} Instant).

Requirements tested:
1. Static properties: name, mana cost, power/toughness, types, subtypes.
2. Is a Creature.
3. ETB trigger: registers a trigger on EntersBattlefieldTriggeredEvent.
4. ETB targeting: get_targets returns a target requirement for a player.
5. Token creation: target player gets a 1/1 white and black Inkling creature
   token with flying.
6. Prepared condition: becomes prepared if an opponent controls more creatures.
7. Does NOT become prepared if opponent has same or fewer creatures.
8. Edge cases: no chosen target, self-targeting, opponent targeting.
"""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature, Instant
from engine.events import EntersBattlefieldTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestEmeritusOfTruceProperties:
    """Static card data should match the SOS 13 spec."""

    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce"

    def test_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_power_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_has_creature_type(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_has_cat_cleric_subtypes(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes


# ---------------------------------------------------------------------------
# ETB trigger — registration
# ---------------------------------------------------------------------------


class TestEmeritusOfTruceETBTriggerRegistration:
    """When this creature enters, the ETB trigger should be registered."""

    def test_registers_etb_trigger(self) -> None:
        """register_triggers should register at least one
        EntersBattlefieldTriggeredEvent trigger."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        before_count = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after_count = len(game.trigger_manager.get_triggers())

        assert after_count > before_count

    def test_registered_trigger_watches_etb_event(self) -> None:
        """The registered trigger should watch for
        EntersBattlefieldTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_triggers = [
            t for t in triggers
            if t.event_type is EntersBattlefieldTriggeredEvent
        ]
        assert len(etb_triggers) >= 1

    def test_trigger_condition_matches_self_entering(self) -> None:
        """The trigger condition should match when this creature enters."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_triggers = [
            t for t in triggers
            if t.event_type is EntersBattlefieldTriggeredEvent
        ]
        assert len(etb_triggers) >= 1

        event = EntersBattlefieldTriggeredEvent(
            permanent=card, controller=p1
        )
        trigger = etb_triggers[0]
        if trigger.condition is not None:
            assert trigger.condition(game, event) is True

    def test_trigger_condition_does_not_match_other_permanent(self) -> None:
        """The trigger should NOT fire when a different permanent enters."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        other = Creature(
            name="Other Creature", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )

        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_triggers = [
            t for t in triggers
            if t.event_type is EntersBattlefieldTriggeredEvent
        ]
        assert len(etb_triggers) >= 1

        event = EntersBattlefieldTriggeredEvent(
            permanent=other, controller=p1
        )
        trigger = etb_triggers[0]
        if trigger.condition is not None:
            assert trigger.condition(game, event) is False


# ---------------------------------------------------------------------------
# ETB targeting — target player
# ---------------------------------------------------------------------------


class TestEmeritusOfTruceTargeting:
    """get_targets() should advertise a target requirement for a player."""

    def test_returns_at_least_one_target_requirement(self) -> None:
        game = create_game()
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) >= 1

    def test_target_requirement_is_valid_type(self) -> None:
        game = create_game()
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        reqs = card.get_targets(game)
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_accepts_player(self) -> None:
        """The target requirement should accept a player object."""
        game = create_game()
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        reqs = card.get_targets(game)
        req = reqs[0]
        assert req.filter_fn(game.players[0]) is True
        assert req.filter_fn(game.players[1]) is True


# ---------------------------------------------------------------------------
# Token creation — Inkling token properties
# ---------------------------------------------------------------------------


class TestEmeritusOfTruceTokenCreation:
    """When the ETB trigger resolves, the target player creates a 1/1
    white and black Inkling creature token with flying."""

    def test_target_player_gets_token(self) -> None:
        """The targeted player should receive one creature token on the
        battlefield."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        bf_before = len(game.get_battlefield(p2).get_all())

        # Simulate the ETB trigger resolving with p2 as the target.
        card.chosen_targets = [p2]
        card.on_resolve(game)

        bf_after = len(game.get_battlefield(p2).get_all())
        assert bf_after - bf_before == 1, \
            "Target player should receive exactly one token"

    def test_token_is_creature(self) -> None:
        """The created token should be a Creature."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.chosen_targets = [p2]
        card.on_resolve(game)

        tokens = [
            obj for obj in game.get_battlefield(p2).get_all()
            if isinstance(obj, Creature) and getattr(obj, "is_token", False)
        ]
        assert len(tokens) >= 1, "Expected at least one creature token"

    def test_token_is_inkling(self) -> None:
        """The token should have the Inkling creature subtype."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.chosen_targets = [p2]
        card.on_resolve(game)

        tokens = [
            obj for obj in game.get_battlefield(p2).get_all()
            if isinstance(obj, Creature) and getattr(obj, "is_token", False)
        ]
        assert len(tokens) >= 1
        token = tokens[0]
        assert "Inkling" in getattr(token, "subtypes", set()), \
            "Token should have Inkling subtype"

    def test_token_power_toughness(self) -> None:
        """The token should be 1/1."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.chosen_targets = [p2]
        card.on_resolve(game)

        tokens = [
            obj for obj in game.get_battlefield(p2).get_all()
            if isinstance(obj, Creature) and getattr(obj, "is_token", False)
        ]
        assert len(tokens) >= 1
        token = tokens[0]
        assert token.base_power == 1
        assert token.base_toughness == 1

    def test_token_has_flying(self) -> None:
        """The token should have the flying keyword."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.chosen_targets = [p2]
        card.on_resolve(game)

        tokens = [
            obj for obj in game.get_battlefield(p2).get_all()
            if isinstance(obj, Creature) and getattr(obj, "is_token", False)
        ]
        assert len(tokens) >= 1
        token = tokens[0]
        assert Keyword.FLYING in token.keywords, \
            "Token should have flying"

    def test_controller_can_target_self_for_token(self) -> None:
        """The controller can target themselves to receive the token."""
        game = create_game()
        p1 = game.players[0]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        bf_before = len(game.get_battlefield(p1).get_all())

        card.chosen_targets = [p1]
        card.on_resolve(game)

        bf_after = len(game.get_battlefield(p1).get_all())
        # The Emeritus itself + 1 token
        assert bf_after - bf_before == 1, \
            "Controller should get exactly one token when targeting self"


# ---------------------------------------------------------------------------
# Prepared condition — opponent controls more creatures
# ---------------------------------------------------------------------------


class TestEmeritusOfTrucePreparedCondition:
    """After the token is created, if an opponent controls more creatures
    than you, this creature becomes prepared."""

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        """When opponent controls more creatures than the controller,
        Emeritus should become prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # Opponent has several creatures
        for i in range(3):
            bear = Creature(
                name=f"Bear{i}", owner=p2, controller=p2,
                base_power=2, base_toughness=2,
            )
            game.get_battlefield(p2).add(bear)

        # Target opponent for the token (they get +1 creature, doesn't help us)
        # P1 has: Emeritus (1 creature)
        # P2 has: 3 bears + 1 token = 4 creatures
        card.chosen_targets = [p2]
        card.on_resolve(game)

        assert getattr(card, "is_prepared", False) is True, \
            "Emeritus should be prepared when opponent has more creatures"

    def test_not_prepared_when_controller_has_equal_creatures(self) -> None:
        """When controller has equal or more creatures, should NOT become
        prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # P1 also has another creature
        extra = Creature(
            name="Extra", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        game.get_battlefield(p1).add(extra)

        # P2 has 1 creature
        opp_bear = Creature(
            name="Opp Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        game.get_battlefield(p2).add(opp_bear)

        # Target self — P1 gets the token
        # P1: Emeritus + Extra + Token = 3
        # P2: Opp Bear = 1
        card.chosen_targets = [p1]
        card.on_resolve(game)

        assert getattr(card, "is_prepared", False) is False, \
            "Emeritus should NOT be prepared when controller has >= creatures"

    def test_not_prepared_when_controller_has_more_creatures(self) -> None:
        """Definitely not prepared when controller has strictly more."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # Add more creatures for p1
        for i in range(3):
            extra = Creature(
                name=f"P1Creature{i}", owner=p1, controller=p1,
                base_power=2, base_toughness=2,
            )
            game.get_battlefield(p1).add(extra)

        # P2 has no creatures at all; target p2 for token
        # After resolve: P1 = 4 creatures, P2 = 1 token
        card.chosen_targets = [p2]
        card.on_resolve(game)

        assert getattr(card, "is_prepared", False) is False, \
            "Emeritus should NOT be prepared when controller has more creatures"

    def test_becomes_prepared_targeting_self_opponent_still_has_more(self) -> None:
        """Targeting self for the token but opponent still has more creatures."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # Opponent has 4 creatures
        for i in range(4):
            opp = Creature(
                name=f"OppCreature{i}", owner=p2, controller=p2,
                base_power=2, base_toughness=2,
            )
            game.get_battlefield(p2).add(opp)

        # Target self: P1 gets Emeritus + Token = 2, P2 has 4
        card.chosen_targets = [p1]
        card.on_resolve(game)

        assert getattr(card, "is_prepared", False) is True, \
            "Should be prepared even when targeting self if opponent still has more"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEmeritusOfTruceEdgeCases:
    """Edge cases and boundary conditions."""

    def test_on_resolve_no_chosen_targets_does_not_crash(self) -> None:
        """If there are no chosen targets, on_resolve should be a no-op."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        # No chosen_targets set
        card.on_resolve(game)

    def test_on_resolve_empty_chosen_targets_does_not_crash(self) -> None:
        """If chosen_targets is empty, on_resolve should be a no-op."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.chosen_targets = []
        card.on_resolve(game)

    def test_opponent_has_no_creatures_token_given_to_opponent(self) -> None:
        """When only the token is on the opponent's side, the opponent has
        1 creature and the controller has 1 (Emeritus). Not prepared since
        opponent does NOT have MORE (equal is not more)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # No creatures on either side except Emeritus
        # Target p2: P1 = 1 (Emeritus), P2 = 1 (token)
        card.chosen_targets = [p2]
        card.on_resolve(game)

        # P2 has only the token, P1 has Emeritus. Equal -> not prepared.
        assert getattr(card, "is_prepared", False) is False, \
            "Equal creature counts should not trigger prepared"

    def test_token_on_opponent_side_tips_balance(self) -> None:
        """If giving the token to the opponent causes them to have more
        creatures, the card becomes prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # Opponent has 1 creature already
        opp_bear = Creature(
            name="Opp Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        game.get_battlefield(p2).add(opp_bear)

        # Target p2: P1 = 1 (Emeritus), P2 = 1 bear + 1 token = 2
        card.chosen_targets = [p2]
        card.on_resolve(game)

        assert getattr(card, "is_prepared", False) is True, \
            "Giving token to opponent causing them to have more should prepare"
