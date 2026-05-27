"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares.

Card spec:
  Mana cost: {1}{W}{W}
  Type: Creature — Cat Cleric // Instant
  P/T: 3/3
  Keywords: Prepared
  Oracle text:
    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.
    (While it's prepared, you may cast a copy of its spell. Doing so
    unprepares it.)
"""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestEmeritusOfTruceProperties:
    """Static card data should match the SOS 13 spec."""

    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)

    def test_card_type_contains_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        # Front-face name (creature side)
        assert "Emeritus of Truce" in card.name

    def test_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_base_power(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3

    def test_base_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_toughness == 3

    def test_subtypes_include_cat(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cat" in card.subtypes

    def test_subtypes_include_cleric(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cleric" in card.subtypes

    def test_is_prepared_defaults_to_false(self) -> None:
        """The prepared state should default to False before any ETB trigger."""
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.is_prepared is False


# ---------------------------------------------------------------------------
# ETB trigger registration
# ---------------------------------------------------------------------------

class TestEmeritusETBTriggerRegistration:
    """register_triggers() must wire an EntersBattlefieldTriggeredEvent trigger."""

    def test_registers_at_least_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_registers_enters_battlefield_trigger(self) -> None:
        """The trigger must watch for EntersBattlefieldTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) >= 1
        event_types = [t.event_type for t in triggers]
        assert any(
            issubclass(EntersBattlefieldTriggeredEvent, t) or t is EntersBattlefieldTriggeredEvent
            for t in event_types
        )

    def test_etb_trigger_fires_on_self_entering(self) -> None:
        """Firing an ETB event for this creature should push onto the stack."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        stack_before = len(game.stack)
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )
        assert len(game.stack) > stack_before

    def test_etb_trigger_condition_fires_for_self(self) -> None:
        """Trigger condition must pass for this card entering the battlefield."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_triggers = [
            t for t in triggers
            if issubclass(EntersBattlefieldTriggeredEvent, t.event_type)
            or t.event_type is EntersBattlefieldTriggeredEvent
        ]
        assert len(etb_triggers) >= 1
        trigger = etb_triggers[0]
        event = EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        if trigger.condition is not None:
            assert trigger.condition(game, event) is True


# ---------------------------------------------------------------------------
# ETB token creation
# ---------------------------------------------------------------------------

class TestEmeritusInklingTokenCreation:
    """ETB effect must create a 1/1 white-and-black Inkling creature token
    with flying for the target player."""

    def _get_etb_trigger(self, game, card):
        """Helper: return the ETB trigger registration for card."""
        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_triggers = [
            t for t in triggers
            if issubclass(EntersBattlefieldTriggeredEvent, t.event_type)
            or t.event_type is EntersBattlefieldTriggeredEvent
        ]
        assert etb_triggers, "No ETB trigger found"
        return etb_triggers[0]

    def test_token_created_on_target_player_battlefield(self) -> None:
        """After ETB trigger effect, target player gains a creature on battlefield."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p1]   # target player for the token
        before = len(game.get_battlefield(p1).get_all())
        trigger.effect(game)
        after = len(game.get_battlefield(p1).get_all())
        assert after > before

    def test_token_has_inkling_subtype(self) -> None:
        """The created token must have the 'Inkling' creature type."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p1]
        trigger.effect(game)
        # Find the token on the battlefield
        bf_objects = game.get_battlefield(p1).get_all()
        inkling_tokens = [
            obj for obj in bf_objects
            if hasattr(obj, "subtypes") and "Inkling" in obj.subtypes
        ]
        assert len(inkling_tokens) >= 1

    def test_token_is_1_1(self) -> None:
        """The Inkling token must be a 1/1 creature."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p1]
        trigger.effect(game)
        bf_objects = game.get_battlefield(p1).get_all()
        inkling_tokens = [
            obj for obj in bf_objects
            if hasattr(obj, "subtypes") and "Inkling" in obj.subtypes
        ]
        assert len(inkling_tokens) >= 1
        token = inkling_tokens[0]
        assert token.base_power == 1
        assert token.base_toughness == 1

    def test_token_has_flying(self) -> None:
        """The Inkling token must have the Flying keyword."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p1]
        trigger.effect(game)
        bf_objects = game.get_battlefield(p1).get_all()
        inkling_tokens = [
            obj for obj in bf_objects
            if hasattr(obj, "subtypes") and "Inkling" in obj.subtypes
        ]
        assert len(inkling_tokens) >= 1
        token = inkling_tokens[0]
        assert Keyword.FLYING in token.keywords

    def test_token_is_flagged_as_token(self) -> None:
        """Token should have is_token=True."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p1]
        trigger.effect(game)
        bf_objects = game.get_battlefield(p1).get_all()
        inkling_tokens = [
            obj for obj in bf_objects
            if hasattr(obj, "subtypes") and "Inkling" in obj.subtypes
        ]
        assert len(inkling_tokens) >= 1
        token = inkling_tokens[0]
        assert getattr(token, "is_token", False) is True

    def test_token_is_creature_type(self) -> None:
        """The Inkling token must be a creature."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p1]
        trigger.effect(game)
        bf_objects = game.get_battlefield(p1).get_all()
        inkling_tokens = [
            obj for obj in bf_objects
            if hasattr(obj, "subtypes") and "Inkling" in obj.subtypes
        ]
        assert len(inkling_tokens) >= 1
        token = inkling_tokens[0]
        assert isinstance(token, Creature)

    def test_token_can_be_created_for_opponent(self) -> None:
        """Token can be created for the opponent when they are the target."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p2]   # opponent is the target player
        before = len(game.get_battlefield(p2).get_all())
        trigger.effect(game)
        after = len(game.get_battlefield(p2).get_all())
        assert after > before

    def test_no_target_is_a_noop(self) -> None:
        """With no target set, the ETB effect must not raise."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = []
        # Should not raise
        trigger.effect(game)


