"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import discard, draw_card
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_stack(game: Any) -> None:
    """Pop and resolve everything on the stack."""
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _make_lorehold(owner: Any = None) -> LoreholdTheHistorian:
    return LoreholdTheHistorian(owner=owner, controller=owner)


class _DummyInstant(Instant):
    resolved: bool = False

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dummy Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)
        self.resolved = False

    def on_resolve(self, game: Any) -> None:
        self.resolved = True


class _DummySorcery(Sorcery):
    resolved: bool = False

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dummy Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)
        self.resolved = False

    def on_resolve(self, game: Any) -> None:
        self.resolved = True


class _DummyCreature(Creature):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dummy Creature")
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)


# ---------------------------------------------------------------------------
# 1. Card identity
# ---------------------------------------------------------------------------


class TestLoreholdIdentity:
    def test_name(self) -> None:
        assert _make_lorehold().name == "Lorehold, the Historian"

    def test_power_toughness(self) -> None:
        lore = _make_lorehold()
        assert lore.base_power == 5
        assert lore.base_toughness == 5

    def test_flying_haste(self) -> None:
        lore = _make_lorehold()
        assert Keyword.FLYING in lore.keywords
        assert Keyword.HASTE in lore.keywords

    def test_legendary(self) -> None:
        lore = _make_lorehold()
        assert Supertype.LEGENDARY in lore.supertypes

    def test_creature_type(self) -> None:
        lore = _make_lorehold()
        assert CardType.CREATURE in lore.card_types
        assert "Elder" in lore.subtypes
        assert "Dragon" in lore.subtypes

    def test_mana_cost(self) -> None:
        lore = _make_lorehold()
        assert lore.mana_cost == ManaCost.parse("{3}{R}{W}")


# ---------------------------------------------------------------------------
# 2. Miracle: first draw of instant triggers offer
# ---------------------------------------------------------------------------


class TestMiracleInstant:
    def test_instant_drawn_first_triggers_miracle_offer(self) -> None:
        """Drawing an instant as the first card this turn prompts miracle cast."""
        game = create_game(scripts=([True, False], []))  # p1: yes to miracle, no other choices needed
        p1 = game.players[0]
        lore = _make_lorehold(owner=p1)
        instant = _DummyInstant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[lore])
        lore.register_triggers(game)

        # Reset draw counter
        p1.cards_drawn_this_turn = 0

        # Put instant on top of library
        game.get_library(p1).add(instant)

        draw_card(game, p1)
        # Trigger should be on stack
        assert not game.stack.is_empty(), "Miracle trigger should be on stack"

    def test_instant_drawn_first_miracle_accepted(self) -> None:
        """When player accepts miracle offer for an instant, it resolves."""
        game = create_game(scripts=([True], []))  # p1 answers True to miracle offer
        p1 = game.players[0]
        lore = _make_lorehold(owner=p1)
        instant = _DummyInstant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[lore])
        lore.register_triggers(game)
        p1.cards_drawn_this_turn = 0

        game.get_library(p1).add(instant)
        draw_card(game, p1)
        _resolve_stack(game)

        # instant.resolved should be True (on_resolve was called)
        assert instant.resolved, "Instant should have resolved via miracle"
        # Card should no longer be in hand
        assert not game.get_hand(p1).contains(instant)

    def test_instant_drawn_first_miracle_declined(self) -> None:
        """When player declines miracle offer, card stays in hand."""
        game = create_game(scripts=([False], []))  # p1 answers False
        p1 = game.players[0]
        lore = _make_lorehold(owner=p1)
        instant = _DummyInstant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[lore])
        lore.register_triggers(game)
        p1.cards_drawn_this_turn = 0

        game.get_library(p1).add(instant)
        draw_card(game, p1)
        _resolve_stack(game)

        # Card stays in hand
        assert game.get_hand(p1).contains(instant)
        assert not instant.resolved


# ---------------------------------------------------------------------------
# 3. Miracle: first draw of sorcery triggers offer
# ---------------------------------------------------------------------------


