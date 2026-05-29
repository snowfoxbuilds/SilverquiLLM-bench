"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares.

Oracle text:
  When this creature enters, target player creates a 1/1 white and black
  Inkling creature token with flying. Then if an opponent controls more
  creatures than you, this creature becomes prepared.
  (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)

The "spell" is Swords to Plowshares:
  Exile target creature. Its controller gains life equal to its power.

Tests cover:
- Static card properties (name, mana cost, P/T, subtypes, type)
- ETB trigger registration
- ETB trigger fires on EntersBattlefieldTriggeredEvent for self only
- Inkling token creation: target player gets the token
- Inkling token properties: 1/1, has Flying, subtype "Inkling"
- Conditional prepared: opponent controls more creatures → is_prepared = True
- Conditional prepared: equal creatures → is_prepared = False (no preparation)
- Conditional prepared: opponent controls fewer creatures → is_prepared = False
- Prepared ability: get_activated_abilities returns something while prepared
- Prepared STP effect: exile target creature
- Prepared STP effect: target creature's controller gains life = creature's power
- Prepared STP effect: after use is_prepared becomes False (unprepared)
- Unprepared: no usable prepared ability
"""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static property tests
# ---------------------------------------------------------------------------


class TestEmeritusOfTruceProperties:
    """Static card data must match the SOS 13 spec."""

    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)

    def test_card_type_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"

    def test_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_power(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_toughness == 3

    def test_subtype_cat(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cat" in card.subtypes

    def test_subtype_cleric(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cleric" in card.subtypes

    def test_is_not_prepared_initially(self) -> None:
        """Card starts unprepared."""
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert not getattr(card, "is_prepared", False)


# ---------------------------------------------------------------------------
# ETB trigger registration
# ---------------------------------------------------------------------------


class TestEmeritusOfTruceETBTriggerRegistration:
    """register_triggers must register an ETB trigger for this creature."""

    def test_register_triggers_does_not_raise(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)  # must not raise

    def test_etb_trigger_is_registered(self) -> None:
        """After register_triggers, at least one trigger exists for source."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) >= 1

    def test_etb_trigger_fires_on_self_entry(self) -> None:
        """Firing EntersBattlefieldTriggeredEvent for this creature pushes to stack."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        assert game.stack.is_empty()
        event = EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        game.trigger_manager.fire_event(game, event)
        assert not game.stack.is_empty()

    def test_etb_trigger_does_not_fire_for_other_creature(self) -> None:
        """The trigger must NOT fire when a different creature enters."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        assert game.stack.is_empty()
        other = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        event = EntersBattlefieldTriggeredEvent(permanent=other, controller=p1)
        game.trigger_manager.fire_event(game, event)
        assert game.stack.is_empty()


# ---------------------------------------------------------------------------
# Inkling token creation
# ---------------------------------------------------------------------------


class TestEmeritusOfTruceInklingToken:
    """ETB trigger creates a 1/1 Inkling token with Flying for the target player."""

    def _fire_and_pop_trigger(self, game, card):
        """Helper: fire ETB for card and pop the resulting trigger stack object."""
        p1 = card.controller
        event = EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        game.trigger_manager.fire_event(game, event)
        return game.stack.pop()

    def test_trigger_creates_token_on_target_player_battlefield(self) -> None:
        """When trigger resolves with a target player, that player gets a new creature."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        trigger_obj = self._fire_and_pop_trigger(game, card)
        # Set the target player (the one who will receive the token)
        trigger_obj.chosen_targets = [p1]

        bf_before = len(game.get_battlefield(p1).get_all())
        trigger_obj.on_resolve(game)
        bf_after = len(game.get_battlefield(p1).get_all())

        # Exactly one new permanent (the Inkling token) enters p1's battlefield
        assert bf_after - bf_before == 1

    def test_trigger_creates_token_for_opponent_if_targeted(self) -> None:
        """Target player can be the opponent — the token goes to their battlefield."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        trigger_obj = self._fire_and_pop_trigger(game, card)
        trigger_obj.chosen_targets = [p2]

        bf_before_p2 = len(game.get_battlefield(p2).get_all())
        bf_before_p1 = len(game.get_battlefield(p1).get_all())
        trigger_obj.on_resolve(game)

        # Token enters p2's battlefield
        assert len(game.get_battlefield(p2).get_all()) - bf_before_p2 == 1
        # p1's battlefield size unchanged by token creation
        assert len(game.get_battlefield(p1).get_all()) - bf_before_p1 == 0

    def test_inkling_token_is_one_one(self) -> None:
        """The created token is a 1/1 creature."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        trigger_obj = self._fire_and_pop_trigger(game, card)
        trigger_obj.chosen_targets = [p1]
        trigger_obj.on_resolve(game)

        new_creatures = [
            obj for obj in game.get_battlefield(p1).get_all()
            if isinstance(obj, Creature) and getattr(obj, "is_token", False)
        ]
        assert len(new_creatures) == 1
        tok = new_creatures[0]
        assert tok.base_power == 1
        assert tok.base_toughness == 1

    def test_inkling_token_has_flying(self) -> None:
        """The created Inkling token has the Flying keyword."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        trigger_obj = self._fire_and_pop_trigger(game, card)
        trigger_obj.chosen_targets = [p1]
        trigger_obj.on_resolve(game)

        tokens = [
            obj for obj in game.get_battlefield(p1).get_all()
            if isinstance(obj, Creature) and getattr(obj, "is_token", False)
        ]
        assert len(tokens) == 1
        assert Keyword.FLYING in tokens[0].keywords

    def test_inkling_token_has_inkling_subtype(self) -> None:
        """The created token has 'Inkling' as a subtype."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        trigger_obj = self._fire_and_pop_trigger(game, card)
        trigger_obj.chosen_targets = [p1]
        trigger_obj.on_resolve(game)

        tokens = [
            obj for obj in game.get_battlefield(p1).get_all()
            if isinstance(obj, Creature) and getattr(obj, "is_token", False)
        ]
        assert len(tokens) == 1
        assert "Inkling" in getattr(tokens[0], "subtypes", set())

    def test_inkling_token_is_creature(self) -> None:
        """The created token has CREATURE card type."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        trigger_obj = self._fire_and_pop_trigger(game, card)
        trigger_obj.chosen_targets = [p1]
        trigger_obj.on_resolve(game)

        tokens = [
            obj for obj in game.get_battlefield(p1).get_all()
            if isinstance(obj, Creature) and getattr(obj, "is_token", False)
        ]
        assert len(tokens) == 1
        assert CardType.CREATURE in tokens[0].card_types


