"""Tests for cards/foundations/special_guests.py — SPG Batch 2.

Verifies 5 complex Special Guest cards:
- Sphinx's Tutelage: draw trigger mills, repeat on shared color, stop on mismatch, activated ability
- Embercleave: cost reduction, flash, ETB attach, double strike + trample
- Akroma's Memorial: 6 keywords + 2 protection colors
- Temporal Manipulation: extra turn granted
- Fiend Artisan: P/T tracks graveyard, activated ability, sorcery-speed restriction
"""

from __future__ import annotations

import pytest

from cards.foundations.special_guests import (
    AkromasMemorial,
    Embercleave,
    FiendArtisan,
    SphinxsTutelage,
    TemporalManipulation,
    register_special_guests,
)
from cards.registry import CardRegistry
from engine.card import CardImpl, Creature
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.triggers import EventType
from engine.types import CardType, Color, Keyword, ManaCost, ManaType, Phase, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(*, phase: Phase = Phase.PRECOMBAT_MAIN) -> GameState:
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    game = GameState([p1, p2])
    game.phase = phase
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0
    return game


def _place_on_battlefield(game, card, player):
    card.owner = player
    card.controller = player
    game.get_battlefield(player).add(card)


def _make_creature(name="Bear", power=2, toughness=2, **kwargs):
    return Creature(name=name, base_power=power, base_toughness=toughness, **kwargs)


def _simulate_etb(game, permanent, controller=None):
    if controller is None:
        controller = getattr(permanent, "controller", game.players[0])
    permanent.register_triggers(game)
    game.trigger_manager.fire_event(
        game,
        EventType.ENTERS_BATTLEFIELD,
        {"permanent": permanent, "controller": controller},
    )
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _add_to_library(player, card):
    card.owner = player
    player.zones[Zone.LIBRARY].add(card)


def _add_to_graveyard(player, card):
    card.owner = player
    card.controller = player
    player.zones[Zone.GRAVEYARD].add(card)


def _fire_event_and_resolve(game, event_type, data):
    """Fire an event and resolve all resulting stack objects."""
    game.trigger_manager.fire_event(game, event_type, data)
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


# ===========================================================================
# SPHINX'S TUTELAGE
# ===========================================================================


