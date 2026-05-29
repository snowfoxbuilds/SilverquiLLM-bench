"""Tests for sos_13 — Emeritus of Truce // Swords to Plowshares.

Covers:
- Static properties (name, mana cost, power/toughness, type)
- ETB trigger registration
- ETB trigger: creates 1/1 white and black Inkling token with flying for target player
- ETB trigger: creature becomes prepared if opponent controls more creatures
- ETB trigger: creature does NOT become prepared if opponent does not control more creatures
- Prepared state tracked on creature (is_prepared attribute)
- While prepared: can cast a copy of Swords to Plowshares
- Casting the copy unprepares the creature
- Swords to Plowshares copy effect: exiles target creature, its controller gains life = power
"""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature, Instant
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    Zone,
)
from test_utils import create_game, set_board_state


class TestEmeritusOfTruceProperties:
    """Static card data should match the sos_13 spec."""

    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce"

    def test_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_base_power(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3

    def test_base_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_toughness == 3

    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_has_cat_cleric_subtypes(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes


class TestEmeritusOfTruceETBTrigger:
    """ETB trigger registration and firing."""

    def test_register_triggers_adds_at_least_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_etb_trigger_fires_on_enters_battlefield_event(self) -> None:
        """Trigger must watch EntersBattlefieldTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_triggers = [
            t for t in triggers
            if t.event_type is EntersBattlefieldTriggeredEvent
        ]
        assert len(etb_triggers) >= 1

    def test_etb_trigger_condition_fires_only_for_self(self) -> None:
        """Trigger condition should only fire when THIS creature enters."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_triggers = [
            t for t in triggers
            if t.event_type is EntersBattlefieldTriggeredEvent
        ]
        assert len(etb_triggers) >= 1
        trigger = etb_triggers[0]
        if trigger.condition is not None:
            event_self = EntersBattlefieldTriggeredEvent(permanent=card)
            other = Creature(name="Other Creature", owner=p1, controller=p1)
            event_other = EntersBattlefieldTriggeredEvent(permanent=other)
            assert trigger.condition(game, event_self) is True
            assert trigger.condition(game, event_other) is False


class TestEmeritusOfTruceTokenCreation:
    """ETB trigger: creates 1/1 white and black Inkling token with flying."""

    def test_etb_creates_inkling_token_on_controller_battlefield(self) -> None:
        """ETB trigger should place an Inkling token on the target player's battlefield."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        event = EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        game.trigger_manager.fire_event(game, event)
        # Find token on any player's battlefield
        all_tokens = []
        for player in game.players:
            bf = game.get_battlefield(player)
            for obj in bf.get_all():
                if getattr(obj, "is_token", False):
                    all_tokens.append(obj)
        assert len(all_tokens) >= 1, "ETB trigger should create at least one token"

    def test_etb_token_is_inkling_subtype(self) -> None:
        """Token created by ETB trigger should have Inkling subtype."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        event = EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        game.trigger_manager.fire_event(game, event)
        all_tokens = []
        for player in game.players:
            bf = game.get_battlefield(player)
            for obj in bf.get_all():
                if getattr(obj, "is_token", False):
                    all_tokens.append(obj)
        assert any(
            "Inkling" in getattr(t, "subtypes", set()) for t in all_tokens
        ), "Created token should have Inkling subtype"

    def test_etb_token_has_flying(self) -> None:
        """Token created by ETB trigger should have flying."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        event = EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        game.trigger_manager.fire_event(game, event)
        all_tokens = []
        for player in game.players:
            bf = game.get_battlefield(player)
            for obj in bf.get_all():
                if getattr(obj, "is_token", False):
                    all_tokens.append(obj)
        assert any(
            Keyword.FLYING in getattr(t, "keywords", Keyword(0)) for t in all_tokens
        ), "Created token should have flying"

    def test_etb_token_is_1_1(self) -> None:
        """Token created by ETB trigger should be 1/1."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        event = EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        game.trigger_manager.fire_event(game, event)
        all_tokens = []
        for player in game.players:
            bf = game.get_battlefield(player)
            for obj in bf.get_all():
                if getattr(obj, "is_token", False):
                    all_tokens.append(obj)
        inkling_tokens = [t for t in all_tokens if "Inkling" in getattr(t, "subtypes", set())]
        assert len(inkling_tokens) >= 1
        token = inkling_tokens[0]
        assert getattr(token, "base_power", None) == 1, "Token power should be 1"
        assert getattr(token, "base_toughness", None) == 1, "Token toughness should be 1"


class TestEmeritusOfTrucePreparedState:
    """ETB trigger: creature becomes prepared based on opponent creature count."""

    def test_not_prepared_when_opponent_has_fewer_creatures(self) -> None:
        """Creature should NOT be prepared if opponent has fewer creatures."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # p1 has 2 creatures (including the card itself), p2 has 1 — p2 doesn't have MORE
        bear = Creature(name="Grizzly Bears", owner=p2, controller=p2, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[bear])
        card.register_triggers(game)
        event = EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        game.trigger_manager.fire_event(game, event)
        assert not getattr(card, "is_prepared", False), \
            "Should not be prepared when opponent has fewer/equal creatures"

    def test_not_prepared_when_opponent_has_equal_creatures(self) -> None:
        """Creature should NOT be prepared if opponent has equal count (need strictly more)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # p1: 1 creature (card), p2: 1 creature — equal, not MORE
        opp_bear = Creature(name="Opp Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[opp_bear])
        card.register_triggers(game)
        event = EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        game.trigger_manager.fire_event(game, event)
        assert not getattr(card, "is_prepared", False), \
            "Should not be prepared when opponent has equal creatures"

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        """Creature should become prepared if an opponent controls more creatures."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # p1: 1 creature (card), p2: 3 creatures — p2 has MORE
        opp1 = Creature(name="Opp Bear 1", owner=p2, controller=p2, base_power=2, base_toughness=2)
        opp2 = Creature(name="Opp Bear 2", owner=p2, controller=p2, base_power=2, base_toughness=2)
        opp3 = Creature(name="Opp Bear 3", owner=p2, controller=p2, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[opp1, opp2, opp3])
        card.register_triggers(game)
        event = EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        game.trigger_manager.fire_event(game, event)
        assert getattr(card, "is_prepared", False) is True, \
            "Should become prepared when opponent controls more creatures"

    def test_not_prepared_when_controller_has_no_opponents_with_more_creatures(self) -> None:
        """Creature is not prepared if no opponent has strictly more creatures."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # p1: 3 creatures, p2: 1 creature — p1 has more, not the opponent
        extra1 = Creature(name="Ally 1", owner=p1, controller=p1, base_power=2, base_toughness=2)
        extra2 = Creature(name="Ally 2", owner=p1, controller=p1, base_power=2, base_toughness=2)
        opp1 = Creature(name="Opp Bear 1", owner=p2, controller=p2, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card, extra1, extra2])
        set_board_state(game, 1, battlefield=[opp1])
        card.register_triggers(game)
        event = EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        game.trigger_manager.fire_event(game, event)
        assert not getattr(card, "is_prepared", False), \
            "Should not be prepared when you have more creatures than opponent"

    def test_is_prepared_attribute_starts_false_before_etb(self) -> None:
        """A freshly created card should not be prepared before ETB trigger fires."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # Before any ETB fires, is_prepared should be False or absent
        assert not getattr(card, "is_prepared", False), \
            "New card should not start in prepared state"


class TestSwordsToPlowsharesEffect:
    """The Swords to Plowshares copy from prepared state exiles a creature and gains life."""

    def test_swords_to_plowshares_copy_exiles_target_creature(self) -> None:
        """STP copy effect should exile the target creature."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        target = Creature(
            name="Target Creature",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        set_board_state(game, 1, battlefield=[target])
        # Simulate the card being prepared
        card.is_prepared = True
        # Use the on_resolve method with chosen_targets to simulate STP copy
        card.chosen_targets = [target]
        card.on_resolve_swords_to_plowshares(game)
        # Target should now be in exile
        exile_zone = game.get_exile(p2)
        assert exile_zone.contains(target), "Target should be exiled by STP copy"

    def test_swords_to_plowshares_copy_grants_life_equal_to_power(self) -> None:
        """STP copy effect: target creature's controller gains life equal to its power."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        target = Creature(
            name="Target Creature",
            owner=p2,
            controller=p2,
            base_power=4,
            base_toughness=4,
        )
        set_board_state(game, 1, battlefield=[target], life=20)
        card.is_prepared = True
        card.chosen_targets = [target]
        card.on_resolve_swords_to_plowshares(game)
        # p2 should gain 4 life (power of target)
        assert game.players[1].life == 24, \
            "Target's controller should gain life equal to target's power"

    def test_swords_to_plowshares_copy_removes_target_from_battlefield(self) -> None:
        """STP copy effect: target creature should no longer be on battlefield."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        target = Creature(
            name="Exiled Creature",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 1, battlefield=[target])
        card.is_prepared = True
        card.chosen_targets = [target]
        card.on_resolve_swords_to_plowshares(game)
        bf = game.get_battlefield(p2)
        assert not bf.contains(target), "Target should not remain on battlefield after STP"

    def test_swords_to_plowshares_with_no_target_is_noop(self) -> None:
        """STP copy effect with no targets should not raise."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = True
        card.chosen_targets = []
        try:
            card.on_resolve_swords_to_plowshares(game)
        except Exception as exc:
            pytest.fail(f"on_resolve_swords_to_plowshares raised unexpectedly: {exc}")


class TestEmeritusOfTruceUnpreparedAfterCast:
    """Casting the STP copy unprepares the creature."""

    def test_casting_stp_copy_sets_is_prepared_to_false(self) -> None:
        """After using the STP copy (resolving it), creature should no longer be prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        target = Creature(
            name="Fodder",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 1, battlefield=[target])
        # Mark as prepared
        card.is_prepared = True
        card.chosen_targets = [target]
        card.on_resolve_swords_to_plowshares(game)
        # After resolving the copy, creature must be unprepared
        assert not getattr(card, "is_prepared", True), \
            "Creature should be unprepared after casting the STP copy"
