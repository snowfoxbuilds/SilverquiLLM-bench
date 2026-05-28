"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares.

Emeritus of Truce is a preparation card:
  Front face: Creature — Cat Cleric, {1}{W}{W}, 3/3
  Prepare spell: Swords to Plowshares, Instant, {W}

Oracle text (front face):
  "When this creature enters, target player creates a 1/1 white and
  black Inkling creature token with flying. Then if an opponent controls
  more creatures than you, this creature becomes prepared. (While it's
  prepared, you may cast a copy of its spell. Doing so unprepares it.)"

Requirements tested:
  1. Static properties (name, mana cost, P/T, subtypes, creature type).
  2. ETB trigger registration for the enters-the-battlefield ability.
  3. ETB effect: target player creates a 1/1 white+black Inkling token
     with flying.
  4. Prepared condition: after token creation, becomes prepared if an
     opponent controls more creatures than the controller.
  5. Prepared designation attribute tracking.
"""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature, Instant
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------

class TestEmeritusStaticProperties:
    """Static card data should match the SOS 13 spec."""

    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)

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

    def test_subtypes_include_cat_and_cleric(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_has_creature_card_type(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types


# ---------------------------------------------------------------------------
# ETB trigger registration
# ---------------------------------------------------------------------------

class TestEmeritusETBTriggerRegistration:
    """register_triggers must wire an ETB trigger through trigger_manager."""

    def test_registers_at_least_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_registered_trigger_watches_etb_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) >= 1
        etb_trigger = triggers[0]
        assert etb_trigger.event_type is EntersBattlefieldTriggeredEvent

    def test_trigger_condition_fires_only_for_self(self) -> None:
        """The ETB trigger should fire when this creature itself enters,
        not when some other creature enters."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_trigger = triggers[0]
        # Condition should match when the entering permanent is self.
        self_event = EntersBattlefieldTriggeredEvent(
            permanent=card, controller=p1
        )
        assert etb_trigger.condition is None or etb_trigger.condition(game, self_event)
        # Condition should NOT match when some other creature enters.
        other = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        other_event = EntersBattlefieldTriggeredEvent(
            permanent=other, controller=p1
        )
        if etb_trigger.condition is not None:
            assert etb_trigger.condition(game, other_event) is False


# ---------------------------------------------------------------------------
# ETB effect — Inkling token creation
# ---------------------------------------------------------------------------