class TestMiracleSorcery:
    def test_sorcery_drawn_first_triggers_miracle_offer(self) -> None:
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        lore = _make_lorehold(owner=p1)
        sorcery = _DummySorcery(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[lore])
        lore.register_triggers(game)
        p1.cards_drawn_this_turn = 0

        game.get_library(p1).add(sorcery)
        draw_card(game, p1)
        assert not game.stack.is_empty(), "Miracle trigger should be on stack for sorcery"

    def test_sorcery_drawn_first_miracle_accepted(self) -> None:
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        lore = _make_lorehold(owner=p1)
        sorcery = _DummySorcery(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[lore])
        lore.register_triggers(game)
        p1.cards_drawn_this_turn = 0

        game.get_library(p1).add(sorcery)
        draw_card(game, p1)
        _resolve_stack(game)

        assert sorcery.resolved
        assert not game.get_hand(p1).contains(sorcery)


# ---------------------------------------------------------------------------
# 4. Miracle: second draw does NOT trigger offer
# ---------------------------------------------------------------------------


class TestMiracleSecondDraw:
    def test_second_draw_instant_no_miracle(self) -> None:
        """Instant drawn as the second card this turn does not get miracle offer."""
        game = create_game()
        p1 = game.players[0]
        lore = _make_lorehold(owner=p1)
        filler = _DummyCreature(owner=p1, controller=p1)
        instant = _DummyInstant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[lore])
        lore.register_triggers(game)
        p1.cards_drawn_this_turn = 0

        # Draw filler (creature) first → cards_drawn_this_turn = 1, no miracle
        game.get_library(p1).add(filler)
        draw_card(game, p1)
        _resolve_stack(game)  # no trigger to resolve

        # Now draw instant → cards_drawn_this_turn = 2 → no miracle
        game.get_library(p1).add(instant)
        draw_card(game, p1)
        # Stack should be empty (no miracle trigger)
        assert game.stack.is_empty(), "No miracle for second draw"


# ---------------------------------------------------------------------------
# 5. Miracle: non-instant/sorcery first draw does NOT trigger
# ---------------------------------------------------------------------------


class TestMiracleNonSpell:
    def test_creature_drawn_first_no_miracle(self) -> None:
        """Drawing a creature as the first card does not trigger miracle."""
        game = create_game()
        p1 = game.players[0]
        lore = _make_lorehold(owner=p1)
        creature = _DummyCreature(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[lore])
        lore.register_triggers(game)
        p1.cards_drawn_this_turn = 0

        game.get_library(p1).add(creature)
        draw_card(game, p1)
        assert game.stack.is_empty(), "No miracle for creature"

    def test_opponent_draws_instant_no_miracle(self) -> None:
        """Opponent drawing an instant does not trigger Lorehold's miracle."""
        game = create_game()
        p1, p2 = game.players
        lore = _make_lorehold(owner=p1)
        instant = _DummyInstant(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[lore])
        lore.register_triggers(game)
        p2.cards_drawn_this_turn = 0

        game.get_library(p2).add(instant)
        draw_card(game, p2)
        assert game.stack.is_empty(), "Opponent's draw should not trigger miracle"


# ---------------------------------------------------------------------------
# 6. Lorehold not on battlefield: no miracle trigger
# ---------------------------------------------------------------------------


class TestNoMiracleWithoutLorehold:
    def test_no_miracle_when_lorehold_not_in_play(self) -> None:
        """Without Lorehold on battlefield, no miracle trigger fires."""
        game = create_game()
        p1 = game.players[0]
        # Lorehold in hand, not battlefield
        lore = _make_lorehold(owner=p1)
        instant = _DummyInstant(owner=p1, controller=p1)

        set_board_state(game, 0, hand=[lore])
        # Triggers NOT registered (Lorehold never entered battlefield)

        p1.cards_drawn_this_turn = 0
        game.get_library(p1).add(instant)
        draw_card(game, p1)
        assert game.stack.is_empty(), "No miracle without Lorehold on battlefield"


# ---------------------------------------------------------------------------
# 7. Opponent upkeep trigger: fires on opponent's upkeep
# ---------------------------------------------------------------------------


