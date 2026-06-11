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
    is_sorcery_speed,
    play_land,
)
from engine.decisions import Decision, GameRef
from engine.game_state import GameState
from engine.intent_player import DeterministicPlayer, Intent
from engine.stack import StackObject
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Step


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