class TestSphinxsTutelage:
    def test_metadata(self):
        card = SphinxsTutelage()
        assert card.name == "Sphinx's Tutelage"
        assert card.mana_cost == ManaCost.parse("{2}{U}")
        assert CardType.ENCHANTMENT in card.card_types

    def test_draw_trigger_mills_two(self):
        """Drawing a card should mill 2 from opponent's library."""
        game = _make_game()
        p1, p2 = game.players

        tutelage = SphinxsTutelage()
        _place_on_battlefield(game, tutelage, p1)
        tutelage.register_triggers(game)

        # Put two nonland cards that do NOT share a color in p2's library
        # so the repeat loop stops after first mill
        c1 = CardImpl(name="RedCard")
        c1.card_types = {CardType.CREATURE}
        c1.mana_cost = ManaCost.parse("{R}")
        _add_to_library(p2, c1)

        c2 = CardImpl(name="BlueCard")
        c2.card_types = {CardType.CREATURE}
        c2.mana_cost = ManaCost.parse("{U}")
        _add_to_library(p2, c2)

        initial_gy_count = len(p2.zones[Zone.GRAVEYARD])

        # Fire draw event for p1 and resolve stack
        _fire_event_and_resolve(
            game,
            EventType.DRAWS_CARD,
            {"player": p1, "card": CardImpl(name="dummy")},
        )

        # p2 should have 2 more cards in graveyard
        assert len(p2.zones[Zone.GRAVEYARD]) == initial_gy_count + 2

    def test_repeat_when_milled_share_color(self):
        """Mill repeats when two nonland cards share a color."""
        game = _make_game()
        p1, p2 = game.players

        tutelage = SphinxsTutelage()
        _place_on_battlefield(game, tutelage, p1)
        tutelage.register_triggers(game)

        # Library is a stack (top = last added, milled first).
        # Bottom of library: different colors (stop pair, milled second)
        g1 = CardImpl(name="Green1")
        g1.card_types = {CardType.CREATURE}
        g1.mana_cost = ManaCost.parse("{G}")
        _add_to_library(p2, g1)

        b1 = CardImpl(name="Blue1")
        b1.card_types = {CardType.CREATURE}
        b1.mana_cost = ManaCost.parse("{U}")
        _add_to_library(p2, b1)

        # Top of library: two red cards (share color → repeat, milled first)
        r1 = CardImpl(name="Red1")
        r1.card_types = {CardType.CREATURE}
        r1.mana_cost = ManaCost.parse("{1}{R}")
        _add_to_library(p2, r1)

        r2 = CardImpl(name="Red2")
        r2.card_types = {CardType.CREATURE}
        r2.mana_cost = ManaCost.parse("{R}")
        _add_to_library(p2, r2)

        _fire_event_and_resolve(
            game,
            EventType.DRAWS_CARD,
            {"player": p1, "card": CardImpl(name="dummy")},
        )

        # Should have milled 4 total (2 + repeat 2, then stop)
        assert len(p2.zones[Zone.GRAVEYARD]) == 4

    def test_stop_when_colors_dont_match(self):
        """Mill does NOT repeat when milled cards don't share a color."""
        game = _make_game()
        p1, p2 = game.players

        tutelage = SphinxsTutelage()
        _place_on_battlefield(game, tutelage, p1)
        tutelage.register_triggers(game)

        # Two nonland cards, different colors
        c1 = CardImpl(name="White1")
        c1.card_types = {CardType.CREATURE}
        c1.mana_cost = ManaCost.parse("{W}")
        _add_to_library(p2, c1)

        c2 = CardImpl(name="Black1")
        c2.card_types = {CardType.CREATURE}
        c2.mana_cost = ManaCost.parse("{B}")
        _add_to_library(p2, c2)

        # Extra cards that should NOT be milled
        extra = CardImpl(name="Extra")
        extra.card_types = {CardType.CREATURE}
        extra.mana_cost = ManaCost.parse("{G}")
        _add_to_library(p2, extra)

        _fire_event_and_resolve(
            game,
            EventType.DRAWS_CARD,
            {"player": p1, "card": CardImpl(name="dummy")},
        )

        # Only 2 milled, not 3+
        assert len(p2.zones[Zone.GRAVEYARD]) == 2

    def test_activated_ability_draws_and_discards(self):
        """The {5}{U} ability should draw a card then discard a card."""
        game = _make_game()
        p1 = game.players[0]

        tutelage = SphinxsTutelage()
        _place_on_battlefield(game, tutelage, p1)

        # Put a card in library to draw
        draw_target = CardImpl(name="DrawMe")
        draw_target.owner = p1
        _add_to_library(p1, draw_target)

        # Give mana to pay {5}{U}
        p1.mana_pool.add(ManaType.BLUE, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 5)

        abilities = tutelage.get_activated_abilities()
        assert len(abilities) >= 1
        ab = abilities[0]
        paid = ab.cost(game, tutelage)
        assert paid is True
        ab.effect(game)

        # Should have drawn (card goes to hand) and then discarded (hand → graveyard)
        # Net effect: hand size stays same or decreases, graveyard gains 1
        assert len(p1.zones[Zone.GRAVEYARD]) >= 1


# ===========================================================================
# EMBERCLEAVE
# ===========================================================================