class TestUpkeepTrigger:
    def _setup(
        self, p1_script: list, p2_script: list | None = None
    ) -> tuple:
        game = create_game(scripts=(p1_script, p2_script or []))
        p1, p2 = game.players
        lore = _make_lorehold(owner=p1)
        set_board_state(game, 0, battlefield=[lore])
        lore.register_triggers(game)
        return game, p1, p2, lore

    def test_trigger_fires_on_opponent_upkeep(self) -> None:
        """Upkeep trigger goes on stack when opponent's upkeep fires."""
        game, p1, p2, lore = self._setup([False])  # p1 declines discard
        # Simulate opponent's (p2's) upkeep
        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert not game.stack.is_empty(), "Trigger should be on stack"

    def test_trigger_does_not_fire_on_own_upkeep(self) -> None:
        """Upkeep trigger does NOT fire when p1 (Lorehold's controller) has upkeep."""
        game, p1, p2, lore = self._setup([])
        # Simulate p1's own upkeep
        game.active_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert game.stack.is_empty(), "No trigger on own upkeep"

    def test_discard_draw_on_opponent_upkeep(self) -> None:
        """Accepting discard causes p1 to lose one card and gain one card."""
        # Script: True (yes discard), card choice is answered via choose_card
        dummy_card = _DummyInstant(name="Hand Card")
        # Script: True -> yes to discard; dummy_card -> card to discard
        game = create_game(scripts=([True, dummy_card], []))
        p1, p2 = game.players
        lore = _make_lorehold(owner=p1)
        dummy_draw = _DummyCreature(name="Top of Library")

        # p1 has 1 card in hand, 1 card in library
        set_board_state(
            game, 0,
            battlefield=[lore],
            hand=[dummy_card],
        )
        dummy_card.owner = p1
        dummy_card.controller = p1
        game.get_library(p1).add(dummy_draw)
        lore.register_triggers(game)

        hand_before = len(game.get_hand(p1).get_all())
        library_before = len(game.get_library(p1).get_all())

        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)

        hand_after = len(game.get_hand(p1).get_all())
        # Discarded 1, drew 1 → net 0 change
        assert hand_after == hand_before, (
            f"Expected hand size {hand_before}, got {hand_after}"
        )
        # Discarded card is in graveyard
        assert game.get_graveyard(p1).contains(dummy_card)
        # Drawn card is in hand
        assert game.get_hand(p1).contains(dummy_draw)

    def test_decline_discard_no_draw(self) -> None:
        """Declining discard means no draw."""
        game = create_game(scripts=([False], []))  # p1 says no
        p1, p2 = game.players
        lore = _make_lorehold(owner=p1)
        dummy_draw = _DummyCreature(name="Library Top")

        set_board_state(game, 0, battlefield=[lore], hand=[])
        game.get_library(p1).add(dummy_draw)
        lore.register_triggers(game)

        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)

        # No draw occurred
        assert not game.get_hand(p1).contains(dummy_draw)
        assert game.stack.is_empty()

    def test_no_upkeep_trigger_without_lorehold(self) -> None:
        """Without Lorehold on battlefield, upkeep trigger does not fire."""
        game = create_game()
        p1, p2 = game.players
        lore = _make_lorehold(owner=p1)
        # Lorehold in hand, triggers NOT registered
        set_board_state(game, 0, hand=[lore])

        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert game.stack.is_empty()

    def test_upkeep_trigger_after_lorehold_leaves_battlefield(self) -> None:
        """Effect is a no-op when Lorehold has left the battlefield."""
        game = create_game(scripts=([False], []))
        p1, p2 = game.players
        lore = _make_lorehold(owner=p1)

        set_board_state(game, 0, battlefield=[lore])
        lore.register_triggers(game)

        # Remove Lorehold from battlefield (simulate death)
        game.get_battlefield(p1).remove(lore)
        game.trigger_manager.unregister(lore)

        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert game.stack.is_empty()


# ---------------------------------------------------------------------------
# 8. cards_drawn_this_turn resets on untap
# ---------------------------------------------------------------------------


class TestDrawCounterReset:
    def test_draw_counter_resets_on_untap(self) -> None:
        """cards_drawn_this_turn resets when the untap step executes."""
        from engine.turn import _do_untap_step

        game = create_game()
        p1 = game.players[0]
        p1.cards_drawn_this_turn = 5  # simulate previous draws
        _do_untap_step(game)
        assert p1.cards_drawn_this_turn == 0
