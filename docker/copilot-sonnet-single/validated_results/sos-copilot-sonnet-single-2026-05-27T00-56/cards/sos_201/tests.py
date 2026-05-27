"""Tests for sos_201 — Lorehold, the Historian.

Requirements tested:
1. Static properties: name, mana cost, P/T, creature type, keywords, supertype, subtypes.
2. Upkeep trigger: fires at each *opponent's* upkeep (not own); may discard → draw.
3. Miracle mechanic: each instant/sorcery in the controller's hand receives miracle {2};
   non-instant/non-sorcery cards do not.
"""

from __future__ import annotations

from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state

from cards.sos.sos_201.card_impl import LoreholdTheHistorian


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestLoreholdProperties:
    """Static card data should match the sos_201 spec."""

    def test_name(self) -> None:
        assert LoreholdTheHistorian(owner=None).name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        assert LoreholdTheHistorian(owner=None).mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_base_power(self) -> None:
        assert LoreholdTheHistorian(owner=None).base_power == 5

    def test_base_toughness(self) -> None:
        assert LoreholdTheHistorian(owner=None).base_toughness == 5

    def test_is_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert isinstance(card, Creature)

    def test_has_flying(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.HASTE in card.keywords

    def test_is_legendary(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes_include_elder_and_dragon(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes


# ---------------------------------------------------------------------------
# Opponent's upkeep trigger
# ---------------------------------------------------------------------------

class TestLoreholdUpkeepTrigger:
    """At the beginning of each opponent's upkeep, may discard → draw."""

    def _find_upkeep_trigger(self, game, lorehold):
        """Return the BeginningOfUpkeepTriggeredEvent trigger for lorehold."""
        return next(
            (
                t
                for t in game.trigger_manager.get_triggers_for_source(lorehold)
                if t.event_type is BeginningOfUpkeepTriggeredEvent
            ),
            None,
        )

    def test_register_triggers_registers_upkeep_trigger(self) -> None:
        """register_triggers must add at least one BeginningOfUpkeepTriggeredEvent trigger."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        before = len(game.trigger_manager._triggers)
        lorehold.register_triggers(game)
        after = len(game.trigger_manager._triggers)
        assert after > before, "register_triggers must add at least one trigger"

    def test_upkeep_trigger_event_type(self) -> None:
        """The registered trigger must watch BeginningOfUpkeepTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        lorehold.register_triggers(game)
        trigger = self._find_upkeep_trigger(game, lorehold)
        assert trigger is not None, "No BeginningOfUpkeepTriggeredEvent trigger registered"
        assert trigger.event_type is BeginningOfUpkeepTriggeredEvent

    def test_upkeep_trigger_fires_during_opponent_upkeep(self) -> None:
        """Trigger condition returns True when the active player is an opponent."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        lorehold.register_triggers(game)
        trigger = self._find_upkeep_trigger(game, lorehold)
        assert trigger is not None

        # Simulate p2's turn (opponent's upkeep)
        game.active_player_index = 1
        event = BeginningOfUpkeepTriggeredEvent()
        assert trigger.condition(game, event) is True

    def test_upkeep_trigger_does_not_fire_during_own_upkeep(self) -> None:
        """Trigger condition returns False when the active player is the controller."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        lorehold.register_triggers(game)
        trigger = self._find_upkeep_trigger(game, lorehold)
        assert trigger is not None

        # Simulate p1's own upkeep (active player is controller)
        game.active_player_index = 0
        event = BeginningOfUpkeepTriggeredEvent()
        assert trigger.condition(game, event) is False

    def test_upkeep_effect_discard_then_draw(self) -> None:
        """When the controller discards a card, they draw a card (net hand change = 0)."""
        from engine.card import CardImpl

        game = create_game(scripts=([True], []))  # p1 answers yes to discard
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        lorehold.register_triggers(game)

        # Give p1 a card in hand and a card in library
        hand_card = CardImpl(name="Fodder Card", owner=p1, controller=p1)
        hand_card.card_types = {CardType.INSTANT}
        lib_card = CardImpl(name="Library Card", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[hand_card])
        p1.zones[Zone.LIBRARY].add(lib_card)

        trigger = self._find_upkeep_trigger(game, lorehold)
        assert trigger is not None

        hand_before = len(p1.zones[Zone.HAND].get_all())
        trigger.effect(game)
        hand_after = len(p1.zones[Zone.HAND].get_all())

        # Discarded one, drew one → net change is 0
        assert hand_after == hand_before

        # The original hand_card should now be in the graveyard
        assert p1.zones[Zone.GRAVEYARD].contains(hand_card)

    def test_upkeep_effect_no_discard_no_draw(self) -> None:
        """When the controller declines to discard, they do not draw a card."""
        from engine.card import CardImpl

        game = create_game(scripts=([False], []))  # p1 answers no to discard
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        lorehold.register_triggers(game)

        hand_card = CardImpl(name="Safe Card", owner=p1, controller=p1)
        hand_card.card_types = {CardType.INSTANT}
        lib_card = CardImpl(name="Library Card", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[hand_card])
        p1.zones[Zone.LIBRARY].add(lib_card)

        trigger = self._find_upkeep_trigger(game, lorehold)
        assert trigger is not None

        hand_before = len(p1.zones[Zone.HAND].get_all())
        trigger.effect(game)
        hand_after = len(p1.zones[Zone.HAND].get_all())

        # No card discarded or drawn
        assert hand_after == hand_before
        assert not p1.zones[Zone.GRAVEYARD].contains(hand_card)

    def test_upkeep_effect_empty_hand_is_noop(self) -> None:
        """If the controller has no cards in hand, the trigger effect resolves safely."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        lorehold.register_triggers(game)

        # Empty hand
        set_board_state(game, 0, hand=[])

        trigger = self._find_upkeep_trigger(game, lorehold)
        assert trigger is not None

        # Must not raise
        trigger.effect(game)
        assert len(p1.zones[Zone.HAND].get_all()) == 0


# ---------------------------------------------------------------------------
# Miracle mechanic — "each instant and sorcery in your hand has miracle {2}"
# ---------------------------------------------------------------------------

class TestLoreholdMiracleMechanic:
    """Instants and sorceries in hand should receive miracle {2} via Lorehold's static ability.

    The expected implementation: register_triggers registers a DrawsCardTriggeredEvent
    trigger that sets ``miracle_cost = ManaCost.parse("{2}")`` on drawn instants/sorceries
    when it is the first card drawn this turn.  This is the minimum observable contract.
    """

    def _find_draw_trigger(self, game, lorehold):
        """Return the DrawsCardTriggeredEvent trigger for lorehold, if any."""
        return next(
            (
                t
                for t in game.trigger_manager.get_triggers_for_source(lorehold)
                if t.event_type is DrawsCardTriggeredEvent
            ),
            None,
        )

    def test_register_triggers_registers_draw_trigger_for_miracle(self) -> None:
        """register_triggers must add a DrawsCardTriggeredEvent trigger for miracle."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        lorehold.register_triggers(game)
        trigger = self._find_draw_trigger(game, lorehold)
        assert trigger is not None, (
            "register_triggers should register a DrawsCardTriggeredEvent trigger "
            "to support the miracle {2} static ability"
        )

    def test_drawn_instant_gets_miracle_cost_on_first_draw(self) -> None:
        """An instant drawn as the first card this turn gets miracle_cost = {2}."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        lorehold.register_triggers(game)

        instant_card = Instant(
            name="Test Instant", owner=p1, controller=p1
        )
        instant_card.card_types = {CardType.INSTANT}

        # Simulate first draw of the turn
        p1.cards_drawn_this_turn = 1  # just drawn

        trigger = self._find_draw_trigger(game, lorehold)
        assert trigger is not None

        event = DrawsCardTriggeredEvent(player=p1, card=instant_card)
        if trigger.condition is None or trigger.condition(game, event):
            trigger.effect(game)  # may be a no-op until effect reads the event

        # The simplest path: fire event through trigger_manager and check card
        # We simulate it by directly applying the miracle_cost grant
        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p1, card=instant_card)
        )

        miracle_cost = getattr(instant_card, "miracle_cost", None)
        assert miracle_cost == ManaCost.parse("{2}"), (
            f"Expected miracle_cost={{2}} on drawn instant; got {miracle_cost!r}"
        )

    def test_drawn_sorcery_gets_miracle_cost_on_first_draw(self) -> None:
        """A sorcery drawn as the first card this turn gets miracle_cost = {2}."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        lorehold.register_triggers(game)

        sorcery_card = Sorcery(
            name="Test Sorcery", owner=p1, controller=p1
        )
        sorcery_card.card_types = {CardType.SORCERY}

        p1.cards_drawn_this_turn = 1

        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p1, card=sorcery_card)
        )

        miracle_cost = getattr(sorcery_card, "miracle_cost", None)
        assert miracle_cost == ManaCost.parse("{2}"), (
            f"Expected miracle_cost={{2}} on drawn sorcery; got {miracle_cost!r}"
        )

    def test_non_instant_sorcery_does_not_get_miracle_cost(self) -> None:
        """An instant gets miracle_cost {2}; a creature drawn in the same turn does not.

        We pair a positive assertion (instant gets it) with the negative assertion
        (creature does not) so this test fails before implementation.
        """
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        lorehold.register_triggers(game)

        instant_card = Instant(name="Paired Instant", owner=p1, controller=p1)
        instant_card.card_types = {CardType.INSTANT}

        creature_card = Creature(
            name="Test Creature", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        creature_card.card_types = {CardType.CREATURE}

        p1.cards_drawn_this_turn = 1

        # Fire for the instant first — it should gain miracle_cost
        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p1, card=instant_card)
        )
        assert getattr(instant_card, "miracle_cost", None) == ManaCost.parse("{2}"), (
            "Instant drawn as first card should receive miracle_cost {2}"
        )

        # Fire for the creature — it must NOT gain miracle_cost
        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p1, card=creature_card)
        )
        miracle_cost = getattr(creature_card, "miracle_cost", None)
        assert miracle_cost != ManaCost.parse("{2}"), (
            "Non-instant/non-sorcery cards must not receive miracle_cost {2}"
        )

    def test_second_drawn_card_does_not_get_miracle_cost(self) -> None:
        """The first draw gets miracle {2}; a second draw of the same instant type does not.

        We check both so this test fails before implementation (the first assertion will fail).
        """
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        lorehold.register_triggers(game)

        first_instant = Instant(name="First Instant", owner=p1, controller=p1)
        first_instant.card_types = {CardType.INSTANT}
        late_instant = Instant(name="Late Instant", owner=p1, controller=p1)
        late_instant.card_types = {CardType.INSTANT}

        # First draw — should get miracle
        p1.cards_drawn_this_turn = 1
        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p1, card=first_instant)
        )
        assert getattr(first_instant, "miracle_cost", None) == ManaCost.parse("{2}"), (
            "First drawn instant must receive miracle_cost {2}"
        )

        # Second draw — must NOT get miracle
        p1.cards_drawn_this_turn = 2
        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p1, card=late_instant)
        )
        miracle_cost = getattr(late_instant, "miracle_cost", None)
        assert miracle_cost != ManaCost.parse("{2}"), (
            "Miracle {2} should only apply when the card was the first drawn this turn"
        )


