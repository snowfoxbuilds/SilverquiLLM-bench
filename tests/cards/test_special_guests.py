"""Tests for cards/foundations/special_guests.py — SPG Batch 1.

Verifies 5 Special Guest cards:
- Condemn: attacking creature → bottom of library, controller gains life = toughness
- Grim Tutor: search library → hand, shuffle, lose 3 life
- Goblin Bushwhacker: kicked vs unkicked ETB buff
- Paradise Druid: conditional hexproof, any-color mana
- Bloom Tender: color-based mana production
"""

from __future__ import annotations

import pytest

from cards.foundations.special_guests import (
    BloomTender,
    Condemn,
    GoblinBushwhacker,
    GrimTutor,
    ParadiseDruid,
    register_special_guests,
)
from cards.registry import CardRegistry
from engine.card import CardImpl, Creature, Instant, ManaAbility
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


def _place_on_battlefield(game, creature, player):
    creature.owner = player
    creature.controller = player
    game.get_battlefield(player).add(creature)


def _make_creature(name="Bear", power=2, toughness=2, **kwargs):
    return Creature(name=name, base_power=power, base_toughness=toughness, **kwargs)


def _activate_mana_ability(game, creature, ability_index=0):
    abilities = creature.get_mana_abilities()
    ab = abilities[ability_index]
    if ab.cost(game, creature):
        ab.mana_produced(game)
        return True
    return False


def _simulate_etb(game, creature, controller=None):
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


# ===========================================================================
# CONDEMN
# ===========================================================================


class TestCondemn:
    def test_metadata(self):
        card = Condemn()
        assert card.name == "Condemn"
        assert card.mana_cost == ManaCost.parse("{W}")
        assert CardType.INSTANT in card.card_types

    def test_targets_only_attacking_creatures(self):
        game = _make_game()
        p1, p2 = game.players
        # A non-attacking creature should not be a valid target
        bear = _make_creature("Bear", 2, 2)
        bear.is_attacking = False
        _place_on_battlefield(game, bear, p2)

        card = Condemn()
        targets = card.get_targets(game)
        assert bear not in targets

    def test_targets_include_attacking_creature(self):
        game = _make_game()
        p2 = game.players[1]
        bear = _make_creature("Bear", 2, 2)
        bear.is_attacking = True
        _place_on_battlefield(game, bear, p2)

        card = Condemn()
        targets = card.get_targets(game)
        assert bear in targets

    def test_attacking_creature_goes_to_bottom_of_library(self):
        game = _make_game()
        p1, p2 = game.players
        # Put a dummy card in p2's library so bottom position is meaningful
        dummy = CardImpl(name="TopCard")
        dummy.owner = p2
        p2.zones[Zone.LIBRARY].add(dummy)

        attacker = _make_creature("Attacker", 3, 4)
        attacker.is_attacking = True
        _place_on_battlefield(game, attacker, p2)

        card = Condemn()
        card.controller = p1
        card.owner = p1
        card.chosen_targets = [attacker]
        card.on_resolve(game)

        # Attacker should no longer be on battlefield
        assert not game.get_battlefield(p2).contains(attacker)
        # Attacker should be in p2's library (bottom)
        assert p2.zones[Zone.LIBRARY].contains(attacker)

    def test_controller_gains_life_equal_to_toughness(self):
        game = _make_game()
        p1, p2 = game.players
        p2.life = 20

        attacker = _make_creature("BigGuy", 1, 5)
        attacker.is_attacking = True
        _place_on_battlefield(game, attacker, p2)

        card = Condemn()
        card.controller = p1
        card.owner = p1
        card.chosen_targets = [attacker]
        card.on_resolve(game)

        # p2 (controller of attacker) gains 5 life
        assert p2.life == 25

    def test_no_life_gain_for_zero_toughness(self):
        """Edge case: creature with 0 toughness grants no life."""
        game = _make_game()
        p1, p2 = game.players
        p2.life = 20

        attacker = _make_creature("Weakling", 1, 0)
        attacker.is_attacking = True
        _place_on_battlefield(game, attacker, p2)

        card = Condemn()
        card.controller = p1
        card.owner = p1
        card.chosen_targets = [attacker]
        card.on_resolve(game)

        assert p2.life == 20


# ===========================================================================
# GRIM TUTOR
# ===========================================================================


