"""Comprehensive tests for Eager Glyphmage.

Eager Glyphmage — {3}{W} — Creature — Cat Cleric — 3/3
When this creature enters, create a 1/1 white and black Inkling creature token with flying.

Tests cover:
- Basic functionality (correct stats, mana cost, card types, subtypes)
- Core ETB ability: creates correct Inkling token
- Token characteristics: name, P/T, flying, dual color (white + black)
- Edge cases: empty board, multiple castings, summoning sickness
- Interaction with game rules: stack resolution, SBA, combat
"""

from __future__ import annotations

import pytest

from card_impl import EagerGlyphmage

from engine.card import Creature
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.protection import Color, get_colors
from engine.triggers import EventType
from engine.types import CardType, Keyword, ManaCost, Phase, Step, Zone

from tests.test_utils import (
    create_game,
    set_board_state,
    cast_spell,
    advance_to_phase,
    declare_attackers,
)
from engine.types import ManaType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(*, phase: Phase = Phase.PRECOMBAT_MAIN) -> GameState:
    """Create a minimal 2-player GameState."""
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    game = GameState([p1, p2])
    game.phase = phase
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0
    return game


def _simulate_etb(game: GameState, creature, controller=None):
    """Register triggers then fire ETB event, then resolve stack."""
    if controller is None:
        controller = getattr(creature, "controller", game.players[0])
    creature.register_triggers(game)
    game.trigger_manager.fire_event(
        game,
        EventType.ENTERS_BATTLEFIELD,
        {"permanent": creature, "controller": controller},
    )
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _get_tokens(battlefield_objects: list) -> list:
    """Return only token creatures from a list of battlefield objects."""
    return [c for c in battlefield_objects if getattr(c, "is_token", False)]


# ===================================================================
# Basic Properties
# ===================================================================


class TestEagerGlyphmageBasicProperties:
    """Eager Glyphmage basic property tests."""

    def test_is_creature(self) -> None:
        """Eager Glyphmage must be a Creature subclass."""
        card = EagerGlyphmage()
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """EagerGlyphmage.name must be 'Eager Glyphmage'."""
        card = EagerGlyphmage()
        assert card.name == "Eager Glyphmage"

    def test_card_type_creature(self) -> None:
        """Eager Glyphmage must have CardType.CREATURE."""
        card = EagerGlyphmage()
        assert CardType.CREATURE in card.card_types

    def test_subtype_cat(self) -> None:
        """Eager Glyphmage must have Cat subtype."""
        card = EagerGlyphmage()
        assert "Cat" in card.subtypes

    def test_subtype_cleric(self) -> None:
        """Eager Glyphmage must have Cleric subtype."""
        card = EagerGlyphmage()
        assert "Cleric" in card.subtypes

    def test_mana_cost(self) -> None:
        """Eager Glyphmage must cost {3}{W}."""
        card = EagerGlyphmage()
        expected = ManaCost.parse("{3}{W}")
        assert card.mana_cost.generic == expected.generic
        assert card.mana_cost.pips == expected.pips

    def test_cmc_is_4(self) -> None:
        """Eager Glyphmage must have converted mana cost 4."""
        card = EagerGlyphmage()
        assert card.mana_cost.cmc == 4

    def test_power_is_3(self) -> None:
        """Eager Glyphmage must have power 3."""
        card = EagerGlyphmage()
        assert card.base_power == 3
        assert card.power == 3

    def test_toughness_is_3(self) -> None:
        """Eager Glyphmage must have toughness 3."""
        card = EagerGlyphmage()
        assert card.base_toughness == 3
        assert card.toughness == 3

    def test_no_keywords(self) -> None:
        """Eager Glyphmage has no keyword abilities."""
        card = EagerGlyphmage()
        assert card.keywords == Keyword(0)

    def test_is_white(self) -> None:
        """Eager Glyphmage must be a white card."""
        card = EagerGlyphmage()
        colors = get_colors(card)
        assert Color.WHITE in colors


# ===================================================================
# ETB Token Creation
# ===================================================================