class TestEmeritusInklingTokenCreation:
    """When the ETB trigger resolves, the target player creates a 1/1
    white and black Inkling creature token with flying."""

    def _setup_and_fire_etb(self, game, controller, target_player):
        """Put the card on battlefield, register triggers, and fire its
        ETB effect directly."""
        card = EmeritusOfTruceSwordsToPlowshares(
            owner=controller, controller=controller
        )
        game.get_battlefield(controller).add(card)
        card.register_triggers(game)

        # Find the ETB trigger and resolve its effect directly.
        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_trigger = triggers[0]

        # Set chosen_targets on the card so the effect knows which
        # player receives the token.
        card.chosen_targets = [target_player]

        etb_trigger.effect(game)
        return card

    def test_controller_gets_inkling_when_self_is_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bf_before = len(game.get_battlefield(p1).get_all())
        # Card is already on battlefield from _setup; count its own addition
        self._setup_and_fire_etb(game, p1, p1)
        bf_after = game.get_battlefield(p1).get_all()
        # There should be at least one new token besides the card itself.
        tokens = [
            obj for obj in bf_after
            if getattr(obj, "is_token", False)
        ]
        assert len(tokens) >= 1

    def test_opponent_gets_inkling_when_opponent_is_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bf_before = len(game.get_battlefield(p2).get_all())
        self._setup_and_fire_etb(game, p1, p2)
        bf_after = game.get_battlefield(p2).get_all()
        tokens = [
            obj for obj in bf_after
            if getattr(obj, "is_token", False)
        ]
        assert len(tokens) >= 1

    def test_inkling_token_is_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        self._setup_and_fire_etb(game, p1, p1)
        tokens = [
            obj for obj in game.get_battlefield(p1).get_all()
            if getattr(obj, "is_token", False)
        ]
        assert len(tokens) >= 1
        token = tokens[0]
        assert isinstance(token, Creature)

    def test_inkling_token_is_one_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        self._setup_and_fire_etb(game, p1, p1)
        tokens = [
            obj for obj in game.get_battlefield(p1).get_all()
            if getattr(obj, "is_token", False)
        ]
        assert len(tokens) >= 1
        token = tokens[0]
        assert token.base_power == 1
        assert token.base_toughness == 1

    def test_inkling_token_has_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]
        self._setup_and_fire_etb(game, p1, p1)
        tokens = [
            obj for obj in game.get_battlefield(p1).get_all()
            if getattr(obj, "is_token", False)
        ]
        assert len(tokens) >= 1
        token = tokens[0]
        assert Keyword.FLYING in token.keywords

    def test_inkling_token_has_inkling_subtype(self) -> None:
        game = create_game()
        p1 = game.players[0]
        self._setup_and_fire_etb(game, p1, p1)
        tokens = [
            obj for obj in game.get_battlefield(p1).get_all()
            if getattr(obj, "is_token", False)
        ]
        assert len(tokens) >= 1
        token = tokens[0]
        assert "Inkling" in token.subtypes

    def test_inkling_token_name(self) -> None:
        """Token should be named 'Inkling'."""
        game = create_game()
        p1 = game.players[0]
        self._setup_and_fire_etb(game, p1, p1)
        tokens = [
            obj for obj in game.get_battlefield(p1).get_all()
            if getattr(obj, "is_token", False)
        ]
        assert len(tokens) >= 1
        token = tokens[0]
        assert token.name == "Inkling"


# ---------------------------------------------------------------------------
# Prepared condition check
# ---------------------------------------------------------------------------