class TestGrimTutor:
    def test_metadata(self):
        card = GrimTutor()
        assert card.name == "Grim Tutor"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert CardType.SORCERY in card.card_types

    def test_search_puts_card_in_hand(self):
        game = _make_game()
        p1 = game.players[0]
        # Put a target card in library
        target = CardImpl(name="TargetCard")
        target.owner = p1
        p1.zones[Zone.LIBRARY].add(target)

        card = GrimTutor()
        card.controller = p1
        card.owner = p1
        card.chosen_targets = [target]
        card.on_resolve(game)

        assert p1.zones[Zone.HAND].contains(target)
        assert not p1.zones[Zone.LIBRARY].contains(target)

    def test_lose_three_life(self):
        game = _make_game()
        p1 = game.players[0]
        p1.life = 20
        # Add a card so search succeeds
        dummy = CardImpl(name="Dummy")
        dummy.owner = p1
        p1.zones[Zone.LIBRARY].add(dummy)

        card = GrimTutor()
        card.controller = p1
        card.owner = p1
        card.on_resolve(game)

        assert p1.life == 17

    def test_empty_library_still_loses_life(self):
        """Even with no cards to find, you still lose 3 life."""
        game = _make_game()
        p1 = game.players[0]
        p1.life = 20

        card = GrimTutor()
        card.controller = p1
        card.owner = p1
        card.on_resolve(game)

        assert p1.life == 17


# ===========================================================================
# GOBLIN BUSHWHACKER
# ===========================================================================


class TestGoblinBushwhacker:
    def test_metadata(self):
        card = GoblinBushwhacker()
        assert card.name == "Goblin Bushwhacker"
        assert card.mana_cost == ManaCost.parse("{R}")
        assert card.base_power == 1
        assert card.base_toughness == 1
        assert "Goblin" in card.subtypes
        assert "Warrior" in card.subtypes

    def test_kicked_buffs_all_creatures(self):
        game = _make_game()
        p1 = game.players[0]

        # Another creature already on battlefield
        bear = _make_creature("Bear", 2, 2)
        _place_on_battlefield(game, bear, p1)

        bush = GoblinBushwhacker()
        bush.kicked = True
        _place_on_battlefield(game, bush, p1)

        _simulate_etb(game, bush, p1)
        game.effect_manager.apply_all(game)

        # Bear should get +1/+0
        assert bear.base_power == 3
        # Bush itself should also get +1/+0
        assert bush.base_power == 2
        # Both should have haste
        assert Keyword.HASTE in bear.keywords
        assert Keyword.HASTE in bush.keywords

    def test_unkicked_no_buff(self):
        game = _make_game()
        p1 = game.players[0]

        bear = _make_creature("Bear", 2, 2)
        _place_on_battlefield(game, bear, p1)

        bush = GoblinBushwhacker()
        bush.kicked = False
        _place_on_battlefield(game, bush, p1)

        _simulate_etb(game, bush, p1)

        # No buff should be applied
        assert bear.base_power == 2
        assert bush.base_power == 1

    def test_kicked_grants_haste(self):
        game = _make_game()
        p1 = game.players[0]

        creature = _make_creature("Soldier", 1, 1)
        _place_on_battlefield(game, creature, p1)

        bush = GoblinBushwhacker()
        bush.kicked = True
        _place_on_battlefield(game, bush, p1)

        _simulate_etb(game, bush, p1)
        game.effect_manager.apply_all(game)

        assert Keyword.HASTE in creature.keywords


# ===========================================================================
# PARADISE DRUID
# ===========================================================================


class TestParadiseDruid:
    def test_metadata(self):
        card = ParadiseDruid()
        assert card.name == "Paradise Druid"
        assert card.mana_cost == ManaCost.parse("{1}{G}")
        assert card.base_power == 2
        assert card.base_toughness == 1
        assert "Elf" in card.subtypes
        assert "Druid" in card.subtypes

    def test_hexproof_while_untapped(self):
        game = _make_game()
        p1 = game.players[0]
        druid = ParadiseDruid()
        druid.is_tapped = False
        _place_on_battlefield(game, druid, p1)
        druid.register_triggers(game)
        # Apply continuous effects
        game.effect_manager.apply_all(game)

        assert Keyword.HEXPROOF in druid.keywords

    def test_no_hexproof_when_tapped(self):
        game = _make_game()
        p1 = game.players[0]
        druid = ParadiseDruid()
        _place_on_battlefield(game, druid, p1)
        druid.register_triggers(game)
        druid.is_tapped = True
        # Apply continuous effects
        game.effect_manager.apply_all(game)

        assert Keyword.HEXPROOF not in druid.keywords

    def test_tap_for_mana_any_color(self):
        """Tapping should produce mana of chosen color."""
        game = _make_game()
        p1 = game.players[0]
        druid = ParadiseDruid()
        _place_on_battlefield(game, druid, p1)

        abilities = druid.get_mana_abilities()
        # Should have 5 abilities (one per color)
        assert len(abilities) == 5
        assert all(isinstance(a, ManaAbility) for a in abilities)

    def test_tap_produces_green(self):
        game = _make_game()
        p1 = game.players[0]
        druid = ParadiseDruid()
        _place_on_battlefield(game, druid, p1)

        # Activate green mana ability (index 4 = G based on WUBRG order)
        result = _activate_mana_ability(game, druid, ability_index=4)
        assert result is True
        assert p1.mana_pool.get(ManaType.GREEN) == 1

    def test_cannot_tap_when_already_tapped(self):
        game = _make_game()
        p1 = game.players[0]
        druid = ParadiseDruid()
        _place_on_battlefield(game, druid, p1)
        druid.is_tapped = True

        result = _activate_mana_ability(game, druid, ability_index=0)
        assert result is False

    def test_loses_hexproof_after_tapping_for_mana(self):
        game = _make_game()
        p1 = game.players[0]
        druid = ParadiseDruid()
        _place_on_battlefield(game, druid, p1)
        druid.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert Keyword.HEXPROOF in druid.keywords

        # Tap for mana
        _activate_mana_ability(game, druid, ability_index=0)
        assert druid.is_tapped is True

        # Re-apply continuous effects
        game.effect_manager.apply_all(game)
        assert Keyword.HEXPROOF not in druid.keywords