class TestEmbercleave:
    def test_metadata(self):
        card = Embercleave()
        assert card.name == "Embercleave"
        assert card.mana_cost == ManaCost.parse("{4}{R}{R}")
        assert Keyword.FLASH in card.keywords

    def test_cost_reduction_with_attackers(self):
        """Cost reduction = number of attacking creatures."""
        game = _make_game()
        p1 = game.players[0]

        cleave = Embercleave()
        cleave.controller = p1
        cleave.owner = p1

        # 3 attacking creatures
        for i in range(3):
            c = _make_creature(f"Attacker{i}")
            c.is_attacking = True
            _place_on_battlefield(game, c, p1)

        reduction = cleave.cost_reduction(game)
        assert reduction == 3

    def test_cost_reduction_zero_with_no_attackers(self):
        """No attacking creatures → no cost reduction."""
        game = _make_game()
        p1 = game.players[0]

        cleave = Embercleave()
        cleave.controller = p1
        cleave.owner = p1

        # Non-attacking creature
        c = _make_creature("Defender")
        c.is_attacking = False
        _place_on_battlefield(game, c, p1)

        assert cleave.cost_reduction(game) == 0

    def test_etb_attaches_to_creature(self):
        """ETB trigger should attach Embercleave to a creature you control."""
        game = _make_game()
        p1 = game.players[0]

        target = _make_creature("Warrior", 3, 3)
        _place_on_battlefield(game, target, p1)

        cleave = Embercleave()
        _place_on_battlefield(game, cleave, p1)
        _simulate_etb(game, cleave, p1)

        assert cleave.attached_to is target

    def test_equipped_creature_gets_keywords(self):
        """Equipped creature should get +1/+1, double strike, and trample."""
        game = _make_game()
        p1 = game.players[0]

        target = _make_creature("Warrior", 3, 3)
        _place_on_battlefield(game, target, p1)

        cleave = Embercleave()
        _place_on_battlefield(game, cleave, p1)
        _simulate_etb(game, cleave, p1)

        # Apply continuous effects
        game.effect_manager.apply_all(game)

        assert Keyword.DOUBLE_STRIKE in target.keywords
        assert Keyword.TRAMPLE in target.keywords
        # +1/+1 buff
        assert target.base_power >= 4
        assert target.base_toughness >= 4


# ===========================================================================
# AKROMA'S MEMORIAL
# ===========================================================================


class TestAkromasMemorial:
    def test_metadata(self):
        card = AkromasMemorial()
        assert card.name == "Akroma's Memorial"
        assert card.mana_cost == ManaCost.parse("{7}")

    def test_grants_all_six_keywords(self):
        """Should grant flying, first strike, vigilance, trample, haste to creatures."""
        game = _make_game()
        p1 = game.players[0]

        creature = _make_creature("Soldier", 2, 2)
        _place_on_battlefield(game, creature, p1)

        memorial = AkromasMemorial()
        _place_on_battlefield(game, memorial, p1)
        memorial.register_triggers(game)
        game.effect_manager.apply_all(game)

        expected_keywords = [
            Keyword.FLYING,
            Keyword.FIRST_STRIKE,
            Keyword.VIGILANCE,
            Keyword.TRAMPLE,
            Keyword.HASTE,
        ]
        for kw in expected_keywords:
            assert kw in creature.keywords, f"{kw} not granted"

    def test_grants_protection_from_black_and_red(self):
        """Creatures should get protection from black and red."""
        game = _make_game()
        p1 = game.players[0]

        creature = _make_creature("Soldier", 2, 2)
        _place_on_battlefield(game, creature, p1)

        memorial = AkromasMemorial()
        _place_on_battlefield(game, memorial, p1)
        memorial.register_triggers(game)
        game.effect_manager.apply_all(game)

        assert hasattr(creature, "protections")
        qualities = {p.quality for p in creature.protections}
        assert Color.BLACK in qualities
        assert Color.RED in qualities

    def test_does_not_affect_noncreatures(self):
        """Non-creature permanents should not get keywords."""
        game = _make_game()
        p1 = game.players[0]

        artifact = CardImpl(name="SomeArtifact")
        artifact.card_types = {CardType.ARTIFACT}
        artifact.keywords = Keyword(0)
        _place_on_battlefield(game, artifact, p1)

        memorial = AkromasMemorial()
        _place_on_battlefield(game, memorial, p1)
        memorial.register_triggers(game)
        game.effect_manager.apply_all(game)

        assert Keyword.FLYING not in artifact.keywords


# ===========================================================================
# TEMPORAL MANIPULATION
# ===========================================================================


class TestTemporalManipulation:
    def test_metadata(self):
        card = TemporalManipulation()
        assert card.name == "Temporal Manipulation"
        assert card.mana_cost == ManaCost.parse("{3}{U}{U}")
        assert CardType.SORCERY in card.card_types

    def test_grants_extra_turn(self):
        """Resolving should add controller's index to extra_turns queue."""
        game = _make_game()
        p1 = game.players[0]

        card = TemporalManipulation()
        card.controller = p1
        card.owner = p1

        assert len(game.extra_turns) == 0
        card.on_resolve(game)
        assert len(game.extra_turns) == 1
        assert game.extra_turns[0] == 0  # p1 is index 0


