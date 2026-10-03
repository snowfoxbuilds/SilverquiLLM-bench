"""Tests for engine/casting.py — casting and resolution pipeline.

Covers:
- Timing helpers: is_sorcery_speed, can_cast_at_instant_speed
- cast_spell: full pipeline from hand → stack → resolve → destination zone
- play_land: special action bypassing the stack
- CastingError for illegal actions
- Hook callbacks (on_cast, on_resolve)
- Mana payment verification
"""

from __future__ import annotations

import pytest

from engine.card import (
    Artifact,
    ArtifactCreature,
    CardImpl,
    Creature,
    Enchantment,
    Instant,
    Land,
    Planeswalker,
    Sorcery,
)
from engine.casting import (
    CastingError,
    _PERMANENT_TYPES,
    can_cast_at_instant_speed,
    cast_spell,
    cast_spell_free,
    is_sorcery_speed,
    play_land,
)
from engine.decisions import Decision, GameRef
from engine.events import SpellCastTriggeredEvent
from engine.game_state import GameState
from engine.intent_player import DeterministicPlayer, Intent
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Step, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(
    *,
    phase: Phase = Phase.PRECOMBAT_MAIN,
    step: Step | None = None,
) -> GameState:
    """Create a minimal 2-player GameState at the specified phase/step."""
    p1 = DeterministicPlayer("Alice")
    p2 = DeterministicPlayer("Bob")
    game = GameState([p1, p2])
    game.phase = phase
    game.step = step
    return game


def _add_to_hand(game: GameState, player_idx: int, card: CardImpl) -> None:
    """Put *card* into the player's hand."""
    game.get_hand(game.players[player_idx]).add(card)


def _add_mana(player: DeterministicPlayer, mana_type: ManaType, amount: int) -> None:
    """Shortcut to add mana to a player's pool."""
    player.mana_pool.add(mana_type, amount)


# ---------------------------------------------------------------------------
# Timing helper tests — is_sorcery_speed
# ---------------------------------------------------------------------------

class TestIsSorcerySpeed:
    """Verify is_sorcery_speed requires: active player + main phase + empty stack."""

    def test_precombat_main_active_player_empty_stack_is_true(self):
        game = _make_game(phase=Phase.PRECOMBAT_MAIN)
        assert is_sorcery_speed(game, game.players[0]) is True

    def test_postcombat_main_active_player_empty_stack_is_true(self):
        game = _make_game(phase=Phase.POSTCOMBAT_MAIN)
        assert is_sorcery_speed(game, game.players[0]) is True

    def test_non_active_player_returns_false(self):
        game = _make_game(phase=Phase.PRECOMBAT_MAIN)
        assert is_sorcery_speed(game, game.players[1]) is False

    def test_combat_phase_returns_false(self):
        game = _make_game(phase=Phase.COMBAT, step=Step.DECLARE_ATTACKERS)
        assert is_sorcery_speed(game, game.players[0]) is False

    def test_beginning_phase_returns_false(self):
        game = _make_game(phase=Phase.BEGINNING, step=Step.UPKEEP)
        assert is_sorcery_speed(game, game.players[0]) is False

    def test_ending_phase_returns_false(self):
        game = _make_game(phase=Phase.ENDING, step=Step.END)
        assert is_sorcery_speed(game, game.players[0]) is False

    def test_nonempty_stack_returns_false(self):
        game = _make_game(phase=Phase.PRECOMBAT_MAIN)
        dummy = StackObject(source=None, controller=game.players[0])
        game.stack.push(dummy)
        assert is_sorcery_speed(game, game.players[0]) is False


# ---------------------------------------------------------------------------
# Timing helper tests — can_cast_at_instant_speed
# ---------------------------------------------------------------------------

class TestCanCastAtInstantSpeed:
    """Verify instant-speed detection: instant type or FLASH keyword."""

    def test_instant_returns_true(self):
        assert can_cast_at_instant_speed(Instant(name="Bolt")) is True

    def test_sorcery_returns_false(self):
        assert can_cast_at_instant_speed(Sorcery(name="Div")) is False

    def test_creature_without_flash_returns_false(self):
        assert can_cast_at_instant_speed(
            Creature(name="Bear", base_power=2, base_toughness=2)
        ) is False

    def test_creature_with_flash_returns_true(self):
        card = Creature(name="Viper", base_power=2, base_toughness=1, keywords=Keyword.FLASH)
        assert can_cast_at_instant_speed(card) is True

    def test_enchantment_with_flash_returns_true(self):
        card = Enchantment(name="Leyline", keywords=Keyword.FLASH)
        assert can_cast_at_instant_speed(card) is True


# ---------------------------------------------------------------------------
# cast_spell — core pipeline tests
# ---------------------------------------------------------------------------

class TestCastSpellCreature:
    """Requirement: cast vanilla creature → on stack → resolve → battlefield."""

    def test_cast_puts_creature_on_stack(self):
        game = _make_game()
        player = game.players[0]
        bear = Creature(
            name="Grizzly Bears",
            mana_cost=ManaCost(generic=1, pips={ManaType.GREEN: 1}),
            base_power=2, base_toughness=2,
        )
        _add_to_hand(game, 0, bear)
        _add_mana(player, ManaType.GREEN, 2)

        cast_spell(game, player, bear)

        assert not game.stack.is_empty()
        top = game.stack.peek()
        assert top is not None
        assert top.source is bear
        assert top.controller is player

    def test_cast_removes_creature_from_hand(self):
        game = _make_game()
        player = game.players[0]
        bear = Creature(
            name="Bear", mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
            base_power=2, base_toughness=2,
        )
        _add_to_hand(game, 0, bear)
        _add_mana(player, ManaType.GREEN, 1)

        cast_spell(game, player, bear)
        assert not game.get_hand(player).contains(bear)

    def test_resolve_creature_to_battlefield(self):
        game = _make_game()
        player = game.players[0]
        bear = Creature(
            name="Bear",
            mana_cost=ManaCost(generic=1, pips={ManaType.GREEN: 1}),
            base_power=2, base_toughness=2,
        )
        _add_to_hand(game, 0, bear)
        _add_mana(player, ManaType.GREEN, 2)

        cast_spell(game, player, bear)
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert game.get_battlefield(player).contains(bear)
        assert not game.get_graveyard(player).contains(bear)


class TestCastSpellInstant:
    """Requirement: cast instant → resolve → graveyard (not battlefield)."""

    def test_resolve_instant_to_graveyard(self):
        game = _make_game()
        player = game.players[0]
        bolt = Instant(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, bolt)
        _add_mana(player, ManaType.RED, 1)

        cast_spell(game, player, bolt)
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert game.get_graveyard(player).contains(bolt)
        assert not game.get_battlefield(player).contains(bolt)


class TestCastSpellSorcery:
    """Requirement: cast sorcery → resolve → graveyard."""

    def test_resolve_sorcery_to_graveyard(self):
        game = _make_game()
        player = game.players[0]
        div = Sorcery(
            name="Divination",
            mana_cost=ManaCost(generic=2, pips={ManaType.BLUE: 1}),
        )
        _add_to_hand(game, 0, div)
        _add_mana(player, ManaType.BLUE, 3)

        cast_spell(game, player, div)
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert game.get_graveyard(player).contains(div)
        assert not game.get_battlefield(player).contains(div)


# ---------------------------------------------------------------------------
# cast_spell — timing rejection tests
# ---------------------------------------------------------------------------

class TestCastSpellTimingRejections:
    """Requirement: sorcery-speed violations raise CastingError."""

    def test_sorcery_during_combat_phase_raises(self):
        """Sorcery during combat → CastingError."""
        game = _make_game(phase=Phase.COMBAT, step=Step.DECLARE_ATTACKERS)
        player = game.players[0]
        sorc = Sorcery(name="Wrath", mana_cost=ManaCost(pips={ManaType.WHITE: 1}))
        _add_to_hand(game, 0, sorc)
        _add_mana(player, ManaType.WHITE, 1)

        with pytest.raises(CastingError, match="sorcery-speed timing"):
            cast_spell(game, player, sorc)

    def test_creature_during_combat_phase_raises(self):
        """Non-flash creature during combat → CastingError."""
        game = _make_game(phase=Phase.COMBAT, step=Step.DECLARE_BLOCKERS)
        player = game.players[0]
        bear = Creature(
            name="Bear", mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
            base_power=2, base_toughness=2,
        )
        _add_to_hand(game, 0, bear)
        _add_mana(player, ManaType.GREEN, 1)

        with pytest.raises(CastingError, match="sorcery-speed timing"):
            cast_spell(game, player, bear)

    def test_sorcery_with_nonempty_stack_raises(self):
        """Sorcery with non-empty stack → CastingError."""
        game = _make_game()
        player = game.players[0]
        dummy = StackObject(source=None, controller=player)
        game.stack.push(dummy)

        sorc = Sorcery(name="Div", mana_cost=ManaCost(pips={ManaType.BLUE: 1}))
        _add_to_hand(game, 0, sorc)
        _add_mana(player, ManaType.BLUE, 1)

        with pytest.raises(CastingError, match="sorcery-speed timing"):
            cast_spell(game, player, sorc)

    def test_non_active_player_sorcery_raises(self):
        """Non-active player casting sorcery → CastingError."""
        game = _make_game()
        non_active = game.players[1]
        sorc = Sorcery(name="Div", mana_cost=ManaCost(pips={ManaType.BLUE: 1}))
        _add_to_hand(game, 1, sorc)
        _add_mana(non_active, ManaType.BLUE, 1)

        with pytest.raises(CastingError, match="sorcery-speed timing"):
            cast_spell(game, non_active, sorc)

    def test_non_active_player_creature_no_flash_raises(self):
        """Non-active player casting creature without flash → CastingError."""
        game = _make_game()
        non_active = game.players[1]
        bear = Creature(
            name="Bear", mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
            base_power=2, base_toughness=2,
        )
        _add_to_hand(game, 1, bear)
        _add_mana(non_active, ManaType.GREEN, 1)

        with pytest.raises(CastingError, match="sorcery-speed timing"):
            cast_spell(game, non_active, bear)


