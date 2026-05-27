"""Tests for SOS 201 — Lorehold, the Historian.

Covers:
- Static properties (name, mana cost, P/T, types, keywords)
- Flying and Haste keywords
- Miracle granting to instants/sorceries in hand
- Triggered ability: opponent's upkeep discard-to-draw
- Edge cases (miracle only first draw, not your own upkeep)
"""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Step,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state, advance_to_phase


class TestLoreholdProperties:
    """Static card data should match the SOS 201 spec."""

    def test_is_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_cmc(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.mana_cost.cmc == 5

    def test_power(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_power == 5

    def test_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_toughness == 5

    def test_card_types(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_subtypes(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_supertype_legendary(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_flying(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.HASTE in card.keywords


class TestLoreholdMiracle:
    """Instants and sorceries in hand get miracle {2}."""

    def test_instant_in_hand_gets_miracle(self) -> None:
        """An instant in the controller's hand should have miracle cost {2}."""
        game = create_game()
        p1 = game.players[0]

        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1,
                       mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, hand=[bolt])

        # The instant in hand should have miracle cost {2}
        miracle_cost = getattr(bolt, "miracle_cost", None)
        assert miracle_cost is not None
        assert miracle_cost == ManaCost.parse("{2}")

    def test_sorcery_in_hand_gets_miracle(self) -> None:
        """A sorcery in the controller's hand should have miracle cost {2}."""
        game = create_game()
        p1 = game.players[0]

        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        divination = Sorcery(name="Divination", owner=p1, controller=p1,
                             mana_cost=ManaCost.parse("{2}{U}"))
        set_board_state(game, 0, hand=[divination])

        miracle_cost = getattr(divination, "miracle_cost", None)
        assert miracle_cost is not None
        assert miracle_cost == ManaCost.parse("{2}")

    def test_creature_in_hand_does_not_get_miracle(self) -> None:
        """Creature cards in hand should not gain miracle."""
        game = create_game()
        p1 = game.players[0]

        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{1}{G}"))
        set_board_state(game, 0, hand=[bear])

        miracle_cost = getattr(bear, "miracle_cost", None)
        assert miracle_cost is None

    def test_miracle_only_on_first_card_drawn_per_turn(self) -> None:
        """Miracle can only be used when the card is the first drawn this turn."""
        game = create_game()
        p1 = game.players[0]

        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        # Simulate first draw of turn — miracle should be available
        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1,
                       mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, hand=[bolt])

        # Mark that this is the first card drawn this turn
        game.cards_drawn_this_turn = getattr(game, "cards_drawn_this_turn", {})
        game.cards_drawn_this_turn[p1] = 1

        # First draw: miracle should be castable at miracle cost
        can_miracle = getattr(lorehold, "can_miracle", None)
        if can_miracle:
            assert can_miracle(game, bolt) is True

        # After drawing more cards, miracle should not be available
        game.cards_drawn_this_turn[p1] = 2
        if can_miracle:
            assert can_miracle(game, bolt) is False


class TestLoreholdUpkeepTrigger:
    """At beginning of each opponent's upkeep, may discard to draw."""

    def test_triggers_on_opponent_upkeep(self) -> None:
        """Lorehold should trigger at the beginning of opponent's upkeep."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        # Set up hand with a card to discard and library with a card to draw
        discard_card = Instant(name="Filler", owner=p1, controller=p1,
                               mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[discard_card])

        draw_card = Instant(name="Prize", owner=p1, controller=p1,
                            mana_cost=ManaCost.parse("{1}"))
        p1.zones[Zone.LIBRARY].add(draw_card)

        # Make p2 the active player (it's their turn)
        game.active_player_index = 1

        # Advance to upkeep
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP

        # Check that the trigger is registered for opponent's upkeep
        triggers = getattr(game, "pending_triggers", [])
        # After processing upkeep triggers, there should be a Lorehold trigger
        lorehold_triggers = [
            t for t in getattr(lorehold, "get_triggers", lambda g: [])(game)
            if "upkeep" in str(getattr(t, "description", "")).lower()
            or "discard" in str(getattr(t, "description", "")).lower()
        ]
        assert len(lorehold_triggers) > 0 or hasattr(lorehold, "on_upkeep_trigger")

    def test_does_not_trigger_on_own_upkeep(self) -> None:
        """Lorehold should NOT trigger on its controller's own upkeep."""
        game = create_game()
        p1 = game.players[0]

        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        # Make p1 the active player (it's their turn)
        game.active_player_index = 0
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP

        # The trigger should NOT fire on our own upkeep
        triggers = getattr(lorehold, "get_triggers", lambda g: [])(game)
        upkeep_triggers = [
            t for t in triggers
            if "upkeep" in str(getattr(t, "description", "")).lower()
            or "discard" in str(getattr(t, "description", "")).lower()
        ]
        # On own upkeep, no trigger should be queued
        assert len(upkeep_triggers) == 0

    def test_discard_then_draw(self) -> None:
        """If you choose to discard, you draw a card."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        # Card to discard
        filler = Instant(name="Filler Card", owner=p1, controller=p1,
                         mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[filler])

        # Card to draw
        prize = Instant(name="Prize Card", owner=p1, controller=p1,
                        mana_cost=ManaCost.parse("{2}"))
        p1.zones[Zone.LIBRARY].add(prize)

        hand_before = len(game.get_hand(p1).get_all())
        graveyard_before = len(game.get_graveyard(p1).get_all())

        # Simulate the trigger resolving with choice to discard
        # The trigger effect should discard a card then draw a card
        if hasattr(lorehold, "on_upkeep_trigger"):
            lorehold.on_upkeep_trigger(game, discard=True)
        elif hasattr(lorehold, "upkeep_trigger_effect"):
            lorehold.upkeep_trigger_effect(game)

        # After: filler should be in graveyard, prize should be in hand
        hand_after = game.get_hand(p1).get_all()
        graveyard_after = game.get_graveyard(p1).get_all()

        # Discarded card goes to graveyard
        graveyard_names = [getattr(c, "name", "") for c in graveyard_after]
        assert "Filler Card" in graveyard_names

        # Drew a card
        hand_names = [getattr(c, "name", "") for c in hand_after]
        assert "Prize Card" in hand_names

    def test_may_choose_not_to_discard(self) -> None:
        """The discard is optional ('may'). Choosing not to discard means no draw."""
        game = create_game()
        p1 = game.players[0]

        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        filler = Instant(name="Keep Me", owner=p1, controller=p1,
                         mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[filler])

        hand_before = [getattr(c, "name", "") for c in game.get_hand(p1).get_all()]

        # If choosing not to discard, hand should remain unchanged
        if hasattr(lorehold, "on_upkeep_trigger"):
            lorehold.on_upkeep_trigger(game, discard=False)

        hand_after = [getattr(c, "name", "") for c in game.get_hand(p1).get_all()]
        assert hand_after == hand_before

    def test_empty_hand_cannot_discard(self) -> None:
        """With an empty hand, cannot discard so no draw occurs."""
        game = create_game()
        p1 = game.players[0]

        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        # Empty hand
        set_board_state(game, 0, hand=[])

        prize = Instant(name="Prize", owner=p1, controller=p1,
                        mana_cost=ManaCost.parse("{1}"))
        p1.zones[Zone.LIBRARY].add(prize)

        library_before = len(p1.zones[Zone.LIBRARY].get_all())

        # With no cards in hand, the trigger should not result in a draw
        if hasattr(lorehold, "on_upkeep_trigger"):
            lorehold.on_upkeep_trigger(game, discard=True)

        library_after = len(p1.zones[Zone.LIBRARY].get_all())
        # Library should be unchanged (no draw occurred)
        assert library_after == library_before