# ---------------------------------------------------------------------------
# Conditional prepared state
# ---------------------------------------------------------------------------


class TestEmeritusOfTruceConditionalPrepared:
    """After ETB, if an opponent controls more creatures than you → is_prepared = True."""

    def _fire_and_pop_trigger(self, game, card):
        p1 = card.controller
        event = EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        game.trigger_manager.fire_event(game, event)
        return game.stack.pop()

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        """Opponent has 2 creatures, controller has 0 → prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put 2 creatures on opponent's battlefield
        opp_creature_1 = Creature(name="Bear1", base_power=2, base_toughness=2,
                                   owner=p2, controller=p2)
        opp_creature_2 = Creature(name="Bear2", base_power=2, base_toughness=2,
                                   owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[opp_creature_1, opp_creature_2])

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        trigger_obj = self._fire_and_pop_trigger(game, card)
        trigger_obj.chosen_targets = [p1]
        trigger_obj.on_resolve(game)

        assert getattr(card, "is_prepared", False) is True

    def test_not_prepared_when_opponent_has_equal_creatures(self) -> None:
        """Opponent has 1 creature, controller has 1 creature → NOT prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        opp_creature = Creature(name="OppBear", base_power=2, base_toughness=2,
                                 owner=p2, controller=p2)
        my_creature = Creature(name="MyBear", base_power=2, base_toughness=2,
                                owner=p1, controller=p1)
        set_board_state(game, 1, battlefield=[opp_creature])
        set_board_state(game, 0, battlefield=[my_creature])

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        trigger_obj = self._fire_and_pop_trigger(game, card)
        trigger_obj.chosen_targets = [p1]
        trigger_obj.on_resolve(game)

        assert getattr(card, "is_prepared", False) is False

    def test_not_prepared_when_controller_has_more_creatures(self) -> None:
        """Controller has 3 creatures, opponent has 1 → NOT prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        opp_creature = Creature(name="OppBear", base_power=2, base_toughness=2,
                                 owner=p2, controller=p2)
        my_creatures = [
            Creature(name=f"MyBear{i}", base_power=2, base_toughness=2,
                     owner=p1, controller=p1)
            for i in range(3)
        ]
        set_board_state(game, 1, battlefield=[opp_creature])
        set_board_state(game, 0, battlefield=my_creatures)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        trigger_obj = self._fire_and_pop_trigger(game, card)
        trigger_obj.chosen_targets = [p1]
        trigger_obj.on_resolve(game)

        assert getattr(card, "is_prepared", False) is False

    def test_not_prepared_when_both_empty_battlefields(self) -> None:
        """Both players have 0 creatures → opponent does NOT have more → NOT prepared."""
        game = create_game()
        p1 = game.players[0]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        trigger_obj = self._fire_and_pop_trigger(game, card)
        trigger_obj.chosen_targets = [p1]
        trigger_obj.on_resolve(game)

        # The token we just created goes to p1, so now p1 has 1, p2 has 0:
        # opponent does NOT have more creatures → not prepared
        assert getattr(card, "is_prepared", False) is False

    def test_prepared_check_considers_inkling_token_count(self) -> None:
        """The prepared check happens AFTER token creation; creature counts include token."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Opponent has 2 creatures; after giving p1 the token (1 creature),
        # opponent still has more → prepared
        opp_c1 = Creature(name="Opp1", base_power=1, base_toughness=1,
                           owner=p2, controller=p2)
        opp_c2 = Creature(name="Opp2", base_power=1, base_toughness=1,
                           owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[opp_c1, opp_c2])

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        trigger_obj = self._fire_and_pop_trigger(game, card)
        trigger_obj.chosen_targets = [p1]
        trigger_obj.on_resolve(game)

        # After token: p1 has 1 creature, p2 has 2 → p2 has more → prepared
        assert getattr(card, "is_prepared", False) is True