# ---------------------------------------------------------------------------
# cast_spell — flash / instant-speed success
# ---------------------------------------------------------------------------

class TestCastSpellInstantSpeed:
    """Requirement: FLASH keyword at instant speed → succeeds."""

    def test_flash_creature_during_combat_succeeds(self):
        game = _make_game(phase=Phase.COMBAT, step=Step.DECLARE_BLOCKERS)
        player = game.players[0]
        viper = Creature(
            name="Ambush Viper",
            mana_cost=ManaCost(generic=1, pips={ManaType.GREEN: 1}),
            base_power=2, base_toughness=1,
            keywords=Keyword.FLASH,
        )
        _add_to_hand(game, 0, viper)
        _add_mana(player, ManaType.GREEN, 2)

        cast_spell(game, player, viper)
        assert not game.stack.is_empty()
        assert game.stack.peek().source is viper

    def test_instant_during_upkeep_succeeds(self):
        game = _make_game(phase=Phase.BEGINNING, step=Step.UPKEEP)
        player = game.players[0]
        bolt = Instant(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, bolt)
        _add_mana(player, ManaType.RED, 1)

        cast_spell(game, player, bolt)
        assert not game.stack.is_empty()

    def test_non_active_player_can_cast_instant(self):
        game = _make_game()
        non_active = game.players[1]
        bolt = Instant(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 1, bolt)
        _add_mana(non_active, ManaType.RED, 1)

        cast_spell(game, non_active, bolt)
        assert not game.stack.is_empty()

    def test_flash_enchantment_during_combat_succeeds(self):
        game = _make_game(phase=Phase.COMBAT, step=Step.END_COMBAT)
        player = game.players[0]
        ench = Enchantment(
            name="Leyline",
            mana_cost=ManaCost(pips={ManaType.WHITE: 1}),
            keywords=Keyword.FLASH,
        )
        _add_to_hand(game, 0, ench)
        _add_mana(player, ManaType.WHITE, 1)

        cast_spell(game, player, ench)
        assert not game.stack.is_empty()


# ---------------------------------------------------------------------------
# cast_spell — mana payment
# ---------------------------------------------------------------------------

class TestCastSpellManaPayment:
    """Requirement: insufficient mana → CastingError; mana deducted on success."""

    def test_insufficient_mana_raises(self):
        game = _make_game()
        player = game.players[0]
        bear = Creature(
            name="Bear",
            mana_cost=ManaCost(generic=1, pips={ManaType.GREEN: 1}),
            base_power=2, base_toughness=2,
        )
        _add_to_hand(game, 0, bear)
        _add_mana(player, ManaType.GREEN, 1)  # only 1G, need 1G + {1}

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell(game, player, bear)

    def test_no_mana_at_all_raises(self):
        game = _make_game()
        player = game.players[0]
        bolt = Instant(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, bolt)
        # No mana added

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell(game, player, bolt)

    def test_wrong_color_mana_raises(self):
        game = _make_game()
        player = game.players[0]
        bolt = Instant(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, bolt)
        _add_mana(player, ManaType.BLUE, 5)  # plenty of mana, but wrong color

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell(game, player, bolt)

    def test_mana_deducted_after_cast(self):
        """Verify mana pool is reduced by the cost after a successful cast."""
        game = _make_game()
        player = game.players[0]
        bear = Creature(
            name="Bear",
            mana_cost=ManaCost(generic=1, pips={ManaType.GREEN: 1}),
            base_power=2, base_toughness=2,
        )
        _add_to_hand(game, 0, bear)
        _add_mana(player, ManaType.GREEN, 3)

        cast_spell(game, player, bear)

        # 3G minus {G} pip minus {1} generic (auto-paid with G) = 1G left
        assert player.mana_pool.get(ManaType.GREEN) == 1

    def test_exact_mana_leaves_zero(self):
        """Paying exactly the cost leaves the pool empty."""
        game = _make_game()
        player = game.players[0]
        bolt = Instant(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, bolt)
        _add_mana(player, ManaType.RED, 1)

        cast_spell(game, player, bolt)
        assert player.mana_pool.get(ManaType.RED) == 0

    def test_zero_cost_spell_requires_no_mana(self):
        """A zero-cost spell can be cast with an empty pool."""
        game = _make_game()
        player = game.players[0]
        card = Instant(name="Pact", mana_cost=ManaCost())
        _add_to_hand(game, 0, card)
        # No mana added — pool is empty

        cast_spell(game, player, card)
        assert not game.stack.is_empty()

    def test_mana_not_deducted_on_failure(self):
        """When casting fails (e.g. timing), mana should not be deducted."""
        game = _make_game(phase=Phase.COMBAT, step=Step.DECLARE_ATTACKERS)
        player = game.players[0]
        sorc = Sorcery(name="Div", mana_cost=ManaCost(pips={ManaType.BLUE: 1}))
        _add_to_hand(game, 0, sorc)
        _add_mana(player, ManaType.BLUE, 1)

        with pytest.raises(CastingError):
            cast_spell(game, player, sorc)

        # Mana should still be there since timing check fails before payment
        assert player.mana_pool.get(ManaType.BLUE) == 1


# ---------------------------------------------------------------------------
# cast_spell — hook callbacks
# ---------------------------------------------------------------------------

class TestCastSpellHooks:
    """Requirements: on_cast called during cast; on_resolve called during resolution."""

    def test_on_cast_callback_is_called(self):
        on_cast_log: list[str] = []

        class TrackedCreature(Creature):
            def on_cast(self, game: GameState) -> None:
                on_cast_log.append("on_cast")

        game = _make_game()
        player = game.players[0]
        card = TrackedCreature(
            name="Tracked",
            mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
            base_power=1, base_toughness=1,
        )
        _add_to_hand(game, 0, card)
        _add_mana(player, ManaType.GREEN, 1)

        cast_spell(game, player, card)
        assert on_cast_log == ["on_cast"]

    def test_on_resolve_callback_is_called(self):
        on_resolve_log: list[str] = []

        class TrackedInstant(Instant):
            def on_resolve(self, game: GameState) -> None:
                on_resolve_log.append("on_resolve")

        game = _make_game()
        player = game.players[0]
        card = TrackedInstant(
            name="Tracked", mana_cost=ManaCost(pips={ManaType.RED: 1}),
        )
        _add_to_hand(game, 0, card)
        _add_mana(player, ManaType.RED, 1)

        cast_spell(game, player, card)
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert on_resolve_log == ["on_resolve"]

    def test_on_cast_called_before_push_to_stack(self):
        """on_cast fires during cast_spell, before the StackObject is pushed."""
        stack_was_empty_during_on_cast: list[bool] = []

        class InspectorCreature(Creature):
            def on_cast(self, game: GameState) -> None:
                # At on_cast time the stack should still be empty
                # (StackObject push happens after on_cast)
                stack_was_empty_during_on_cast.append(game.stack.is_empty())

        game = _make_game()
        player = game.players[0]
        card = InspectorCreature(
            name="Inspector",
            mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
            base_power=1, base_toughness=1,
        )
        _add_to_hand(game, 0, card)
        _add_mana(player, ManaType.GREEN, 1)

        cast_spell(game, player, card)
        assert stack_was_empty_during_on_cast == [True]

    def test_on_resolve_receives_game_state(self):
        """on_resolve receives the game state so the card can interact with it."""
        received_game: list[GameState | None] = []

        class InspectorSorcery(Sorcery):
            def on_resolve(self, game: GameState) -> None:
                received_game.append(game)

        game = _make_game()
        player = game.players[0]
        card = InspectorSorcery(
            name="Inspector", mana_cost=ManaCost(pips={ManaType.BLUE: 1}),
        )
        _add_to_hand(game, 0, card)
        _add_mana(player, ManaType.BLUE, 1)

        cast_spell(game, player, card)
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert received_game == [game]


# ---------------------------------------------------------------------------
# cast_spell — additional legality checks
# ---------------------------------------------------------------------------

