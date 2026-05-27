"""Rewritten audited tests for Lorehold, the Historian (sos_201).

8 tests covering oracle behavior:
1. Identity — name, mana_cost {3}{R}{W}, 5/5, Legendary Creature — Elder Dragon,
   Flying + Haste.
2. Miracle grant to instants and sorceries (not creatures) in hand while on bf.
3. Grant removed when Lorehold leaves the battlefield.
4. Miracle cast on first draw this turn (instant/sorcery).
5. No miracle on subsequent draws.
6. Opponent-upkeep discard-to-draw: declined path.
7. Opponent-upkeep discard-to-draw: accepted path.
8. No trigger on controller's own upkeep.
"""

from __future__ import annotations

import pytest

from card_impl import LoreholdTheHistorian

from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.game import destroy, draw_card
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import (
    card_colors,
    create_game,
    resolve_top,
    set_battlefield,
    set_hand,
    set_library_top,
    set_mana_pool,
)


class TestIdentity:
    """Test 1: Verify card identity — name, cost, stats, types, keywords."""

    def test_identity(self) -> None:
        """{3}{R}{W} 5/5 Legendary Creature — Elder Dragon, Flying, Haste."""
        card = LoreholdTheHistorian(name="Lorehold, the Historian", owner=None)

        # Name
        assert card.name == "Lorehold, the Historian"

        # Mana cost: {3}{R}{W} → generic=3, 1 red, 1 white → CMC 5
        assert card.mana_cost.generic == 3
        assert card.mana_cost.pips.get(ManaType.RED) == 1
        assert card.mana_cost.pips.get(ManaType.WHITE) == 1
        assert card.mana_cost.cmc == 5

        # Colors: Red and White
        colors = card_colors(card)
        assert "R" in colors
        assert "W" in colors

        # Type line: Legendary Creature — Elder Dragon
        assert CardType.CREATURE in card.card_types
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

        # Stats
        assert card.base_power == 5
        assert card.base_toughness == 5

        # Keywords
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords


class TestMiracleGrantToInstantsAndSorceries:
    """Test 2: While Lorehold is on the battlefield, instants/sorceries in
    controller's hand get miracle_cost={2}, but creatures do not."""

    def test_miracle_granted_to_instants_and_sorceries_not_creatures(self) -> None:
        """Instants and sorceries in hand gain miracle_cost; creatures do not."""
        game = create_game()
        player = game.players[0]

        lorehold = LoreholdTheHistorian(owner=player)
        bolt = Instant(name="Lightning Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}), owner=player)
        divination = Sorcery(name="Divination", mana_cost=ManaCost(generic=2, pips={ManaType.BLUE: 1}), owner=player)
        bear = Creature(name="Grizzly Bears", mana_cost=ManaCost(generic=1, pips={ManaType.GREEN: 1}), owner=player, base_power=2, base_toughness=2)

        # Put Lorehold on the battlefield (which triggers register_triggers via _set_zone)
        set_battlefield(game, 0, [lorehold])
        # Put cards in hand
        set_hand(game, 0, [bolt, divination, bear])

        # Apply continuous effects so the miracle_cost is granted
        game.effect_manager.apply_all(game)

        # Instants and sorceries should have miracle_cost = ManaCost(generic=2)
        assert hasattr(bolt, "miracle_cost") and bolt.miracle_cost is not None, \
            "Instant in hand should have miracle_cost"
        assert bolt.miracle_cost.cmc == 2

        assert hasattr(divination, "miracle_cost") and divination.miracle_cost is not None, \
            "Sorcery in hand should have miracle_cost"
        assert divination.miracle_cost.cmc == 2

        # Creature should NOT have miracle_cost
        has_miracle = hasattr(bear, "miracle_cost") and bear.miracle_cost is not None
        assert not has_miracle, "Creature in hand should NOT get miracle_cost"


class TestGrantRemovedWhenLoreholdLeaves:
    """Test 3: After Lorehold leaves the battlefield, cards in hand no longer
    have miracle_cost."""

    def test_miracle_grant_removed_on_leave(self) -> None:
        """When Lorehold is destroyed, instants/sorceries in hand lose miracle_cost."""
        game = create_game()
        player = game.players[0]

        lorehold = LoreholdTheHistorian(owner=player)
        bolt = Instant(name="Lightning Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}), owner=player)

        set_battlefield(game, 0, [lorehold])
        set_hand(game, 0, [bolt])
        game.effect_manager.apply_all(game)

        # Confirm miracle_cost is granted
        assert hasattr(bolt, "miracle_cost") and bolt.miracle_cost is not None

        # Destroy Lorehold
        destroy(game, lorehold)

        # After removal, apply_all should no longer grant miracle_cost
        game.effect_manager.apply_all(game)

        has_miracle = hasattr(bolt, "miracle_cost") and bolt.miracle_cost is not None
        assert not has_miracle, \
            "After Lorehold leaves, instants/sorceries in hand should NOT have miracle_cost"


class TestMiracleCastOnFirstDraw:
    """Test 4: When controller draws a card (first draw this turn) that is an
    instant/sorcery, can cast it for miracle cost {2}."""

    def test_miracle_cast_on_first_draw(self) -> None:
        """First-drawn instant/sorcery this turn triggers miracle — can cast for {2}."""
        # Script: choose yes when offered miracle cast
        game = create_game(scripts=([True], []))
        player = game.players[0]

        lorehold = LoreholdTheHistorian(owner=player)
        bolt = Instant(name="Lightning Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}), owner=player)

        set_battlefield(game, 0, [lorehold])
        # Library top has the bolt
        set_library_top(game, 0, [bolt])
        # Give player {2} mana to pay miracle cost
        set_mana_pool(game, 0, {ManaType.COLORLESS: 2})

        # Ensure it's the first draw this turn
        player.cards_drawn_this_turn = 0

        # Draw the card — triggers miracle
        drawn = draw_card(game, player)
        assert drawn is bolt

        # The miracle trigger should put something on the stack; resolve it
        if not game.stack.is_empty():
            resolve_top(game)

        # The bolt should have been cast (moved from hand to stack or resolved to graveyard)
        hand_cards = player.zones[Zone.HAND].get_all()
        assert bolt not in hand_cards, \
            "After miracle cast, the card should no longer be in hand"


class TestNoMiracleOnSubsequentDraws:
    """Test 5: Second+ draw in the same turn does NOT trigger miracle."""

    def test_no_miracle_on_second_draw(self) -> None:
        """Second draw this turn should NOT trigger miracle."""
        # Script: if miracle were offered (it shouldn't be), say yes
        game = create_game(scripts=([True], []))
        player = game.players[0]

        lorehold = LoreholdTheHistorian(owner=player)
        bolt = Instant(name="Lightning Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}), owner=player)

        set_battlefield(game, 0, [lorehold])
        set_library_top(game, 0, [bolt])
        set_mana_pool(game, 0, {ManaType.COLORLESS: 2})

        # Simulate that the player already drew one card this turn
        player.cards_drawn_this_turn = 1

        # Draw the second card
        drawn = draw_card(game, player)
        assert drawn is bolt

        # Stack should be empty — no miracle trigger
        assert game.stack.is_empty(), \
            "Miracle should NOT trigger on second+ draw this turn"

        # Card should remain in hand
        hand_cards = player.zones[Zone.HAND].get_all()
        assert bolt in hand_cards, \
            "Card should stay in hand when miracle doesn't trigger"


class TestOpponentUpkeepDiscardDeclined:
    """Test 6: During opponent upkeep, trigger offers discard; if declined,
    nothing happens."""

    def test_discard_to_draw_declined(self) -> None:
        """Player declines to discard during opponent's upkeep — no effect."""
        # Script: choose_yes_no -> False (decline discard)
        game = create_game(scripts=([False], []))
        player = game.players[0]
        opponent = game.players[1]

        lorehold = LoreholdTheHistorian(owner=player)
        hand_card = Instant(name="Shock", mana_cost=ManaCost(pips={ManaType.RED: 1}), owner=player)

        set_battlefield(game, 0, [lorehold])
        set_hand(game, 0, [hand_card])

        # Set opponent as active player (it's opponent's upkeep)
        game.active_player_index = 1

        # Fire upkeep event
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # Resolve the trigger on the stack
        if not game.stack.is_empty():
            resolve_top(game)

        # Hand should be unchanged — card still there, no draw happened
        hand_cards = player.zones[Zone.HAND].get_all()
        assert hand_card in hand_cards, \
            "Declining discard should leave hand unchanged"
        assert len(hand_cards) == 1, \
            "No extra cards should be drawn when declining"


class TestOpponentUpkeepDiscardAccepted:
    """Test 7: During opponent upkeep, if discard accepted, controller discards
    then draws."""

    def test_discard_to_draw_accepted(self) -> None:
        """Player accepts discard during opponent's upkeep — discards one, draws one."""
        shock = Instant(name="Shock", mana_cost=ManaCost(pips={ManaType.RED: 1}), owner=None)
        new_card = Instant(name="New Card", mana_cost=ManaCost(generic=1), owner=None)

        # Script: choose_yes_no -> True (accept), choose_card -> shock (discard it)
        # The drawn card may also trigger miracle choose_yes_no, decline it
        game = create_game(scripts=([True, shock, False], []))
        player = game.players[0]
        opponent = game.players[1]

        lorehold = LoreholdTheHistorian(owner=player)

        set_battlefield(game, 0, [lorehold])
        set_hand(game, 0, [shock])
        set_library_top(game, 0, [new_card])

        # Set opponent as active player (it's opponent's upkeep)
        game.active_player_index = 1

        # Track initial state
        initial_hand = list(player.zones[Zone.HAND].get_all())
        assert shock in initial_hand

        # Fire upkeep event
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # Resolve the trigger
        if not game.stack.is_empty():
            resolve_top(game)

        # Shock should be in graveyard (discarded)
        gy_cards = player.zones[Zone.GRAVEYARD].get_all()
        assert shock in gy_cards, "Discarded card should be in graveyard"

        # New card should have been drawn into hand
        hand_cards = player.zones[Zone.HAND].get_all()
        assert new_card in hand_cards, "Should have drawn a new card after discarding"


class TestNoTriggerOnControllerUpkeep:
    """Test 8: During controller's own upkeep, the discard-draw trigger does
    NOT fire."""

    def test_no_trigger_on_own_upkeep(self) -> None:
        """Controller's upkeep should NOT trigger the discard-to-draw ability."""
        # If trigger fires unexpectedly, script exhaustion will cause an error
        game = create_game(scripts=([], []))
        player = game.players[0]

        lorehold = LoreholdTheHistorian(owner=player)
        hand_card = Instant(name="Shock", mana_cost=ManaCost(pips={ManaType.RED: 1}), owner=player)

        set_battlefield(game, 0, [lorehold])
        set_hand(game, 0, [hand_card])

        # Set controller as active player (it's controller's upkeep)
        game.active_player_index = 0

        # Fire upkeep event
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # Stack should be empty — no trigger
        assert game.stack.is_empty(), \
            "Discard-to-draw should NOT trigger on controller's own upkeep"

        # Hand should be unchanged
        hand_cards = player.zones[Zone.HAND].get_all()
        assert hand_card in hand_cards
        assert len(hand_cards) == 1
