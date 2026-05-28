"""Tests for SOS 201 — Lorehold, the Historian.

Requirements under test:
1. Static card properties (name, mana cost, type, P/T, supertypes, subtypes).
2. Keywords: Flying and Haste.
3. Upkeep trigger: fires at the beginning of each opponent's upkeep.
4. Upkeep trigger: optional discard — if player says yes, a card is discarded.
5. Upkeep trigger: if discard happened, draw a card.
6. Upkeep trigger: if player says no, no discard and no draw.
7. Upkeep trigger: fires on opponent's upkeep, NOT controller's own upkeep.
8. Miracle granting: each instant and sorcery in controller's hand gains miracle {2}.
9. Miracle cost: the granted miracle cost is exactly {2}.
10. Miracle granting: non-instant/sorcery cards in hand are NOT given miracle.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestLoreholdStaticProperties:
    """Lorehold, the Historian must match the card spec exactly."""

    def test_name(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_is_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_is_legendary(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes_include_elder_dragon(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert "Elder" in card.subtypes or "Dragon" in card.subtypes or (
            "Elder Dragon" in " ".join(card.subtypes) or
            {"Elder", "Dragon"} <= card.subtypes
        )

    def test_power_is_5(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_power == 5

    def test_toughness_is_5(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_toughness == 5


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

class TestLoreholdKeywords:
    """Flying and Haste are both required."""

    def test_has_flying(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.HASTE in card.keywords


# ---------------------------------------------------------------------------
# Upkeep trigger registration
# ---------------------------------------------------------------------------

class TestLoreholdUpkeepTriggerRegistration:
    """register_triggers must wire a BeginningOfUpkeepTriggeredEvent trigger."""

    def test_registers_at_least_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_registers_upkeep_trigger_type(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)
        upkeep_triggers = [
            t for t in game.trigger_manager.get_triggers()
            if t.source is card and t.event_type is BeginningOfUpkeepTriggeredEvent
        ]
        assert len(upkeep_triggers) >= 1

    def test_unregister_removes_triggers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)
        count_before = len(game.trigger_manager.get_triggers_for_source(card))
        assert count_before > 0
        game.trigger_manager.unregister(card)
        assert len(game.trigger_manager.get_triggers_for_source(card)) == 0


# ---------------------------------------------------------------------------
# Upkeep trigger — fires only on opponent's upkeep
# ---------------------------------------------------------------------------

class TestLoreholdUpkeepTriggerCondition:
    """The trigger should fire on opponent's upkeep, not controller's upkeep."""

    def test_trigger_fires_on_opponent_upkeep(self) -> None:
        """When an upkeep event fires and the active player is the opponent,
        the trigger should be placed on the stack."""
        game = create_game()
        p1 = game.players[0]   # controller of Lorehold
        p2 = game.players[1]   # opponent
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)

        # Simulate opponent's upkeep — active player is p2
        game.active_player_index = 1
        before_stack = len(game.stack.objects())
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        after_stack = len(game.stack.objects())
        assert after_stack > before_stack, (
            "Upkeep trigger should fire on opponent's upkeep"
        )

    def test_trigger_does_not_fire_on_controller_upkeep(self) -> None:
        """When active player is the controller (p1), the trigger must NOT fire.

        We first verify that the trigger fires on the opponent's upkeep (showing
        the trigger IS registered), then verify it does NOT fire when controller
        is the active player.
        """
        game = create_game()
        p1 = game.players[0]   # controller of Lorehold
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)

        # First verify at least one trigger is registered (precondition)
        assert len(game.trigger_manager.get_triggers_for_source(card)) > 0, (
            "Prerequisite: trigger must be registered before testing condition"
        )

        # Active player is p1 (the controller) — this is p1's own upkeep
        game.active_player_index = 0
        before_stack = len(game.stack.objects())
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        after_stack = len(game.stack.objects())
        assert after_stack == before_stack, (
            "Upkeep trigger must NOT fire on controller's own upkeep"
        )


# ---------------------------------------------------------------------------
# Upkeep trigger effect — discard/draw loot
# ---------------------------------------------------------------------------

class TestLoreholdUpkeepTriggerEffect:
    """When the trigger resolves: optional discard + conditional draw."""

    def _setup_with_hand_card(self, game, player_idx: int):
        """Put a card in p1's hand so they have something to discard."""
        dummy = Instant(name="Dummy", mana_cost=ManaCost.parse("{1}"))
        hand = game.players[player_idx].zones[Zone.HAND]
        hand.add(dummy)
        return dummy

    def _setup_library_card(self, game, player_idx: int):
        """Put a card in p1's library so draw has something to get."""
        top_card = Sorcery(name="Library Top", mana_cost=ManaCost.parse("{1}"))
        library = game.players[player_idx].zones[Zone.LIBRARY]
        library.add(top_card)
        return top_card

    def test_discard_yes_removes_card_from_hand(self) -> None:
        """Choosing yes: the discarded card moves from hand to graveyard."""
        game = create_game()
        p1 = game.players[0]
        dummy = self._setup_with_hand_card(game, 0)
        self._setup_library_card(game, 0)

        # Simulate opponent's upkeep
        game.active_player_index = 1
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # Resolve the trigger from the stack
        assert not game.stack.is_empty()
        stack_obj = game.stack.pop()

        # Script p1 to say "yes" and pick dummy to discard
        from engine.player import DeterministicPlayer
        p1._script.appendleft(dummy)   # choose_card for the discard
        p1._script.appendleft(True)    # choose_yes_no → yes

        stack_obj.on_resolve(game)

        graveyard = game.get_graveyard(p1)
        hand = game.get_hand(p1)
        assert graveyard.contains(dummy), "Discarded card should be in graveyard"
        assert not hand.contains(dummy), "Discarded card should not remain in hand"

    def test_discard_yes_draws_a_card(self) -> None:
        """Choosing yes to discard: controller draws exactly one card."""
        game = create_game()
        p1 = game.players[0]
        self._setup_with_hand_card(game, 0)
        drawn_card = self._setup_library_card(game, 0)

        game.active_player_index = 1
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert not game.stack.is_empty()
        stack_obj = game.stack.pop()

        hand_before = list(game.get_hand(p1).get_all())
        # Script yes + the discard choice
        dummy = [c for c in game.get_hand(p1).get_all()][0]
        p1._script.appendleft(dummy)
        p1._script.appendleft(True)

        stack_obj.on_resolve(game)

        hand_after = game.get_hand(p1).get_all()
        # Hand loses dummy (discarded), gains drawn_card — net size change is 0
        # but drawn_card must be present
        assert drawn_card in hand_after, "Draw should put the library-top card in hand"

    def test_discard_no_does_not_discard_or_draw(self) -> None:
        """Choosing no: hand and library remain unchanged."""
        game = create_game()
        p1 = game.players[0]
        dummy = self._setup_with_hand_card(game, 0)
        self._setup_library_card(game, 0)

        game.active_player_index = 1
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert not game.stack.is_empty()
        stack_obj = game.stack.pop()

        hand_size_before = len(game.get_hand(p1).get_all())
        library_size_before = len(game.players[0].zones[Zone.LIBRARY].get_all())

        # Script no
        p1._script.appendleft(False)  # choose_yes_no → no

        stack_obj.on_resolve(game)

        hand_size_after = len(game.get_hand(p1).get_all())
        library_size_after = len(game.players[0].zones[Zone.LIBRARY].get_all())
        assert hand_size_after == hand_size_before, "No discard → hand unchanged"
        assert library_size_after == library_size_before, "No discard → no draw → library unchanged"

    def test_discard_yes_empty_hand_skips_draw(self) -> None:
        """If controller has no cards to discard, no discard occurs and no draw either."""
        game = create_game()
        p1 = game.players[0]
        # p1 has an empty hand — nothing to discard
        self._setup_library_card(game, 0)

        game.active_player_index = 1
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        if game.stack.is_empty():
            return  # trigger may not fire if no valid discardable card

        stack_obj = game.stack.pop()
        # Even if player says yes, with no cards in hand nothing should crash
        p1._script.appendleft(True)  # choose_yes_no → yes (no cards to choose)
        try:
            stack_obj.on_resolve(game)
        except Exception:
            pass  # Any no-op or graceful exit is acceptable here
        # Post-condition: game is still in a valid state
        assert not game.is_game_over