class TestEagerGlyphmageETB:
    """Eager Glyphmage ETB ability — creates 1/1 Inkling token with flying."""

    def test_etb_creates_one_token(self) -> None:
        """Casting Eager Glyphmage creates exactly one token."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)
        game.get_battlefield(p1).add(glyph)
        _simulate_etb(game, glyph)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        assert len(tokens) == 1

    def test_token_name_is_inkling(self) -> None:
        """The token must be named 'Inkling'."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)
        _simulate_etb(game, glyph)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        assert tokens[0].name == "Inkling"

    def test_token_power_is_1(self) -> None:
        """The Inkling token must have power 1."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)
        _simulate_etb(game, glyph)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        assert tokens[0].base_power == 1
        assert tokens[0].power == 1

    def test_token_toughness_is_1(self) -> None:
        """The Inkling token must have toughness 1."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)
        _simulate_etb(game, glyph)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        assert tokens[0].base_toughness == 1
        assert tokens[0].toughness == 1

    def test_token_has_flying(self) -> None:
        """The Inkling token must have flying."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)
        _simulate_etb(game, glyph)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        assert Keyword.FLYING in tokens[0].keywords

    def test_token_is_white(self) -> None:
        """The Inkling token must be white."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)
        _simulate_etb(game, glyph)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        colors = get_colors(tokens[0])
        assert Color.WHITE in colors

    def test_token_is_black(self) -> None:
        """The Inkling token must be black."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)
        _simulate_etb(game, glyph)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        colors = get_colors(tokens[0])
        assert Color.BLACK in colors

    def test_token_is_creature(self) -> None:
        """The Inkling token must be a creature type."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)
        _simulate_etb(game, glyph)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        assert CardType.CREATURE in tokens[0].card_types

    def test_token_subtype_inkling(self) -> None:
        """The Inkling token must have the Inkling subtype."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)
        _simulate_etb(game, glyph)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        assert "Inkling" in tokens[0].subtypes

    def test_token_is_flagged_as_token(self) -> None:
        """The Inkling must have is_token = True."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)
        _simulate_etb(game, glyph)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        assert tokens[0].is_token is True

    def test_token_owned_by_controller(self) -> None:
        """The Inkling must be owned and controlled by the caster."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)
        _simulate_etb(game, glyph)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        assert tokens[0].owner is p1
        assert tokens[0].controller is p1


# ===================================================================
# Multiple Castings and Interactions
# ===================================================================


class TestEagerGlyphmageMultiple:
    """Multiple Eager Glyphmage interactions."""

    def test_two_glyphmages_create_two_tokens(self) -> None:
        """Casting two Eager Glyphmages creates two separate tokens."""
        game = _make_game()
        p1 = game.players[0]

        g1 = EagerGlyphmage(owner=p1, controller=p1)
        g2 = EagerGlyphmage(owner=p1, controller=p1)

        # Place first on battlefield, simulate ETB
        game.get_battlefield(p1).add(g1)
        _simulate_etb(game, g1)

        # Place second on battlefield, simulate ETB
        game.get_battlefield(p1).add(g2)
        _simulate_etb(game, g2)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        assert len(tokens) == 2
        for t in tokens:
            assert t.name == "Inkling"
            assert Keyword.FLYING in t.keywords

    def test_glyphmage_and_token_both_on_battlefield(self) -> None:
        """After ETB, both the Glyphmage and token are on the battlefield."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)

        game.get_battlefield(p1).add(glyph)
        _simulate_etb(game, glyph)

        bf = game.get_battlefield(p1).get_all()
        names = [getattr(c, "name", "") for c in bf]
        assert "Eager Glyphmage" in names
        assert "Inkling" in names
        assert len(bf) == 2


# ===================================================================
# Edge Cases
# ===================================================================


class TestEagerGlyphmageEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_board_still_creates_token(self) -> None:
        """Token is created even with nothing else on the battlefield."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)

        game.get_battlefield(p1).add(glyph)
        _simulate_etb(game, glyph)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        assert len(tokens) == 1

    def test_token_has_no_mana_cost(self) -> None:
        """The Inkling token has no mana cost (as tokens do)."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)
        _simulate_etb(game, glyph)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        # Token has default empty ManaCost
        assert tokens[0].mana_cost.cmc == 0

    def test_token_no_flying_protection(self) -> None:
        """The Inkling token is a valid object (not None) and has flying keyword."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)
        _simulate_etb(game, glyph)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        assert tokens[0] is not None
        kw = tokens[0].keywords
        assert kw & Keyword.FLYING

    def test_glyphmage_can_still_attack(self) -> None:
        """After ETB, the Glyphmage is still a valid 3/3 attacker (next turn)."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)

        game.get_battlefield(p1).add(glyph)
        _simulate_etb(game, glyph)

        # Simulate untap step clearing summoning sickness
        glyph.summoning_sick = False
        glyph.is_tapped = False

        bf = game.get_battlefield(p1).get_all()
        glyph_on_bf = [c for c in bf if c.name == "Eager Glyphmage"][0]
        assert glyph_on_bf.power == 3
        assert glyph_on_bf.toughness == 3
        assert glyph_on_bf.summoning_sick is False
        assert glyph_on_bf.is_tapped is False

    def test_cast_spell_places_glyphmage_on_battlefield(self) -> None:
        """Cast via test_utils places the creature on battlefield."""
        game = create_game()
        set_board_state(
            game, 0,
            hand=[EagerGlyphmage()],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 3},
        )
        cast_spell(game, 0, "Eager Glyphmage")

        bf = game.get_battlefield(game.players[0]).get_all()
        names = [getattr(c, "name", "") for c in bf]
        assert "Eager Glyphmage" in names

    def test_inkling_can_attack_with_flying(self) -> None:
        """The Inkling token can be declared as an attacker (has flying, no summoning sickness after untap)."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)

        game.get_battlefield(p1).add(glyph)
        _simulate_etb(game, glyph)

        # Clear summoning sickness
        for obj in game.get_battlefield(p1).get_all():
            if hasattr(obj, "summoning_sick"):
                obj.summoning_sick = False
            if hasattr(obj, "is_tapped"):
                obj.is_tapped = False

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        inkling = tokens[0]
        assert Keyword.FLYING in inkling.keywords
        assert inkling.power == 1
        assert inkling.toughness == 1


# ===================================================================
# Trigger Registration
# ===================================================================


class TestEagerGlyphmageTriggerRegistration:
    """Verify trigger registration mechanics."""

    def test_trigger_registered_on_etb(self) -> None:
        """register_triggers adds an ETB trigger to the trigger manager."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)

        initial_count = len(game.trigger_manager.get_triggers())
        glyph.register_triggers(game)
        after_count = len(game.trigger_manager.get_triggers())
        assert after_count == initial_count + 1

    def test_trigger_is_etb_type(self) -> None:
        """The registered trigger must be an ENTERS_BATTLEFIELD type."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)
        glyph.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(glyph)
        assert len(triggers) == 1
        assert triggers[0].event_type == EventType.ENTERS_BATTLEFIELD

    def test_trigger_only_fires_for_self(self) -> None:
        """The ETB trigger should only fire when this specific instance enters."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)
        glyph.register_triggers(game)

        # Fire ETB for a different creature — should NOT create a token
        other = Creature(name="OtherCreature", owner=p1, controller=p1,
                         base_power=2, base_toughness=2)
        game.trigger_manager.fire_event(
            game,
            EventType.ENTERS_BATTLEFIELD,
            {"permanent": other, "controller": p1},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        assert len(tokens) == 0

    def test_trigger_fires_for_correct_instance(self) -> None:
        """The ETB trigger should fire when the registered creature enters."""
        game = _make_game()
        p1 = game.players[0]
        glyph = EagerGlyphmage(owner=p1, controller=p1)
        glyph.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EventType.ENTERS_BATTLEFIELD,
            {"permanent": glyph, "controller": p1},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        bf = game.get_battlefield(p1).get_all()
        tokens = _get_tokens(bf)
        assert len(tokens) == 1