# ---------------------------------------------------------------------------
# Prepared mechanic
# ---------------------------------------------------------------------------

class TestEmeritusPreparedness:
    """After the ETB trigger effect, is_prepared is set to True iff an
    opponent controls strictly more creatures than the controller."""

    def _get_etb_trigger(self, game, card):
        """Helper: return the ETB trigger registration for card."""
        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_triggers = [
            t for t in triggers
            if issubclass(EntersBattlefieldTriggeredEvent, t.event_type)
            or t.event_type is EntersBattlefieldTriggeredEvent
        ]
        assert etb_triggers, "No ETB trigger found"
        return etb_triggers[0]

    def test_prepared_when_opponent_has_strictly_more_creatures(self) -> None:
        """is_prepared becomes True when an opponent controls more creatures."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # p2 (opponent) has 2 creatures, p1 (controller) has 0
        opp_creature1 = Creature(name="Opp Bear 1", owner=p2, controller=p2,
                                 base_power=2, base_toughness=2)
        opp_creature2 = Creature(name="Opp Bear 2", owner=p2, controller=p2,
                                 base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[opp_creature1, opp_creature2])
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p1]   # token goes to p1 (controller)
        trigger.effect(game)
        assert card.is_prepared is True

    def test_not_prepared_when_controller_has_more_creatures(self) -> None:
        """is_prepared stays False when the controller has more creatures than the opponent."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # p1 (controller) has 3 creatures, p2 (opponent) has 1
        ctrl_creature1 = Creature(name="Ctrl Bear 1", owner=p1, controller=p1,
                                  base_power=2, base_toughness=2)
        ctrl_creature2 = Creature(name="Ctrl Bear 2", owner=p1, controller=p1,
                                  base_power=2, base_toughness=2)
        ctrl_creature3 = Creature(name="Ctrl Bear 3", owner=p1, controller=p1,
                                  base_power=2, base_toughness=2)
        opp_creature1 = Creature(name="Opp Bear", owner=p2, controller=p2,
                                 base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[ctrl_creature1, ctrl_creature2, ctrl_creature3])
        set_board_state(game, 1, battlefield=[opp_creature1])
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p1]
        trigger.effect(game)
        assert card.is_prepared is False

    def test_not_prepared_when_equal_creature_counts(self) -> None:
        """is_prepared stays False when both players control the same number of creatures."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Both players have 1 creature each
        ctrl_creature = Creature(name="Ctrl Bear", owner=p1, controller=p1,
                                 base_power=1, base_toughness=1)
        opp_creature = Creature(name="Opp Bear", owner=p2, controller=p2,
                                base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[ctrl_creature])
        set_board_state(game, 1, battlefield=[opp_creature])
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p1]
        trigger.effect(game)
        assert card.is_prepared is False

    def test_not_prepared_when_both_have_zero_creatures(self) -> None:
        """is_prepared stays False when neither player controls any creatures."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Empty battlefields
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p1]
        trigger.effect(game)
        # After token creation, p1 has 1 creature (the token), p2 has 0
        # 0 < 1 so opponent (p2) does NOT have more creatures — not prepared
        assert card.is_prepared is False

    def test_prepared_with_large_disparity(self) -> None:
        """is_prepared is True when opponent has many more creatures."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # p2 has 5 creatures, p1 has 0
        opp_creatures = [
            Creature(name=f"Opp Creature {i}", owner=p2, controller=p2,
                     base_power=1, base_toughness=1)
            for i in range(5)
        ]
        set_board_state(game, 1, battlefield=opp_creatures)
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p1]
        trigger.effect(game)
        assert card.is_prepared is True