# ===========================================================================
# FIEND ARTISAN
# ===========================================================================


class TestFiendArtisan:
    def test_metadata(self):
        card = FiendArtisan()
        assert card.name == "Fiend Artisan"
        assert "Nightmare" in card.subtypes
        assert CardType.CREATURE in card.card_types

    def test_power_toughness_empty_graveyard(self):
        """With no creatures in graveyard, P/T should be 0/0."""
        game = _make_game()
        p1 = game.players[0]
        artisan = FiendArtisan()
        _place_on_battlefield(game, artisan, p1)

        assert artisan.power == 0
        assert artisan.toughness == 0

    def test_power_toughness_tracks_graveyard_creatures(self):
        """P/T should equal number of creature cards in graveyard."""
        game = _make_game()
        p1 = game.players[0]
        artisan = FiendArtisan()
        _place_on_battlefield(game, artisan, p1)

        # Add 3 creature cards to graveyard
        for i in range(3):
            c = _make_creature(f"Dead{i}")
            _add_to_graveyard(p1, c)

        assert artisan.power == 3
        assert artisan.toughness == 3

    def test_noncreature_cards_dont_count(self):
        """Non-creature cards in graveyard shouldn't increase P/T."""
        game = _make_game()
        p1 = game.players[0]
        artisan = FiendArtisan()
        _place_on_battlefield(game, artisan, p1)

        # Add a non-creature to graveyard
        spell = CardImpl(name="Lightning Bolt")
        spell.card_types = {CardType.INSTANT}
        _add_to_graveyard(p1, spell)

        # Add one creature
        c = _make_creature("Dead1")
        _add_to_graveyard(p1, c)

        assert artisan.power == 1
        assert artisan.toughness == 1

    def test_activated_ability_searches_library(self):
        """Activated ability should find a creature with MV ≤ X and put it on battlefield."""
        game = _make_game()
        p1 = game.players[0]

        artisan = FiendArtisan()
        _place_on_battlefield(game, artisan, p1)

        # Need another creature to sacrifice
        sac_target = _make_creature("Sacrifice", 1, 1)
        _place_on_battlefield(game, sac_target, p1)

        # Put a creature in library with MV 2
        search_target = _make_creature("Found", 3, 3, mana_cost=ManaCost.parse("{1}{G}"))
        _add_to_library(p1, search_target)

        # Set X=2, give mana (X generic + 1 B/G)
        artisan._x_value = 2
        artisan._sacrifice_target = sac_target
        p1.mana_pool.add(ManaType.BLACK, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 2)

        abilities = artisan.get_activated_abilities()
        ab = abilities[0]
        paid = ab.cost(game, artisan)
        assert paid is True
        ab.effect(game)

        # search_target should be on battlefield
        assert game.get_battlefield(p1).contains(search_target)

    def test_sorcery_speed_restriction(self):
        """Activated ability cannot be used outside main phase (not sorcery speed)."""
        game = _make_game(phase=Phase.COMBAT)
        p1 = game.players[0]

        artisan = FiendArtisan()
        _place_on_battlefield(game, artisan, p1)

        sac_target = _make_creature("Sacrifice", 1, 1)
        _place_on_battlefield(game, sac_target, p1)

        artisan._x_value = 0
        p1.mana_pool.add(ManaType.BLACK, 1)

        abilities = artisan.get_activated_abilities()
        ab = abilities[0]
        paid = ab.cost(game, artisan)
        assert paid is False


# ===========================================================================
# REGISTRATION
# ===========================================================================


class TestBatch2Registration:
    def test_register_batch2_cards(self):
        registry = CardRegistry()
        register_special_guests(registry)
        expected = [
            "Sphinx's Tutelage",
            "Embercleave",
            "Akroma's Memorial",
            "Temporal Manipulation",
            "Fiend Artisan",
        ]
        for name in expected:
            assert registry.get(name) is not None, f"{name} not registered"