class TestCastSpellLegality:
    """Miscellaneous legality checks for cast_spell."""

    def test_card_not_in_hand_raises(self):
        game = _make_game()
        player = game.players[0]
        bear = Creature(
            name="Bear", mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
            base_power=2, base_toughness=2,
        )
        _add_mana(player, ManaType.GREEN, 1)
        # Card NOT added to hand

        with pytest.raises(CastingError, match="card not in hand"):
            cast_spell(game, player, bear)

    def test_can_cast_returns_false_raises(self):
        """Land.can_cast always returns False; trying to cast_spell should error."""
        game = _make_game()
        player = game.players[0]
        land = Land(name="Forest")
        _add_to_hand(game, 0, land)

        with pytest.raises(CastingError, match="can_cast returned False"):
            cast_spell(game, player, land)

    def test_hand_unchanged_on_timing_failure(self):
        """If timing check fails, card should remain in hand."""
        game = _make_game(phase=Phase.COMBAT, step=Step.DECLARE_ATTACKERS)
        player = game.players[0]
        bear = Creature(
            name="Bear", mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
            base_power=2, base_toughness=2,
        )
        _add_to_hand(game, 0, bear)
        _add_mana(player, ManaType.GREEN, 1)

        with pytest.raises(CastingError):
            cast_spell(game, player, bear)

        # Card should still be in hand
        assert game.get_hand(player).contains(bear)

    def test_stack_unchanged_on_failure(self):
        """If cast fails, nothing is added to the stack."""
        game = _make_game()
        player = game.players[0]
        bear = Creature(
            name="Bear",
            mana_cost=ManaCost(generic=5, pips={ManaType.GREEN: 1}),
            base_power=2, base_toughness=2,
        )
        _add_to_hand(game, 0, bear)
        # Insufficient mana
        _add_mana(player, ManaType.GREEN, 1)

        with pytest.raises(CastingError):
            cast_spell(game, player, bear)

        assert game.stack.is_empty()


# ---------------------------------------------------------------------------
# play_land tests
# ---------------------------------------------------------------------------

class TestPlayLand:
    """Requirement: play_land moves land hand→battlefield, decrements counter."""

    def test_valid_land_play_moves_to_battlefield(self):
        game = _make_game()
        player = game.players[0]
        forest = Land(name="Forest")
        _add_to_hand(game, 0, forest)

        play_land(game, player, forest)
        assert game.get_battlefield(player).contains(forest)

    def test_valid_land_play_removes_from_hand(self):
        game = _make_game()
        player = game.players[0]
        forest = Land(name="Forest")
        _add_to_hand(game, 0, forest)

        play_land(game, player, forest)
        assert not game.get_hand(player).contains(forest)

    def test_valid_land_play_decrements_remaining(self):
        game = _make_game()
        player = game.players[0]
        forest = Land(name="Forest")
        _add_to_hand(game, 0, forest)
        assert player.land_plays_remaining == 1

        play_land(game, player, forest)
        assert player.land_plays_remaining == 0

    def test_land_play_postcombat_main_succeeds(self):
        game = _make_game(phase=Phase.POSTCOMBAT_MAIN)
        player = game.players[0]
        island = Land(name="Island")
        _add_to_hand(game, 0, island)

        play_land(game, player, island)
        assert game.get_battlefield(player).contains(island)

    def test_second_land_play_when_remaining_zero_raises(self):
        """After playing one land (remaining=0), second play raises CastingError."""
        game = _make_game()
        player = game.players[0]
        f1 = Land(name="Forest")
        f2 = Land(name="Forest")
        _add_to_hand(game, 0, f1)
        _add_to_hand(game, 0, f2)

        play_land(game, player, f1)
        assert player.land_plays_remaining == 0

        with pytest.raises(CastingError, match="no land plays remaining"):
            play_land(game, player, f2)

    def test_remaining_already_zero_raises(self):
        """If remaining=0 from the start, playing a land raises CastingError."""
        game = _make_game()
        player = game.players[0]
        player.land_plays_remaining = 0
        forest = Land(name="Forest")
        _add_to_hand(game, 0, forest)

        with pytest.raises(CastingError, match="no land plays remaining"):
            play_land(game, player, forest)

    def test_land_during_combat_phase_raises(self):
        """Cannot play a land during combat — must be main phase."""
        game = _make_game(phase=Phase.COMBAT, step=Step.DECLARE_ATTACKERS)
        player = game.players[0]
        forest = Land(name="Forest")
        _add_to_hand(game, 0, forest)

        with pytest.raises(CastingError):
            play_land(game, player, forest)

    def test_land_during_beginning_phase_raises(self):
        """Cannot play a land during upkeep — must be main phase."""
        game = _make_game(phase=Phase.BEGINNING, step=Step.UPKEEP)
        player = game.players[0]
        forest = Land(name="Forest")
        _add_to_hand(game, 0, forest)

        with pytest.raises(CastingError):
            play_land(game, player, forest)

    def test_land_by_non_active_player_raises(self):
        """Non-active player cannot play a land."""
        game = _make_game()
        non_active = game.players[1]
        forest = Land(name="Forest")
        _add_to_hand(game, 1, forest)

        with pytest.raises(CastingError):
            play_land(game, non_active, forest)

    def test_land_with_nonempty_stack_raises(self):
        """Cannot play a land when the stack is non-empty."""
        game = _make_game()
        player = game.players[0]
        dummy = StackObject(source=None, controller=player)
        game.stack.push(dummy)

        forest = Land(name="Forest")
        _add_to_hand(game, 0, forest)

        with pytest.raises(CastingError):
            play_land(game, player, forest)

    def test_non_land_card_raises(self):
        """play_land rejects a card that isn't a land."""
        game = _make_game()
        player = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        _add_to_hand(game, 0, creature)

        with pytest.raises(CastingError, match="not a land card"):
            play_land(game, player, creature)

    def test_land_not_in_hand_raises(self):
        """Cannot play a land that's not in hand."""
        game = _make_game()
        player = game.players[0]
        forest = Land(name="Forest")
        # NOT added to hand

        with pytest.raises(CastingError, match="card not in hand"):
            play_land(game, player, forest)

    def test_extra_land_with_increased_limit(self):
        """If land_plays_remaining is 2 (e.g. Exploration), two lands are allowed."""
        game = _make_game()
        player = game.players[0]
        player.land_plays_remaining = 2
        f1 = Land(name="Forest")
        f2 = Land(name="Forest")
        _add_to_hand(game, 0, f1)
        _add_to_hand(game, 0, f2)

        play_land(game, player, f1)
        assert player.land_plays_remaining == 1

        play_land(game, player, f2)
        assert player.land_plays_remaining == 0
        assert game.get_battlefield(player).contains(f1)
        assert game.get_battlefield(player).contains(f2)

    def test_land_does_not_use_stack(self):
        """Playing a land is a special action — it should not go through the stack."""
        game = _make_game()
        player = game.players[0]
        forest = Land(name="Forest")
        _add_to_hand(game, 0, forest)

        play_land(game, player, forest)
        assert game.stack.is_empty()


# ---------------------------------------------------------------------------
# Permanent type detection
# ---------------------------------------------------------------------------

class TestPermanentTypes:
    """Verify _PERMANENT_TYPES covers exactly creature, enchantment, artifact, planeswalker."""

    def test_creature_is_permanent(self):
        assert CardType.CREATURE in _PERMANENT_TYPES

    def test_enchantment_is_permanent(self):
        assert CardType.ENCHANTMENT in _PERMANENT_TYPES

    def test_artifact_is_permanent(self):
        assert CardType.ARTIFACT in _PERMANENT_TYPES

    def test_planeswalker_is_permanent(self):
        assert CardType.PLANESWALKER in _PERMANENT_TYPES

    def test_instant_is_not_permanent(self):
        assert CardType.INSTANT not in _PERMANENT_TYPES

    def test_sorcery_is_not_permanent(self):
        assert CardType.SORCERY not in _PERMANENT_TYPES

    def test_land_is_not_in_permanent_types(self):
        assert CardType.LAND not in _PERMANENT_TYPES


# ---------------------------------------------------------------------------
# Resolution: additional permanent subtypes
# ---------------------------------------------------------------------------

class TestResolveOtherPermanents:
    """Enchantments, artifacts, planeswalkers, artifact creatures → battlefield."""

    def test_enchantment_resolves_to_battlefield(self):
        game = _make_game()
        player = game.players[0]
        ench = Enchantment(name="Pac", mana_cost=ManaCost(pips={ManaType.WHITE: 1}))
        _add_to_hand(game, 0, ench)
        _add_mana(player, ManaType.WHITE, 1)

        cast_spell(game, player, ench)
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert game.get_battlefield(player).contains(ench)

    def test_artifact_resolves_to_battlefield(self):
        game = _make_game()
        player = game.players[0]
        art = Artifact(name="Sol Ring", mana_cost=ManaCost(generic=1))
        _add_to_hand(game, 0, art)
        _add_mana(player, ManaType.COLORLESS, 1)

        cast_spell(game, player, art)
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert game.get_battlefield(player).contains(art)

    def test_planeswalker_resolves_to_battlefield(self):
        game = _make_game()
        player = game.players[0]
        pw = Planeswalker(
            name="Jace",
            mana_cost=ManaCost(generic=2, pips={ManaType.BLUE: 2}),
            starting_loyalty=3,
        )
        _add_to_hand(game, 0, pw)
        _add_mana(player, ManaType.BLUE, 4)

        cast_spell(game, player, pw)
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert game.get_battlefield(player).contains(pw)

    def test_artifact_creature_resolves_to_battlefield(self):
        game = _make_game()
        player = game.players[0]
        ac = ArtifactCreature(
            name="Ornithopter", mana_cost=ManaCost(), base_power=0, base_toughness=2,
        )
        _add_to_hand(game, 0, ac)

        cast_spell(game, player, ac)
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert game.get_battlefield(player).contains(ac)