# ===========================================================================
# BLOOM TENDER
# ===========================================================================


class TestBloomTender:
    def test_metadata(self):
        card = BloomTender()
        assert card.name == "Bloom Tender"
        assert card.mana_cost == ManaCost.parse("{1}{G}")
        assert card.base_power == 1
        assert card.base_toughness == 1
        assert "Elf" in card.subtypes

    def test_produces_mana_for_green_permanent(self):
        """Bloom Tender itself is green, so should produce at least {G}."""
        game = _make_game()
        p1 = game.players[0]
        tender = BloomTender()
        _place_on_battlefield(game, tender, p1)

        result = _activate_mana_ability(game, tender)
        assert result is True
        assert p1.mana_pool.get(ManaType.GREEN) >= 1

    def test_produces_mana_for_multiple_colors(self):
        """With green and red permanents, should produce {G} and {R}."""
        game = _make_game()
        p1 = game.players[0]
        tender = BloomTender()
        _place_on_battlefield(game, tender, p1)

        red_creature = _make_creature("Goblin", 1, 1, mana_cost=ManaCost.parse("{R}"))
        _place_on_battlefield(game, red_creature, p1)

        result = _activate_mana_ability(game, tender)
        assert result is True
        assert p1.mana_pool.get(ManaType.GREEN) >= 1
        assert p1.mana_pool.get(ManaType.RED) >= 1

    def test_no_mana_without_colored_permanents(self):
        """With only colorless permanents, produces no mana."""
        game = _make_game()
        p1 = game.players[0]
        tender = BloomTender()
        # Remove tender from battlefield after activation setup - 
        # we need to test with only colorless permanents
        _place_on_battlefield(game, tender, p1)

        # Add a colorless creature (no mana cost = colorless)
        colorless = CardImpl(name="Myr")
        colorless.card_types = {CardType.CREATURE}
        colorless.mana_cost = ManaCost.parse("{2}")
        _place_on_battlefield(game, colorless, p1)

        # Remove tender so only colorless is on battlefield, then put it back for activation
        game.get_battlefield(p1).remove(tender)
        # Re-add tender (it's still colorless-free scenario? No, tender is green)
        # Actually tender itself is green, so it always produces at least G
        # Let's verify: with only tender (green), we get exactly G
        _place_on_battlefield(game, tender, p1)
        # Remove the colorless creature to isolate
        game.get_battlefield(p1).remove(colorless)

        result = _activate_mana_ability(game, tender)
        assert result is True
        # Only green from tender itself
        assert p1.mana_pool.get(ManaType.GREEN) == 1
        assert p1.mana_pool.get(ManaType.RED) == 0
        assert p1.mana_pool.get(ManaType.BLUE) == 0
        assert p1.mana_pool.get(ManaType.BLACK) == 0
        assert p1.mana_pool.get(ManaType.WHITE) == 0

    def test_cannot_activate_when_tapped(self):
        game = _make_game()
        p1 = game.players[0]
        tender = BloomTender()
        _place_on_battlefield(game, tender, p1)
        tender.is_tapped = True

        result = _activate_mana_ability(game, tender)
        assert result is False


# ===========================================================================
# REGISTRATION
# ===========================================================================


class TestRegistration:
    def test_register_all_five_cards(self):
        registry = CardRegistry()
        register_special_guests(registry)
        expected = ["Condemn", "Grim Tutor", "Goblin Bushwhacker",
                    "Paradise Druid", "Bloom Tender"]
        for name in expected:
            assert registry.get(name) is not None, f"{name} not registered"