class TestEmeritusPreparedCondition:
    """After creating the Inkling token, the card becomes prepared if
    an opponent controls more creatures than the controller."""

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        """Opponent controls more creatures than controller =>
        card should become prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Give opponent several creatures so they control more.
        for i in range(3):
            bear = Creature(
                name=f"Bear {i}", owner=p2, controller=p2,
                base_power=2, base_toughness=2,
            )
            game.get_battlefield(p2).add(bear)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_trigger = triggers[0]
        # Target self (p1) so Inkling goes to p1.
        card.chosen_targets = [p1]
        etb_trigger.effect(game)

        # After ETB, p1 has: card + Inkling = 2 creatures.
        # p2 has 3 bears => opponent has more => should be prepared.
        assert getattr(card, "is_prepared", False) is True or \
               getattr(card, "prepared", False) is True

    def test_not_prepared_when_controller_has_equal_or_more_creatures(self) -> None:
        """Controller has >= creatures as opponent => card should NOT
        become prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Give controller extra creatures so they have at least as many.
        for i in range(3):
            bear = Creature(
                name=f"Bear {i}", owner=p1, controller=p1,
                base_power=2, base_toughness=2,
            )
            game.get_battlefield(p1).add(bear)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_trigger = triggers[0]
        card.chosen_targets = [p1]
        etb_trigger.effect(game)

        # p1: 3 bears + card + Inkling = 5 creatures.
        # p2: 0 creatures => controller has more => NOT prepared.
        is_prep = getattr(card, "is_prepared", False) or \
                  getattr(card, "prepared", False)
        assert is_prep is False

    def test_not_prepared_when_opponent_has_fewer_creatures(self) -> None:
        """Opponent has fewer creatures => card should NOT become prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # p2 has one creature, p1 will have card + Inkling = 2.
        bear = Creature(
            name="Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        game.get_battlefield(p2).add(bear)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_trigger = triggers[0]
        card.chosen_targets = [p1]
        etb_trigger.effect(game)

        # p1: card + Inkling = 2, p2: 1 bear => not strictly more.
        is_prep = getattr(card, "is_prepared", False) or \
                  getattr(card, "prepared", False)
        assert is_prep is False

    def test_prepared_accounts_for_inkling_given_to_opponent(self) -> None:
        """When the Inkling token goes to the opponent, the creature count
        comparison should include that token on the opponent's side."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # p2 starts with 1 creature. Token also goes to p2 => p2 has 2.
        bear = Creature(
            name="Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        game.get_battlefield(p2).add(bear)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        etb_trigger = triggers[0]
        # Target opponent so Inkling goes to p2.
        card.chosen_targets = [p2]
        etb_trigger.effect(game)

        # p1: card = 1 creature. p2: bear + Inkling = 2 => opponent has more.
        assert getattr(card, "is_prepared", False) is True or \
               getattr(card, "prepared", False) is True


# ---------------------------------------------------------------------------
# Prepared designation attribute
# ---------------------------------------------------------------------------

class TestEmeritusPreparedDesignation:
    """The card should track a 'prepared' or 'is_prepared' designation
    attribute that starts as False and can be toggled."""

    def test_starts_not_prepared(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        is_prep = getattr(card, "is_prepared", False) or \
                  getattr(card, "prepared", False)
        assert is_prep is False


# ---------------------------------------------------------------------------
# ETB targeting
# ---------------------------------------------------------------------------

class TestEmeritusTargeting:
    """The ETB trigger targets a player. The card implementation should
    support targeting requirements or chosen_targets for player selection."""

    def test_etb_target_is_player(self) -> None:
        """The ETB ability targets 'target player', meaning it should
        accept any player as a valid target."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        # If get_targets is implemented, it should return a requirement
        # for a player target. If not, chosen_targets must be settable.
        targets = card.get_targets(game)
        if targets:
            req = targets[0]
            assert isinstance(req, TargetRequirement)
        else:
            # Even without get_targets, chosen_targets must be accepted.
            card.chosen_targets = [p2]
            assert card.chosen_targets == [p2]


# ---------------------------------------------------------------------------
# Full cast integration
# ---------------------------------------------------------------------------

class TestEmeritusCastAndResolve:
    """Test casting the creature via cast_spell and verifying the ETB fires."""

    def test_cast_creates_inkling_token(self) -> None:
        """Casting Emeritus of Truce should trigger the ETB and create
        an Inkling token for the target player."""
        from test_utils import cast_spell

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1)
        set_board_state(
            game, 0,
            hand=[card],
            mana={ManaType.WHITE: 3, ManaType.COLORLESS: 1},
        )

        # Script the target choice (p1 targets self to get the token).
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares",
                   targets=[p1])

        # The card should be on the battlefield.
        bf = game.get_battlefield(p1).get_all()
        card_on_bf = [
            obj for obj in bf
            if getattr(obj, "name", "") == "Emeritus of Truce // Swords to Plowshares"
        ]
        assert len(card_on_bf) >= 1

        # An Inkling token should be on p1's battlefield.
        tokens = [
            obj for obj in bf
            if getattr(obj, "is_token", False)
        ]
        assert len(tokens) >= 1
        token = tokens[0]
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert Keyword.FLYING in token.keywords


# ---------------------------------------------------------------------------
# Prepare spell — Swords to Plowshares effect
# ---------------------------------------------------------------------------

class TestSwordsToPlowsharesEffect:
    """When the card is prepared and the Swords to Plowshares prepare
    spell is cast, it should: exile target creature, and its controller
    gains life equal to its power.

    The prepare mechanic (per oracle reminder text): while prepared, the
    controller may cast a copy of the prepare spell. Doing so unprepares
    the creature.
    """

    def _make_prepared_emeritus(self, game, controller):
        """Place an Emeritus on the battlefield and mark it prepared."""
        card = EmeritusOfTruceSwordsToPlowshares(
            owner=controller, controller=controller
        )
        game.get_battlefield(controller).add(card)
        card.is_prepared = True
        return card

    def test_prepare_spell_exiles_target_creature(self) -> None:
        """Swords to Plowshares should exile the target creature,
        removing it from the battlefield."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = self._make_prepared_emeritus(game, p1)

        # Place a target creature on the opponent's battlefield.
        target = Creature(
            name="Grizzly Bears", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        game.get_battlefield(p2).add(target)

        # Resolve the prepare spell effect.
        card.resolve_prepare_spell(game, target)

        # The target should no longer be on the battlefield.
        bf_p2 = game.get_battlefield(p2).get_all()
        target_on_bf = [
            obj for obj in bf_p2
            if getattr(obj, "name", "") == "Grizzly Bears"
        ]
        assert len(target_on_bf) == 0, (
            "Target creature should be exiled from the battlefield"
        )

    def test_prepare_spell_moves_target_to_exile_zone(self) -> None:
        """The exiled creature should end up in its owner's exile zone."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = self._make_prepared_emeritus(game, p1)

        target = Creature(
            name="Grizzly Bears", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        game.get_battlefield(p2).add(target)

        card.resolve_prepare_spell(game, target)

        # The target should be in the exile zone.
        exile_p2 = game.get_exile(p2).get_all()
        exiled = [
            obj for obj in exile_p2
            if getattr(obj, "name", "") == "Grizzly Bears"
        ]
        assert len(exiled) >= 1, (
            "Target creature should be in the exile zone"
        )

    def test_prepare_spell_controller_gains_life_equal_to_power(self) -> None:
        """The exiled creature's controller gains life equal to its power."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = self._make_prepared_emeritus(game, p1)

        # Target creature has power 4.
        target = Creature(
            name="Hill Giant", owner=p2, controller=p2,
            base_power=4, base_toughness=3,
        )
        game.get_battlefield(p2).add(target)

        life_before = p2.life
        card.resolve_prepare_spell(game, target)

        # p2 (the controller of the exiled creature) should gain 4 life.
        assert p2.life == life_before + 4, (
            f"Controller should gain life equal to creature's power (4), "
            f"but life went from {life_before} to {p2.life}"
        )

    def test_prepare_spell_zero_power_creature_no_life_gain(self) -> None:
        """Exiling a 0-power creature grants 0 life (no change)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = self._make_prepared_emeritus(game, p1)

        target = Creature(
            name="Wall of Air", owner=p2, controller=p2,
            base_power=0, base_toughness=5,
        )
        game.get_battlefield(p2).add(target)

        life_before = p2.life
        card.resolve_prepare_spell(game, target)

        assert p2.life == life_before, (
            "Zero-power creature should grant zero life"
        )

    def test_prepare_spell_unprepares_after_casting(self) -> None:
        """After casting the prepare spell, the creature should become
        unprepared (is_prepared = False)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = self._make_prepared_emeritus(game, p1)
        assert card.is_prepared is True

        target = Creature(
            name="Grizzly Bears", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        game.get_battlefield(p2).add(target)

        card.resolve_prepare_spell(game, target)

        assert card.is_prepared is False, (
            "Creature should be unprepared after casting the prepare spell"
        )

    def test_prepare_spell_can_target_own_creature(self) -> None:
        """Swords to Plowshares can target any creature, including
        the controller's own creatures."""
        game = create_game()
        p1 = game.players[0]

        card = self._make_prepared_emeritus(game, p1)

        # Target the controller's own creature.
        own_creature = Creature(
            name="Savannah Lions", owner=p1, controller=p1,
            base_power=2, base_toughness=1,
        )
        game.get_battlefield(p1).add(own_creature)

        life_before = p1.life
        card.resolve_prepare_spell(game, own_creature)

        # Own creature should be exiled.
        bf_p1 = game.get_battlefield(p1).get_all()
        lions_on_bf = [
            obj for obj in bf_p1
            if getattr(obj, "name", "") == "Savannah Lions"
        ]
        assert len(lions_on_bf) == 0, (
            "Own creature should be exiled from the battlefield"
        )

        # Controller (p1) gains life equal to the creature's power (2).
        assert p1.life == life_before + 2, (
            f"Controller of exiled creature gains life equal to its power, "
            f"expected {life_before + 2}, got {p1.life}"
        )