# ---------------------------------------------------------------------------
# ETB iteration — "cards already in hand when Lorehold enters the battlefield"
# ---------------------------------------------------------------------------

class TestLoreholdETBHandIteration:
    """on_resolve() must grant miracle {2} to all instants/sorceries already in the
    controller's hand at the time Lorehold enters the battlefield.

    The engine calls card.on_resolve(game) for each creature that resolves from
    the stack (see engine/casting.py).  Overriding on_resolve is therefore the
    correct ETB hook for this behaviour.
    """

    def test_etb_grants_miracle_to_instant_already_in_hand(self) -> None:
        """An instant already in hand receives miracle_cost {2} when Lorehold enters."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        instant_card = Instant(name="Pre-ETB Instant", owner=p1, controller=p1)
        instant_card.card_types = {CardType.INSTANT}
        set_board_state(game, 0, hand=[instant_card])

        # Simulate ETB — on_resolve is the hook the engine calls
        lorehold.on_resolve(game)

        miracle_cost = getattr(instant_card, "miracle_cost", None)
        assert miracle_cost == ManaCost.parse("{2}"), (
            f"Instant in hand at ETB should have miracle_cost {{2}}; got {miracle_cost!r}"
        )

    def test_etb_grants_miracle_to_sorcery_already_in_hand(self) -> None:
        """A sorcery already in hand receives miracle_cost {2} when Lorehold enters."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        sorcery_card = Sorcery(name="Pre-ETB Sorcery", owner=p1, controller=p1)
        sorcery_card.card_types = {CardType.SORCERY}
        set_board_state(game, 0, hand=[sorcery_card])

        lorehold.on_resolve(game)

        miracle_cost = getattr(sorcery_card, "miracle_cost", None)
        assert miracle_cost == ManaCost.parse("{2}"), (
            f"Sorcery in hand at ETB should have miracle_cost {{2}}; got {miracle_cost!r}"
        )

    def test_etb_grants_miracle_to_all_instants_and_sorceries_in_hand(self) -> None:
        """All instant and sorcery cards in hand receive miracle {2} at ETB; others do not."""
        from engine.card import Creature as EngineCreature

        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        instant1 = Instant(name="Instant Alpha", owner=p1, controller=p1)
        instant1.card_types = {CardType.INSTANT}
        sorcery1 = Sorcery(name="Sorcery Beta", owner=p1, controller=p1)
        sorcery1.card_types = {CardType.SORCERY}
        creature_card = EngineCreature(
            name="Creature Gamma", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        creature_card.card_types = {CardType.CREATURE}

        set_board_state(game, 0, hand=[instant1, sorcery1, creature_card])

        lorehold.on_resolve(game)

        # Both spell types must gain miracle cost
        assert getattr(instant1, "miracle_cost", None) == ManaCost.parse("{2}"), (
            "Instant in hand at ETB must have miracle_cost {2}"
        )
        assert getattr(sorcery1, "miracle_cost", None) == ManaCost.parse("{2}"), (
            "Sorcery in hand at ETB must have miracle_cost {2}"
        )
        # The creature must NOT gain miracle cost
        miracle_cost = getattr(creature_card, "miracle_cost", None)
        assert miracle_cost != ManaCost.parse("{2}"), (
            "Creature in hand at ETB must NOT receive miracle_cost {2}"
        )

    def test_etb_does_not_apply_miracle_to_opponent_hand(self) -> None:
        """Miracle {2} is only applied to the *controller's* hand, not the opponent's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        opponent_instant = Instant(name="Opponent Instant", owner=p2, controller=p2)
        opponent_instant.card_types = {CardType.INSTANT}
        set_board_state(game, 1, hand=[opponent_instant])

        lorehold.on_resolve(game)

        miracle_cost = getattr(opponent_instant, "miracle_cost", None)
        assert miracle_cost != ManaCost.parse("{2}"), (
            "Miracle {2} must NOT be applied to the opponent's hand cards at ETB"
        )

    def test_etb_with_empty_hand_does_not_raise(self) -> None:
        """on_resolve with an empty hand completes without raising an exception."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        set_board_state(game, 0, hand=[])

        # Must not raise
        lorehold.on_resolve(game)
        assert len(p1.zones[Zone.HAND].get_all()) == 0

    def test_etb_does_not_override_existing_miracle_cost(self) -> None:
        """If a card already has a miracle_cost, on_resolve sets it to {2} (Lorehold's override)."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        instant_card = Instant(name="Pre-Costed Instant", owner=p1, controller=p1)
        instant_card.card_types = {CardType.INSTANT}
        # Simulate a card that already had some miracle cost from another source
        instant_card.miracle_cost = ManaCost.parse("{5}")
        set_board_state(game, 0, hand=[instant_card])

        lorehold.on_resolve(game)

        # Lorehold replaces / grants {2}; both outcomes are acceptable as long as
        # the card has a miracle cost and can be cast for {2} (Lorehold grants {2})
        miracle_cost = getattr(instant_card, "miracle_cost", None)
        assert miracle_cost == ManaCost.parse("{2}"), (
            "Lorehold's ETB should set miracle_cost to {2} even if card had a prior miracle cost"
        )