# ---------------------------------------------------------------------------
# Prepared ability — Swords to Plowshares effect
# ---------------------------------------------------------------------------


class TestEmeritusOfTruceSwordsToPlowshares:
    """When prepared, the card can cast a Swords to Plowshares equivalent."""

    def _make_prepared_card(self, game, player_index=0):
        """Create an EmeritusOfTruce with is_prepared=True on the battlefield."""
        p = game.players[player_index]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p, controller=p)
        card.is_prepared = True
        game.get_battlefield(p).add(card)
        return card

    def test_prepared_creature_has_activated_ability(self) -> None:
        """When prepared, get_activated_abilities() returns at least one ability."""
        game = create_game()
        card = self._make_prepared_card(game, 0)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_prepared_ability_exiles_target_creature(self) -> None:
        """Using the prepared Swords ability exiles the target creature."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put a creature on p2's battlefield as the target
        target = Creature(name="TargetCreature", base_power=3, base_toughness=3,
                          owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])

        card = self._make_prepared_card(game, 0)

        # Use the prepared ability — set chosen_targets on the ability source
        card.chosen_targets = [target]
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1
        swords_ability = abilities[0]
        swords_ability.effect(game)

        # The target creature should no longer be on the battlefield
        bf_p2 = game.get_battlefield(p2).get_all()
        assert target not in bf_p2

    def test_prepared_ability_target_goes_to_exile(self) -> None:
        """The exiled creature goes to the exile zone (not graveyard)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="TargetBear", base_power=2, base_toughness=2,
                          owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])

        card = self._make_prepared_card(game, 0)
        card.chosen_targets = [target]

        abilities = card.get_activated_abilities()
        abilities[0].effect(game)

        exile_p2 = game.get_exile(p2).get_all()
        gy_p2 = game.get_graveyard(p2).get_all()
        # Exiled, not in graveyard
        assert target in exile_p2
        assert target not in gy_p2

    def test_prepared_ability_controller_gains_life_equal_to_power(self) -> None:
        """Exiled creature's controller gains life equal to the creature's power."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Creature with power=4 on p2's battlefield
        target = Creature(name="PowerCreature", base_power=4, base_toughness=4,
                          owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])

        card = self._make_prepared_card(game, 0)
        card.chosen_targets = [target]

        initial_life_p2 = p2.life
        abilities = card.get_activated_abilities()
        abilities[0].effect(game)

        # p2 (target's controller) gains 4 life (power of the exiled creature)
        assert p2.life == initial_life_p2 + 4

    def test_prepared_ability_life_gain_matches_power(self) -> None:
        """Life gain equals printed power — test with power=1."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="WeakBear", base_power=1, base_toughness=1,
                          owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])

        card = self._make_prepared_card(game, 0)
        card.chosen_targets = [target]

        initial_life = p2.life
        abilities = card.get_activated_abilities()
        abilities[0].effect(game)

        assert p2.life == initial_life + 1

    def test_prepared_ability_unprepares_after_use(self) -> None:
        """After using the prepared ability, is_prepared becomes False."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="SomeCreature", base_power=2, base_toughness=5,
                          owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])

        card = self._make_prepared_card(game, 0)
        card.chosen_targets = [target]

        assert card.is_prepared is True
        abilities = card.get_activated_abilities()
        abilities[0].effect(game)

        assert card.is_prepared is False

    def test_unprepared_creature_has_no_swords_ability(self) -> None:
        """When NOT prepared, get_activated_abilities() returns no swords ability."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = False
        game.get_battlefield(p1).add(card)

        # Either no abilities or none that correspond to the swords effect
        abilities = card.get_activated_abilities()
        # All returned abilities should NOT be the prepared swords ability
        # (unprepared → zero swords-to-plowshares abilities)
        swords_descriptions = [
            ab for ab in abilities
            if "exile" in getattr(ab, "description", "").lower()
            or "plowshares" in getattr(ab, "description", "").lower()
            or "prepared" in getattr(ab, "description", "").lower()
        ]
        assert len(swords_descriptions) == 0

    def test_prepared_ability_does_not_affect_non_target_creatures(self) -> None:
        """Only the chosen target creature is exiled; others remain untouched."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Target", base_power=2, base_toughness=2,
                          owner=p2, controller=p2)
        bystander = Creature(name="Bystander", base_power=3, base_toughness=3,
                             owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target, bystander])

        card = self._make_prepared_card(game, 0)
        card.chosen_targets = [target]

        abilities = card.get_activated_abilities()
        abilities[0].effect(game)

        # Bystander must remain on the battlefield
        bf_p2 = game.get_battlefield(p2).get_all()
        assert bystander in bf_p2