# ---------------------------------------------------------------------------
# Integration: multi-spell stack LIFO ordering
# ---------------------------------------------------------------------------

class TestCastResolveIntegration:
    """End-to-end integration tests for stack interaction."""

    def test_multiple_spells_resolve_lifo(self):
        """Two instants on the stack resolve in LIFO order."""
        game = _make_game()
        player = game.players[0]

        bolt1 = Instant(name="Bolt 1", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        bolt2 = Instant(name="Bolt 2", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, bolt1)
        _add_to_hand(game, 0, bolt2)
        _add_mana(player, ManaType.RED, 2)

        cast_spell(game, player, bolt1)
        cast_spell(game, player, bolt2)

        top = game.stack.pop()
        assert top.source is bolt2
        top.on_resolve(game)

        next_obj = game.stack.pop()
        assert next_obj.source is bolt1
        next_obj.on_resolve(game)

        assert game.get_graveyard(player).contains(bolt1)
        assert game.get_graveyard(player).contains(bolt2)

    def test_cast_creature_full_lifecycle(self):
        """Full lifecycle: hand → cast → stack → resolve → battlefield."""
        game = _make_game()
        player = game.players[0]
        bear = Creature(
            name="Bear",
            mana_cost=ManaCost(generic=1, pips={ManaType.GREEN: 1}),
            base_power=2, base_toughness=2,
        )
        _add_to_hand(game, 0, bear)
        _add_mana(player, ManaType.GREEN, 2)

        # 1. In hand
        assert game.get_hand(player).contains(bear)
        # 2. Cast
        cast_spell(game, player, bear)
        assert not game.get_hand(player).contains(bear)
        assert len(game.stack.objects()) == 1
        # 3. Resolve
        obj = game.stack.pop()
        obj.on_resolve(game)
        assert game.stack.is_empty()
        assert game.get_battlefield(player).contains(bear)

    def test_cast_with_targets_passes_to_stack_object(self):
        """Targets chosen during casting are stored in the StackObject.

        The engine raises a target Player Query when casting a targeted spell;
        an Intent on the caster prefers a specific battlefield creature, and
        the chosen target is stored on the StackObject (not the card).
        """
        from engine.types import TargetRequirement, Zone

        class TargetedBolt(Instant):
            def get_targets(self, game: GameState):
                return [
                    TargetRequirement(
                        filter_fn=lambda obj: CardType.CREATURE
                        in getattr(obj, "card_types", set()),
                        description="target creature",
                        zone=Zone.BATTLEFIELD,
                    )
                ]

        game = _make_game()
        player = game.players[0]
        # A real, targetable creature the spell can be aimed at.
        target_creature = Creature(
            name="Target Creature",
            mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
            base_power=2,
            base_toughness=2,
        )
        bf = game.players[1].zones[Zone.BATTLEFIELD]
        target_creature.owner = game.players[1]
        target_creature.controller = game.players[1]
        bf.add(target_creature)
        target_creature.instance_id = game.refs.instance_id(
            target_creature, Zone.BATTLEFIELD.value
        )

        card = TargetedBolt(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, card)
        _add_mana(player, ManaType.RED, 1)

        player.start_intent(
            "bolt",
            Intent(
                pattern=GameRef(card=frozenset({("name", "Bolt")})),
                preferences=(Decision.obj(instance=target_creature.instance_id),),
            ),
        )
        cast_spell(game, player, card)
        player.end_intent("bolt")

        top = game.stack.peek()
        assert top.targets == [target_creature]


# ---------------------------------------------------------------------------
# Optional targets — "up to one target X" (TargetRequirement.optional)
# ---------------------------------------------------------------------------

class TestOptionalTargets:
    """`TargetRequirement.optional` makes a target query declinable (min == 0)
    and lets an empty candidate set skip the requirement instead of raising —
    so "up to N target X" is castable with fewer than N (or zero) candidates."""

    @staticmethod
    def _creature_spec(*, optional: bool):
        from engine.types import TargetRequirement, Zone

        return TargetRequirement(
            filter_fn=lambda obj: CardType.CREATURE
            in getattr(obj, "card_types", set()),
            description="up to one target creature" if optional else "target creature",
            zone=Zone.BATTLEFIELD,
            optional=optional,
        )

    def _spell_class(self, specs):
        class _Spell(Instant):
            def get_targets(self, game):
                return specs

        return _Spell

    def _place_creature(self, game, player_idx, name):
        from engine.types import Zone

        p = game.players[player_idx]
        c = Creature(name=name, mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
                     base_power=2, base_toughness=2)
        c.owner = p
        c.controller = p
        p.zones[Zone.BATTLEFIELD].add(c)
        c.instance_id = game.refs.instance_id(c, Zone.BATTLEFIELD.value)
        return c

    def test_optional_empty_candidate_set_casts_without_target(self):
        """No legal candidate + optional: the spell casts, raises no query, and
        goes on the stack with no target (rather than raising CastingError)."""
        Spell = self._spell_class([self._creature_spec(optional=True)])
        game = _make_game()
        player = game.players[0]
        card = Spell(name="Optional Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, card)
        _add_mana(player, ManaType.RED, 1)
        # No creatures anywhere; no intent needed — the empty option set skips.
        cast_spell(game, player, card)
        top = game.stack.peek()
        assert top is not None and top.source is card
        assert top.targets == []

    def test_required_empty_candidate_set_still_raises(self):
        """The required-target boundary is unchanged: an empty candidate set for
        a non-optional spec still raises CastingError, and no StackObject is
        pushed (a candidate present would instead cast — see other tests)."""
        Spell = self._spell_class([self._creature_spec(optional=False)])
        game = _make_game()
        player = game.players[0]
        card = Spell(name="Required Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, card)
        _add_mana(player, ManaType.RED, 1)
        with pytest.raises(CastingError):
            cast_spell(game, player, card)
        assert game.stack.is_empty()   # nothing pushed onto the stack

    def test_optional_declined_when_candidate_present(self):
        """Candidate present but declined (intent with no matching preference,
        min == 0): the spell casts with no target."""
        Spell = self._spell_class([self._creature_spec(optional=True)])
        game = _make_game()
        player = game.players[0]
        self._place_creature(game, 1, "Bystander")
        card = Spell(name="Optional Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, card)
        _add_mana(player, ManaType.RED, 1)
        # Intent routes to the spell but prefers nothing → decline at min == 0.
        player.start_intent("bolt", Intent(
            pattern=GameRef(card=frozenset({("name", "Optional Bolt")})),
            preferences=(),
        ))
        cast_spell(game, player, card)
        player.end_intent("bolt")
        assert game.stack.peek().targets == []

    def test_optional_chosen_when_preferred(self):
        """An optional target IS captured when the intent prefers a candidate."""
        Spell = self._spell_class([self._creature_spec(optional=True)])
        game = _make_game()
        player = game.players[0]
        victim = self._place_creature(game, 1, "Victim")
        card = Spell(name="Optional Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, card)
        _add_mana(player, ManaType.RED, 1)
        player.start_intent("bolt", Intent(
            pattern=GameRef(card=frozenset({("name", "Optional Bolt")})),
            preferences=(Decision.obj(instance=victim.instance_id),),
        ))
        cast_spell(game, player, card)
        player.end_intent("bolt")
        assert game.stack.peek().targets == [victim]

    def test_up_to_two_picks_distinct_targets(self):
        """Two optional specs + an intent preferring both creatures capture two
        DISTINCT targets — the second query excludes the first pick."""
        Spell = self._spell_class([
            self._creature_spec(optional=True),
            self._creature_spec(optional=True),
        ])
        game = _make_game()
        player = game.players[0]
        a = self._place_creature(game, 1, "A")
        b = self._place_creature(game, 1, "B")
        card = Spell(name="Twin Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, card)
        _add_mana(player, ManaType.RED, 1)
        player.start_intent("bolt", Intent(
            pattern=GameRef(card=frozenset({("name", "Twin Bolt")})),
            preferences=(
                Decision.obj(instance=a.instance_id),
                Decision.obj(instance=b.instance_id),
            ),
        ))
        cast_spell(game, player, card)
        player.end_intent("bolt")
        targets = game.stack.peek().targets
        assert set(id(t) for t in targets) == {id(a), id(b)}
        assert len(targets) == 2   # distinct, no duplicate

    def test_up_to_two_with_one_candidate_casts_with_one(self):
        """Two optional specs but only one candidate: casts with a single target
        (the second spec's option set is empty after excluding the first)."""
        Spell = self._spell_class([
            self._creature_spec(optional=True),
            self._creature_spec(optional=True),
        ])
        game = _make_game()
        player = game.players[0]
        only = self._place_creature(game, 1, "Only")
        card = Spell(name="Twin Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, card)
        _add_mana(player, ManaType.RED, 1)
        player.start_intent("bolt", Intent(
            pattern=GameRef(card=frozenset({("name", "Twin Bolt")})),
            preferences=(Decision.obj(instance=only.instance_id),),
        ))
        cast_spell(game, player, card)
        player.end_intent("bolt")
        assert game.stack.peek().targets == [only]


class TestDependentTargetFilterArity:
    """`_safe_filter` supports both (obj) and dependent (obj, chosen) filter
    signatures, so a target's legality can depend on targets already chosen this
    cast (rule 601.2c dependent requirements) without a card-specific backdoor."""

    def test_filter_wants_chosen_detects_arity(self):
        from engine.casting import _filter_wants_chosen
        assert _filter_wants_chosen(lambda obj: True) is False
        assert _filter_wants_chosen(lambda obj, chosen: True) is True
        # The loop-binding idiom `lambda obj, _c=controller` has a DEFAULTED
        # second parameter — it is NOT a dependent filter and must be called with
        # the object alone (regression: binding `chosen` to `_c` broke ~8 cards).
        _controller = object()
        assert _filter_wants_chosen(lambda obj, _c=_controller: True) is False
        assert _filter_wants_chosen(lambda obj, g=None, ctrl=None: True) is False
        # `*rest` is not a required second positional — treated as single-arg.
        assert _filter_wants_chosen(lambda obj, *rest: True) is False

        class _C:
            def one(self, obj):
                return True

            def two(self, obj, chosen):
                return True

            def bound_default(self, obj, _c=None):
                return True

        # Bound methods: `self` is excluded from the counted parameters.
        assert _filter_wants_chosen(_C().one) is False
        assert _filter_wants_chosen(_C().two) is True
        assert _filter_wants_chosen(_C().bound_default) is False

    def test_single_arg_filter_called_with_object_only(self):
        from engine.casting import _safe_filter
        seen = {}

        def _f(obj):
            seen["obj"] = obj
            return obj == "x"

        assert _safe_filter(_f, "x", ["ignored"]) is True
        assert _safe_filter(_f, "y", []) is False
        assert seen["obj"] == "y"

    def test_dependent_filter_receives_chosen(self):
        from engine.casting import _safe_filter
        captured = {}

        def _f(obj, chosen):
            captured["chosen"] = list(chosen)
            return obj in chosen

        assert _safe_filter(_f, "a", ["a", "b"]) is True
        assert _safe_filter(_f, "z", ["a", "b"]) is False
        assert captured["chosen"] == ["a", "b"]

    def test_raising_filter_is_excluded_not_propagated(self):
        from engine.casting import _safe_filter

        def _boom(obj, chosen):
            raise RuntimeError("nope")

        assert _safe_filter(_boom, "a", []) is False


class TestSpellTargetStintRevalidation:
    """cast_spell / cast_spell_free capture the casting controller + each chosen
    target's zone-stint on the StackObject; a target that leaves its selected
    zone and returns before resolution (a new object in the same Python instance)
    is rejected at resolution."""

    def _mark_spell(self, owner):
        from engine.card import Instant
        from engine.types import CardType, TargetRequirement, Zone as _Z

        class _MarkCreature(Instant):
            def get_targets(self, game):
                return [TargetRequirement(
                    filter_fn=lambda o: CardType.CREATURE in getattr(o, "card_types", set()),
                    description="target creature",
                    zone=_Z.BATTLEFIELD,
                )]

            def on_resolve(self, game):
                chosen = getattr(self, "chosen_targets", None) or []
                target = chosen[0] if chosen else None
                if target is not None:
                    target._marked = True

        return _MarkCreature(name="Mark Creature", owner=owner, controller=owner)

    def _cast_free_no_resolve(self, game, player, card, target, from_zone):
        from engine.casting import cast_spell_free
        from engine.decisions import Decision, GameRef
        from engine.intent_player import Intent
        from engine.types import Zone as _Z
        inst = game.refs.instance_id(target, _Z.BATTLEFIELD.value)
        player.start_intent("free", Intent(
            pattern=GameRef(card=frozenset({("name", card.name)})),
            preferences=(Decision.obj(instance=inst),),
        ))
        try:
            cast_spell_free(game, player, card, from_zone)
        finally:
            player.end_intent("free")

    def test_free_cast_marks_target_normally(self):
        from engine.card import Creature
        from engine.stack import resolve_top_of_stack
        from engine.types import Zone
        from test_utils import create_game, set_board_state
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        spell = self._mark_spell(p1)
        set_board_state(game, 1, battlefield=[bear])
        p1.zones[Zone.EXILE].add(spell)
        spell.instance_id = game.refs.instance_id(spell, Zone.EXILE.value)
        self._cast_free_no_resolve(game, p1, spell, bear, Zone.EXILE)
        resolve_top_of_stack(game)
        assert getattr(bear, "_marked", False) is True

    def test_free_cast_leave_and_return_rejected(self):
        from engine.card import Creature
        from engine.stack import resolve_top_of_stack
        from engine.types import Zone
        from engine.zones import move_to_zone
        from test_utils import create_game, set_board_state
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        spell = self._mark_spell(p1)
        set_board_state(game, 1, battlefield=[bear])
        p1.zones[Zone.EXILE].add(spell)
        spell.instance_id = game.refs.instance_id(spell, Zone.EXILE.value)
        self._cast_free_no_resolve(game, p1, spell, bear, Zone.EXILE)
        move_to_zone(game, bear, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        move_to_zone(game, bear, Zone.GRAVEYARD, Zone.BATTLEFIELD)  # new stint
        resolve_top_of_stack(game)
        assert getattr(bear, "_marked", False) is False            # rejected by stint

    def test_normal_cast_context_stored_on_stack_object(self):
        from engine.card import Creature
        from engine.casting import cast_spell as engine_cast_spell
        from engine.decisions import Decision, GameRef
        from engine.intent_player import Intent
        from engine.types import Phase, Zone
        from test_utils import create_game, set_board_state
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        spell = self._mark_spell(p1)
        set_board_state(game, 0, hand=[spell])
        set_board_state(game, 1, battlefield=[bear])
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        inst = game.refs.instance_id(bear, Zone.BATTLEFIELD.value)
        p1.start_intent("c", Intent(
            pattern=GameRef(card=frozenset({("name", spell.name)})),
            preferences=(Decision.obj(instance=inst),),
        ))
        try:
            engine_cast_spell(game, p1, spell)
        finally:
            p1.end_intent("c")
        top = game.stack.peek()
        # The casting controller and the target stint are captured on the stack.
        assert top.activation_context is not None
        assert top.activation_context.controller is p1
        assert top.activation_context.target_instance_ids[0] == inst


# ---------------------------------------------------------------------------
# Spell-cast history — authoritative per-player, per-turn record
# ---------------------------------------------------------------------------


class TestSpellCastHistoryRecord:
    """The turn-stamped record on :class:`~engine.player.Player` itself.

    This is the authoritative surface a cast-triggered ability (Thousand-Year
    Storm) reads its copy count from. It belongs to the player/turn lifecycle:
    per-player, resettable at the turn boundary, and never owned by a trigger
    source.
    """

    def test_record_and_read_round_trips_in_cast_order(self):
        p = DeterministicPlayer("Alice")
        s1, s2 = object(), object()
        p.record_instant_or_sorcery_cast(s1, 3)
        p.record_instant_or_sorcery_cast(s2, 3)
        assert p.instant_or_sorcery_casts_this_turn(3) == [s1, s2]

    def test_read_returns_a_copy_not_the_backing_list(self):
        p = DeterministicPlayer("Alice")
        s1 = object()
        p.record_instant_or_sorcery_cast(s1, 1)
        out = p.instant_or_sorcery_casts_this_turn(1)
        out.append(object())
        assert p.instant_or_sorcery_casts_this_turn(1) == [s1]

    def test_stale_turn_reads_empty(self):
        p = DeterministicPlayer("Alice")
        p.record_instant_or_sorcery_cast(object(), 1)
        assert p.instant_or_sorcery_casts_this_turn(2) == []

    def test_recording_on_a_new_turn_resets_before_appending(self):
        p = DeterministicPlayer("Alice")
        s1, s2 = object(), object()
        p.record_instant_or_sorcery_cast(s1, 1)
        p.record_instant_or_sorcery_cast(s2, 2)  # new turn — resets, then appends
        assert p.instant_or_sorcery_casts_this_turn(1) == []
        assert p.instant_or_sorcery_casts_this_turn(2) == [s2]

    def test_players_keep_separate_records(self):
        p1 = DeterministicPlayer("Alice")
        p2 = DeterministicPlayer("Bob")
        a, b = object(), object()
        p1.record_instant_or_sorcery_cast(a, 1)
        p2.record_instant_or_sorcery_cast(b, 1)
        assert p1.instant_or_sorcery_casts_this_turn(1) == [a]
        assert p2.instant_or_sorcery_casts_this_turn(1) == [b]

    def test_record_returns_prior_qualifying_cast_count(self):
        # Each recording reports how many qualifying casts came before it this
        # turn — the immutable prior-cast count for that occurrence.
        p = DeterministicPlayer("Alice")
        s1, s2, s3 = object(), object(), object()
        assert p.record_instant_or_sorcery_cast(s1, 1) == 0
        assert p.record_instant_or_sorcery_cast(s2, 1) == 1
        assert p.record_instant_or_sorcery_cast(s3, 1) == 2

    def test_record_counts_a_recast_object_as_a_new_occurrence(self):
        # The SAME object recorded twice this turn is two occurrences: the second
        # recording reports one prior cast, not zero. Excluding "the current cast"
        # by identity would instead treat both entries as the current cast.
        p = DeterministicPlayer("Alice")
        obj = object()
        assert p.record_instant_or_sorcery_cast(obj, 1) == 0
        assert p.record_instant_or_sorcery_cast(obj, 1) == 1
        assert p.instant_or_sorcery_casts_this_turn(1) == [obj, obj]

    def test_record_prior_count_restarts_at_the_turn_boundary(self):
        p = DeterministicPlayer("Alice")
        p.record_instant_or_sorcery_cast(object(), 1)
        assert p.record_instant_or_sorcery_cast(object(), 1) == 1
        # A new turn resets the record, so the count restarts from zero.
        assert p.record_instant_or_sorcery_cast(object(), 2) == 0


class TestSpellCastHistoryPipeline:
    """The casting pipeline records qualifying casts exactly once, at the single
    authoritative cast site, and only for instant/sorcery spells."""

    def _fresh(self) -> tuple[GameState, DeterministicPlayer]:
        game = _make_game()
        return game, game.players[0]

    def test_cast_instant_is_recorded(self):
        game, p = self._fresh()
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{0}"), owner=p)
        _add_to_hand(game, 0, bolt)
        cast_spell(game, p, bolt)
        assert p.instant_or_sorcery_casts_this_turn(game.turn_number) == [bolt]

    def test_cast_sorcery_is_recorded(self):
        game, p = self._fresh()
        ritual = Sorcery(name="Ritual", mana_cost=ManaCost.parse("{0}"), owner=p)
        _add_to_hand(game, 0, ritual)
        cast_spell(game, p, ritual)
        assert p.instant_or_sorcery_casts_this_turn(game.turn_number) == [ritual]

    def test_instant_is_recorded_exactly_once(self):
        game, p = self._fresh()
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{0}"), owner=p)
        _add_to_hand(game, 0, bolt)
        cast_spell(game, p, bolt)
        history = p.instant_or_sorcery_casts_this_turn(game.turn_number)
        assert history.count(bolt) == 1

    def test_nonqualifying_spells_do_not_record(self):
        # A creature, artifact, enchantment, and planeswalker each cast in a
        # fresh game (empty stack for sorcery-speed timing) — none is recorded.
        nonqualifying = [
            Creature(name="Bear", base_power=2, base_toughness=2,
                     mana_cost=ManaCost.parse("{0}")),
            Artifact(name="Rock", mana_cost=ManaCost.parse("{0}")),
            Enchantment(name="Glow", mana_cost=ManaCost.parse("{0}")),
            Planeswalker(name="Walker", mana_cost=ManaCost.parse("{0}"),
                         starting_loyalty=3),
        ]
        for card in nonqualifying:
            game, p = self._fresh()
            card.owner = p
            _add_to_hand(game, 0, card)
            cast_spell(game, p, card)
            assert p.instant_or_sorcery_casts_this_turn(game.turn_number) == [], (
                f"{card.name} should not be recorded"
            )

    def test_playing_a_land_does_not_record(self):
        # Lands are played via a special action (never through cast_spell), so
        # they are structurally excluded from the record.
        game, p = self._fresh()
        forest = Land(name="Forest", owner=p)
        _add_to_hand(game, 0, forest)
        play_land(game, p, forest)
        assert p.instant_or_sorcery_casts_this_turn(game.turn_number) == []

    def test_two_players_get_separate_histories_through_the_pipeline(self):
        game = _make_game()
        p1, p2 = game.players
        a = Instant(name="A", mana_cost=ManaCost.parse("{0}"), owner=p1)
        b = Instant(name="B", mana_cost=ManaCost.parse("{0}"), owner=p2)
        _add_to_hand(game, 0, a)
        _add_to_hand(game, 1, b)
        cast_spell(game, p1, a)
        cast_spell(game, p2, b)  # non-active player, but instant speed is legal
        t = game.turn_number
        assert p1.instant_or_sorcery_casts_this_turn(t) == [a]
        assert p2.instant_or_sorcery_casts_this_turn(t) == [b]

    def test_free_cast_is_recorded(self):
        from engine.casting import cast_spell_free
        from engine.types import Zone

        game, p = self._fresh()
        bolt = Instant(name="FreeBolt", mana_cost=ManaCost.parse("{5}"), owner=p)
        p.zones[Zone.HAND].add(bolt)
        cast_spell_free(game, p, bolt, Zone.HAND)
        assert p.instant_or_sorcery_casts_this_turn(game.turn_number) == [bolt]

    def test_turn_rollover_resets_through_the_pipeline(self):
        game, p = self._fresh()
        a = Instant(name="A", mana_cost=ManaCost.parse("{0}"), owner=p)
        b = Instant(name="B", mana_cost=ManaCost.parse("{0}"), owner=p)
        _add_to_hand(game, 0, a)
        _add_to_hand(game, 0, b)
        cast_spell(game, p, a)
        t1 = game.turn_number
        assert p.instant_or_sorcery_casts_this_turn(t1) == [a]
        game.turn_number += 1
        # A new turn: last turn's cast no longer contributes.
        assert p.instant_or_sorcery_casts_this_turn(game.turn_number) == []
        cast_spell(game, p, b)
        assert p.instant_or_sorcery_casts_this_turn(game.turn_number) == [b]
        assert p.instant_or_sorcery_casts_this_turn(t1) == []

    def test_cast_stamps_prior_qualifying_count_on_the_stack_object(self):
        # The cast's StackObject — the stack representation of that one occurrence
        # — carries the immutable prior-qualifying-cast count read at record time.
        game, p = self._fresh()
        a = Instant(name="A", mana_cost=ManaCost.parse("{0}"), owner=p)
        b = Instant(name="B", mana_cost=ManaCost.parse("{0}"), owner=p)
        _add_to_hand(game, 0, a)
        _add_to_hand(game, 0, b)
        cast_spell(game, p, a)
        cast_spell(game, p, b)
        stamp = {so.source: so.prior_qualifying_casts for so in game.stack._items}
        assert stamp[a] == 0
        assert stamp[b] == 1

    def test_free_cast_stamps_prior_qualifying_count_on_the_stack_object(self):
        from engine.casting import cast_spell_free
        from engine.types import Zone

        game, p = self._fresh()
        a = Instant(name="A", mana_cost=ManaCost.parse("{0}"), owner=p)
        b = Instant(name="B", mana_cost=ManaCost.parse("{5}"), owner=p)
        _add_to_hand(game, 0, a)
        p.zones[Zone.HAND].add(b)
        cast_spell(game, p, a)
        cast_spell_free(game, p, b, Zone.HAND)   # b is the second qualifying cast
        stamp = {so.source: so.prior_qualifying_casts for so in game.stack._items}
        assert stamp[a] == 0
        assert stamp[b] == 1

    def test_nonqualifying_cast_stamps_no_prior_count(self):
        # A creature is not a qualifying cast, so its StackObject carries no count.
        game, p = self._fresh()
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{0}"), owner=p)
        _add_to_hand(game, 0, bear)
        cast_spell(game, p, bear)
        (so,) = [s for s in game.stack._items if s.source is bear]
        assert so.prior_qualifying_casts is None


class TestFlashbackDisposition:
    """Flashback is an EXPLICIT cast mode: ``cast_spell_free(...,
    mode=CastMode.FLASHBACK)`` validates the claim (graveyard source + a real
    flashback cost) and stamps ``departure_zone = Zone.EXILE`` on that cast's
    StackObject, which :func:`engine.stack.move_spell_off_stack` honours any
    time the spell leaves the stack (rule 702.34a). The generic free-cast
    helper never infers the mode from card attributes: a flashback-capable
    card free-cast from the graveyard WITHOUT the mode keeps the graveyard
    default.
    """

    def _flashback_instant(self, player):
        card = Instant(name="Recall", mana_cost=ManaCost.parse("{1}{U}"), owner=player)
        card.controller = player
        card.flashback_cost = ManaCost.parse("{2}{U}")
        return card

    def test_flashback_mode_from_graveyard_exiles(self):
        from engine.casting import CastMode, cast_spell_free
        from engine.stack import resolve_top_of_stack
        from engine.types import Zone

        game = _make_game()
        p = game.players[0]
        card = self._flashback_instant(p)
        game.get_graveyard(p).add(card)

        cast_spell_free(game, p, card, Zone.GRAVEYARD, mode=CastMode.FLASHBACK)
        # The disposition rides on this cast's StackObject.
        (so,) = [s for s in game.stack._items if s.source is card]
        assert so.departure_zone == Zone.EXILE

        resolve_top_of_stack(game)
        assert game.get_exile(p).contains(card)
        assert not game.get_graveyard(p).contains(card)

    def test_flashback_capable_graveyard_cast_without_mode_keeps_graveyard(self):
        """The mode is never inferred: the SAME flashback-capable card,
        free-cast from the graveyard without selecting flashback (a
        Underworld-Breach-style graveyard cast), is NOT exiled."""
        from engine.casting import cast_spell_free
        from engine.stack import resolve_top_of_stack
        from engine.types import Zone

        game = _make_game()
        p = game.players[0]
        card = self._flashback_instant(p)
        game.get_graveyard(p).add(card)

        cast_spell_free(game, p, card, Zone.GRAVEYARD)
        (so,) = [s for s in game.stack._items if s.source is card]
        assert so.departure_zone is None

        resolve_top_of_stack(game)
        assert game.get_graveyard(p).contains(card)
        assert not game.get_exile(p).contains(card)

    def test_non_flashback_free_cast_keeps_graveyard(self):
        """A card with no flashback cost, free-cast from the graveyard, keeps the
        default graveyard disposition (no silent exile)."""
        from engine.casting import cast_spell_free
        from engine.stack import resolve_top_of_stack
        from engine.types import Zone

        game = _make_game()
        p = game.players[0]
        card = Instant(name="Plain", mana_cost=ManaCost.parse("{U}"), owner=p)
        card.controller = p
        game.get_graveyard(p).add(card)

        cast_spell_free(game, p, card, Zone.GRAVEYARD)
        (so,) = [s for s in game.stack._items if s.source is card]
        assert so.departure_zone is None

        resolve_top_of_stack(game)
        assert game.get_graveyard(p).contains(card)
        assert not game.get_exile(p).contains(card)

    def test_flashback_card_from_exile_keeps_graveyard(self):
        """A flashback-cost card free-cast from EXILE in the default mode
        (cascade/Etali style) is not a flashback cast and keeps the graveyard
        default."""
        from engine.casting import cast_spell_free
        from engine.stack import resolve_top_of_stack
        from engine.types import Zone

        game = _make_game()
        p = game.players[0]
        card = self._flashback_instant(p)
        game.get_exile(p).add(card)

        cast_spell_free(game, p, card, Zone.EXILE)
        (so,) = [s for s in game.stack._items if s.source is card]
        assert so.departure_zone is None

        resolve_top_of_stack(game)
        assert game.get_graveyard(p).contains(card)
        assert not game.get_exile(p).contains(card)

    # -- rejected mode claims are ATOMIC: every check runs before any mutation,
    #    so controller, owner, zones, stack, cast history, and target state are
    #    byte-for-byte what they were. Each negative test snapshots that state
    #    before the claim and asserts it unchanged after the CastingError.

    @staticmethod
    def _observable_state(game, card):
        """Snapshot everything a rejected flashback claim must leave untouched."""
        from engine.types import Zone

        return {
            "controller": card.controller,
            "owner": card.owner,
            "zones": [
                (i, zone.name, tuple(id(o) for o in player.zones[zone].get_all()))
                for i, player in enumerate(game.players)
                for zone in Zone
                if zone in player.zones
            ],
            "stack": tuple(id(so) for so in game.stack._items),
            "cast_history": [
                (
                    tuple(id(s) for s in player._instant_sorcery_casts),
                    player._instant_sorcery_cast_turn,
                )
                for player in game.players
            ],
            "chosen_targets": getattr(card, "chosen_targets", None),
            "is_tapped": getattr(card, "is_tapped", None),
        }

    def _assert_rejected_claim_untouched(self, game, player, card, from_zone):
        """The FLASHBACK claim raises CastingError and mutates nothing."""
        from engine.casting import CastingError, CastMode, cast_spell_free

        before = self._observable_state(game, card)
        with pytest.raises(CastingError):
            cast_spell_free(game, player, card, from_zone, mode=CastMode.FLASHBACK)
        assert self._observable_state(game, card) == before

    def test_flashback_mode_from_exile_rejected(self):
        """Flashback casts from the graveyard only: an exile claim is rejected
        atomically (the card had no controller — it must still have none)."""
        from engine.types import Zone

        game = _make_game()
        p = game.players[0]
        card = Instant(name="Recall", mana_cost=ManaCost.parse("{1}{U}"))
        card.owner = p  # owner without the constructor's controller default
        card.flashback_cost = ManaCost.parse("{2}{U}")
        assert card.controller is None  # would be mutated by a non-atomic cast
        game.get_exile(p).add(card)

        self._assert_rejected_claim_untouched(game, p, card, Zone.EXILE)
        assert game.get_exile(p).contains(card)
        assert card.controller is None

    def test_flashback_mode_from_hand_rejected(self):
        """A hand claim is rejected atomically — flashback never casts from
        hand, whatever the card's flashback cost says."""
        from engine.types import Zone

        game = _make_game()
        p = game.players[0]
        card = self._flashback_instant(p)
        game.get_hand(p).add(card)

        self._assert_rejected_claim_untouched(game, p, card, Zone.HAND)
        assert game.get_hand(p).contains(card)

    def test_flashback_mode_without_flashback_cost_rejected(self):
        """CastMode.FLASHBACK on a card with no flashback cost is rejected
        atomically (controller stays unset — validation precedes the
        controller/owner defaults)."""
        from engine.types import Zone

        game = _make_game()
        p = game.players[0]
        card = Instant(name="Plain", mana_cost=ManaCost.parse("{U}"))
        card.owner = p  # owner without the constructor's controller default
        assert card.controller is None
        game.get_graveyard(p).add(card)

        self._assert_rejected_claim_untouched(game, p, card, Zone.GRAVEYARD)
        assert game.get_graveyard(p).contains(card)
        assert card.controller is None

    def test_flashback_mode_from_another_players_graveyard_rejected(self):
        """Flashback is owner-scoped: the card must be in the CASTING player's
        own graveyard. A flashback claim on a card sitting in the opponent's
        graveyard is rejected atomically — even when the card's owner field
        would permit the caster (owner is None here)."""
        from engine.types import Zone

        game = _make_game()
        p1, p2 = game.players
        card = Instant(name="Recall", mana_cost=ManaCost.parse("{1}{U}"))
        card.flashback_cost = ManaCost.parse("{2}{U}")
        assert card.owner is None and card.controller is None
        game.get_graveyard(p2).add(card)

        self._assert_rejected_claim_untouched(game, p1, card, Zone.GRAVEYARD)
        assert game.get_graveyard(p2).contains(card)
        assert card.owner is None and card.controller is None

    def test_flashback_mode_wrong_ownership_rejected(self):
        """Flashback is ownership-compatible: a card OWNED by another player is
        not flashback-castable, even from a graveyard the caster can reach
        (rule 702.34a casts from its owner's graveyard). Rejected atomically."""
        from engine.types import Zone

        game = _make_game()
        p1, p2 = game.players
        card = self._flashback_instant(p2)  # owned (and controlled) by p2
        game.get_graveyard(p1).add(card)  # misplaced into p1's graveyard

        self._assert_rejected_claim_untouched(game, p1, card, Zone.GRAVEYARD)
        assert game.get_graveyard(p1).contains(card)
        assert card.owner is p2
        assert card.controller is p2

    def test_flashback_mode_own_card_in_own_graveyard_accepted(self):
        """The owner-scoped checks accept the legal case: the caster's own card
        in the caster's own graveyard flashes back and exiles on resolution."""
        from engine.casting import CastMode, cast_spell_free
        from engine.stack import resolve_top_of_stack
        from engine.types import Zone

        game = _make_game()
        p = game.players[0]
        card = self._flashback_instant(p)
        game.get_graveyard(p).add(card)

        so = cast_spell_free(game, p, card, Zone.GRAVEYARD, mode=CastMode.FLASHBACK)
        assert so.departure_zone == Zone.EXILE
        resolve_top_of_stack(game)
        assert game.get_exile(p).contains(card)


class TestStackOccurrenceTargeting:
    """Zone.STACK target requirements enumerate exact StackObject OCCURRENCES.

    A spell on the stack is targeted as its StackObject, never its source card:
    two casts/copies of the same card are distinct targets, a triggered ability
    sharing a spell's source card is not that spell, and a chosen occurrence
    stays legal only while IT is on ``game.stack`` — a departed occurrence is
    nulled by the resolution-time stint check even when its card was re-cast
    (the card's new stack presence belongs to the new occurrence).
    """

    class _Counter(Instant):
        """Minimal engine-level 'counter target spell' instant."""

        def __init__(self, **kwargs):
            kwargs.setdefault("name", "Test Counter")
            kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
            super().__init__(**kwargs)
            self.countered = None

        def get_targets(self, game):
            from engine.types import TargetRequirement, Zone

            return [
                TargetRequirement(
                    filter_fn=lambda obj: getattr(obj, "is_spell", False)
                    and getattr(obj, "source", None) is not self,
                    description="target spell",
                    zone=Zone.STACK,
                )
            ]

        def on_resolve(self, game):
            from engine.stack import move_spell_off_stack

            chosen = getattr(self, "chosen_targets", None)
            target = chosen[0] if chosen else None
            if isinstance(target, StackObject):
                move_spell_off_stack(game, target)
                self.countered = target

    def _game(self):
        game = _make_game()
        return game, game.players[0], game.players[1]

    def _spell(self, owner, name="Zap"):
        card = Instant(name=name, mana_cost=ManaCost.parse("{U}"), owner=owner)
        card.controller = owner
        return card

    def _cast_counter_at(self, game, player, occurrence):
        """Cast a _Counter through the REAL pipeline, selecting *occurrence*
        by its engine-minted stack instance id (the occurrence's own identity,
        matching what the Zone.STACK enumeration offers)."""
        from engine.casting import cast_spell_free
        from engine.types import Zone

        counter = self._Counter(owner=player, controller=player)
        game.get_hand(player).add(counter)
        occ_iid = game.refs.instance_id(occurrence, Zone.STACK.value)
        player.start_intent("counter", Intent(
            pattern=GameRef(card=frozenset({("name", counter.name)})),
            preferences=(Decision.obj(instance=occ_iid),),
        ))
        try:
            counter_so = cast_spell_free(game, player, counter, Zone.HAND)
        finally:
            player.end_intent("counter")
        return counter, counter_so

    def test_real_pipeline_targets_exact_occurrence(self):
        """The chosen target IS the StackObject occurrence, not the source
        card; countering moves the card to its owner's graveyard."""
        from engine.casting import cast_spell_free
        from engine.stack import resolve_top_of_stack
        from engine.types import Zone

        game, p1, p2 = self._game()
        spell = self._spell(p2)
        game.get_hand(p2).add(spell)
        spell_so = cast_spell_free(game, p2, spell, Zone.HAND)

        counter, counter_so = self._cast_counter_at(game, p1, spell_so)
        assert counter_so.targets[0] is spell_so  # the occurrence, not the card

        resolve_top_of_stack(game)  # counter resolves
        assert counter.countered is spell_so
        assert game.get_graveyard(p2).contains(spell)
        assert game.stack.is_empty()

    def test_ability_sharing_source_card_is_not_targetable(self):
        """A non-spell stack object (a trigger/ability) is never offered as a
        'target spell', even though it has a source card: with only it on the
        stack the counter has no legal target and the cast is rejected."""
        from engine.casting import CastingError, cast_spell_free
        from engine.types import Zone

        game, p1, p2 = self._game()
        permanent = Creature(name="Watcher", base_power=2, base_toughness=2, owner=p2)
        permanent.controller = p2
        game.get_battlefield(p2).add(permanent)
        trigger = StackObject(source=permanent, controller=p2)  # is_spell=False
        game.stack.push(trigger)

        counter = self._Counter(owner=p1, controller=p1)
        game.get_hand(p1).add(counter)
        with pytest.raises(CastingError):
            cast_spell_free(game, p1, counter, Zone.HAND)
        assert game.get_hand(p1).contains(counter)  # rolled back
        assert game.stack.contains(trigger)

    def test_copy_occurrence_targeted_distinctly_from_original(self):
        """A spell COPY is a distinct occurrence: targeting and countering the
        copy leaves the original cast (and its card) untouched."""
        from engine.casting import cast_spell_free
        from engine.stack import copy_spell, resolve_top_of_stack
        from engine.types import Zone

        game, p1, p2 = self._game()
        spell = self._spell(p2)
        game.get_hand(p2).add(spell)
        spell_so = cast_spell_free(game, p2, spell, Zone.HAND)
        copy_so = copy_spell(game, spell_so, p2)
        game.stack.push(copy_so)

        counter, counter_so = self._cast_counter_at(game, p1, copy_so)
        assert counter_so.targets[0] is copy_so

        resolve_top_of_stack(game)  # counter resolves, countering the copy
        assert counter.countered is copy_so
        assert not game.stack.contains(copy_so)
        assert game.stack.contains(spell_so)  # original untouched
        assert p2.zones[Zone.STACK].contains(spell)  # card still cast
        assert not game.get_graveyard(p2).contains(spell)

    def test_departed_occurrence_fizzles_even_after_recast(self):
        """Once the targeted occurrence leaves the stack, the counter fizzles
        at resolution — a re-cast of the SAME card (a new occurrence) is never
        recovered from the source card and is not touched."""
        from engine.casting import cast_spell_free
        from engine.stack import move_spell_off_stack, resolve_top_of_stack
        from engine.types import Zone

        game, p1, p2 = self._game()
        spell = self._spell(p2)
        game.get_hand(p2).add(spell)
        spell_so = cast_spell_free(game, p2, spell, Zone.HAND)

        counter, _ = self._cast_counter_at(game, p1, spell_so)

        # The targeted occurrence departs (countered by something else) …
        assert move_spell_off_stack(game, spell_so) is True
        assert game.get_graveyard(p2).contains(spell)
        # … and the same card is re-cast: a NEW occurrence.
        recast_so = cast_spell_free(game, p2, spell, Zone.GRAVEYARD)
        assert recast_so is not spell_so

        resolve_top_of_stack(game)  # the recast resolves (instant → graveyard)
        assert game.get_graveyard(p2).contains(spell)

        resolve_top_of_stack(game)  # the counter resolves — and fizzles
        assert counter.countered is None
        assert sum(1 for o in game.get_graveyard(p2).get_all() if o is spell) == 1
        assert not game.get_exile(p2).contains(spell)
        assert game.stack.is_empty()


# ---------------------------------------------------------------------------
# Dormant-event firing (Phase I, issue #44): SpellCastTriggeredEvent
# ---------------------------------------------------------------------------

class TestSpellCastEventFiring:
    """cast_spell / cast_spell_free fire SpellCastTriggeredEvent exactly once,
    after the spell is on the stack (Phase I).

    Before Phase I neither cast path fired the event, so every "whenever you
    cast ..." trigger (prowess, Thousand-Year Storm, Consuming Aberration's
    mill) was dormant. The event carries the cast *card* on both ``spell`` and
    ``card`` (subscribers read ``event.spell.card_types``) and the caster on
    both ``player`` and ``controller``.
    """

    @staticmethod
    def _spy(game: GameState) -> list:
        events: list = []

        def _cond(_g: GameState, event: object) -> bool:
            events.append(event)
            return False  # observe only; don't put a trigger on the stack

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_cond,
                effect=lambda _g: None,
                source=object(),
                controller=game.players[0],
            )
        )
        return events

    def test_cast_instant_fires_once_with_card_and_caster(self):
        game = _make_game()
        player = game.players[0]
        bolt = Instant(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, bolt)
        _add_mana(player, ManaType.RED, 1)
        events = self._spy(game)

        cast_spell(game, player, bolt)

        assert len(events) == 1
        e = events[0]
        assert e.spell is bolt          # subscribers read event.spell.card_types
        assert e.card is bolt
        assert e.player is player
        assert e.controller is player

    def test_event_fires_after_spell_is_on_the_stack(self):
        """A subscriber's condition must see the just-cast spell already on the
        stack (rule 601.2i complete before 603.3)."""
        game = _make_game()
        player = game.players[0]
        bolt = Instant(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, bolt)
        _add_mana(player, ManaType.RED, 1)
        on_stack_at_fire: list = []

        def _cond(g: GameState, event: object) -> bool:
            on_stack_at_fire.append(
                any(so.source is event.spell for so in g.stack._items)
            )
            return False

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent, condition=_cond,
                effect=lambda _g: None, source=object(), controller=player,
            )
        )
        cast_spell(game, player, bolt)
        assert on_stack_at_fire == [True]

    def test_cast_creature_also_fires_event(self):
        """The event fires for a NON-instant/sorcery spell too — subscribers
        filter on card type in their own condition, so the fire is unconditional
        (a creature-cast still triggers Kykar / Consuming Aberration)."""
        game = _make_game()
        player = game.players[0]
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost(generic=2))
        _add_to_hand(game, 0, bear)
        _add_mana(player, ManaType.GREEN, 2)
        events = self._spy(game)

        cast_spell(game, player, bear)

        assert len(events) == 1
        assert events[0].spell is bear

    def test_cast_spell_free_fires_once(self):
        game = _make_game()
        player = game.players[0]
        bolt = Instant(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        game.get_hand(player).add(bolt)
        events = self._spy(game)

        cast_spell_free(game, player, bolt, Zone.HAND)

        assert len(events) == 1
        assert events[0].spell is bolt
        assert events[0].player is player

    def test_two_casts_fire_two_events_never_double(self):
        """Each cast fires exactly one event — two casts, two events (no
        double-fire that would double-count a Storm)."""
        game = _make_game()
        player = game.players[0]
        a = Instant(name="A", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        b = Instant(name="B", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, a)
        _add_to_hand(game, 0, b)
        _add_mana(player, ManaType.RED, 2)
        events = self._spy(game)

        cast_spell(game, player, a)
        cast_spell(game, player, b)

        assert [e.spell for e in events] == [a, b]