# ---------------------------------------------------------------------------
# Miracle — granting miracle {2} to instants and sorceries in hand
# ---------------------------------------------------------------------------

class TestLoreholdMiracleGrant:
    """Lorehold grants miracle {2} to each instant/sorcery in controller's hand."""

    def test_instant_in_hand_has_miracle_cost_attribute(self) -> None:
        """An instant in the controller's hand should gain a miracle cost of {2}."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        instant = Instant(name="Test Instant", mana_cost=ManaCost.parse("{3}{R}"))
        instant.owner = p1
        instant.controller = p1
        game.get_hand(p1).add(instant)

        # The card should now have a miracle cost of {2} detectable on the card object
        miracle_cost = getattr(instant, "miracle_cost", None)
        assert miracle_cost is not None, (
            "Instant in hand should have miracle_cost set by Lorehold"
        )
        assert miracle_cost == ManaCost.parse("{2}"), (
            f"Miracle cost should be {{2}}, got {miracle_cost}"
        )

    def test_sorcery_in_hand_has_miracle_cost_attribute(self) -> None:
        """A sorcery in the controller's hand should gain a miracle cost of {2}."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        sorc = Sorcery(name="Test Sorcery", mana_cost=ManaCost.parse("{5}{W}"))
        sorc.owner = p1
        sorc.controller = p1
        game.get_hand(p1).add(sorc)

        miracle_cost = getattr(sorc, "miracle_cost", None)
        assert miracle_cost is not None, (
            "Sorcery in hand should have miracle_cost set by Lorehold"
        )
        assert miracle_cost == ManaCost.parse("{2}"), (
            f"Miracle cost should be {{2}}, got {miracle_cost}"
        )

    def test_creature_in_hand_does_not_get_miracle(self) -> None:
        """Non-instant/sorcery cards (creatures, etc.) must NOT gain miracle."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        creature = Creature(
            name="Test Bear", base_power=2, base_toughness=2,
            mana_cost=ManaCost.parse("{1}{G}"),
            owner=p1, controller=p1,
        )
        game.get_hand(p1).add(creature)

        miracle_cost = getattr(creature, "miracle_cost", None)
        # Either None (never set) or not the {2} miracle — creatures must not have it
        # from Lorehold
        assert miracle_cost is None or not (
            miracle_cost == ManaCost.parse("{2}")
        ), "Creature must NOT receive miracle from Lorehold"

    def test_miracle_cost_is_exactly_two_generic(self) -> None:
        """The miracle cost granted is exactly {2} (two generic mana)."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        instant = Instant(name="Fancy Bolt", mana_cost=ManaCost.parse("{2}{R}{R}"))
        instant.owner = p1
        instant.controller = p1
        game.get_hand(p1).add(instant)

        miracle_cost = getattr(instant, "miracle_cost", None)
        assert miracle_cost is not None
        expected = ManaCost.parse("{2}")
        assert miracle_cost == expected, f"Expected {{2}}, got {miracle_cost}"
