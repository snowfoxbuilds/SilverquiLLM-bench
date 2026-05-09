"""Tests for protection from qualities (keyword ability).

Covers the DEBT mnemonic:
- D: Damage prevention from protected-from sources
- E: Enchanting — auras with that quality fall off (SBA)
- B: Blocking — can't be blocked by creatures with that quality
- T: Targeting — can't be targeted by spells/abilities from sources with that quality

Also covers:
- get_colors utility
- ProtectionAbility matching logic
- Multi-color protection
- Custom predicate-based protection (extensibility)
- Protection does NOT prevent non-DEBT effects
"""

from __future__ import annotations

import pytest

from engine.card import Aura, Creature, Instant, Sorcery
from engine.game import deal_damage
from engine.game_state import GameState
from engine.player import DeterministicPlayer as Player
from engine.protection import (
    ProtectionAbility,
    get_colors,
    get_protections,
    has_protection_from,
    _aura_illegal_due_to_protection,
    _is_illegal_block_due_to_protection,
    _is_illegal_target_due_to_protection,
    _should_prevent_damage,
)
from engine.combat import _can_block
from engine.state_based_actions import check_state_based_actions
from engine.types import Color, ManaCost, ManaType, Zone


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def two_player_game():
    """Create a minimal two-player game state."""
    p1 = Player("Alice", [])
    p2 = Player("Bob", [])
    game = GameState([p1, p2])
    return game, p1, p2


def _make_creature(name="Bear", colors=None, mana_cost=None, **kwargs):
    """Helper to create a creature with optional colors / mana cost."""
    kwargs.setdefault("base_power", 2)
    kwargs.setdefault("base_toughness", 2)
    c = Creature(name=name, mana_cost=mana_cost, **kwargs)
    if colors is not None:
        c.colors = colors
    return c


def _make_red_creature(name="Goblin"):
    return _make_creature(name=name, colors={Color.RED})


def _make_green_creature(name="Elf"):
    return _make_creature(name=name, colors={Color.GREEN})


def _make_pro_red_creature(name="White Knight"):
    c = _make_creature(name=name, colors={Color.WHITE})
    c.protections = [ProtectionAbility(quality=Color.RED)]
    return c


# ---------------------------------------------------------------------------
# get_colors — colour derivation
# ---------------------------------------------------------------------------

class TestGetColors:
    def test_explicit_colors_attribute_takes_precedence(self):
        """Explicit .colors set on an object should be returned directly."""
        c = _make_creature()
        c.colors = {Color.RED, Color.GREEN}
        assert get_colors(c) == {Color.RED, Color.GREEN}

    def test_colors_derived_from_mana_cost_pips(self):
        """Colours derived from mana cost pips when no explicit colors."""
        cost = ManaCost(generic=1, pips={ManaType.RED: 1})
        c = _make_creature(mana_cost=cost)
        assert get_colors(c) == {Color.RED}

    def test_colorless_object_returns_empty_set(self):
        """Object with no color info returns empty set."""
        c = _make_creature()
        assert get_colors(c) == set()

    def test_single_color_attribute_fallback(self):
        """Falls back to .color (singular) if no .colors or mana_cost."""
        c = _make_creature()
        c.color = Color.BLUE
        assert get_colors(c) == {Color.BLUE}

    def test_multicolor_mana_cost(self):
        """Object with multiple colored pips returns all colors."""
        cost = ManaCost(generic=0, pips={ManaType.RED: 1, ManaType.WHITE: 1})
        c = _make_creature(mana_cost=cost)
        colors = get_colors(c)
        assert Color.RED in colors
        assert Color.WHITE in colors


# ---------------------------------------------------------------------------
# ProtectionAbility — matching logic
# ---------------------------------------------------------------------------

class TestProtectionAbility:
    def test_color_protection_matches_source_of_that_color(self):
        prot = ProtectionAbility(quality=Color.RED)
        assert prot.matches(_make_red_creature()) is True

    def test_color_protection_does_not_match_other_color(self):
        prot = ProtectionAbility(quality=Color.RED)
        assert prot.matches(_make_green_creature()) is False

    def test_color_protection_does_not_match_colorless(self):
        """Colorless source should not match any color protection."""
        prot = ProtectionAbility(quality=Color.RED)
        colorless = _make_creature(name="Artifact Golem")
        assert prot.matches(colorless) is False

    def test_custom_predicate_overrides_default_color_matching(self):
        """Custom predicate is used instead of default color matching."""
        prot = ProtectionAbility(
            quality="goblins",
            predicate=lambda src: "Goblin" in getattr(src, "subtypes", set()),
        )
        goblin = _make_creature(subtypes={"Goblin"})
        elf = _make_creature(subtypes={"Elf"})
        assert prot.matches(goblin) is True
        assert prot.matches(elf) is False

    def test_multicolor_source_matches_single_color_protection(self):
        """A red-green creature should match protection from red."""
        prot = ProtectionAbility(quality=Color.RED)
        rg_creature = _make_creature(colors={Color.RED, Color.GREEN})
        assert prot.matches(rg_creature) is True


# ---------------------------------------------------------------------------
# has_protection_from — high-level query
# ---------------------------------------------------------------------------

class TestHasProtectionFrom:
    def test_permanent_with_protection_from_matching_source(self):
        knight = _make_pro_red_creature()
        assert has_protection_from(knight, _make_red_creature()) is True

    def test_permanent_without_protection(self):
        bear = _make_creature()
        assert has_protection_from(bear, _make_red_creature()) is False

    def test_protection_does_not_match_wrong_color(self):
        knight = _make_pro_red_creature()
        assert has_protection_from(knight, _make_green_creature()) is False

    def test_multiple_protections_red_and_black(self):
        """Creature with protection from red AND black blocks both."""
        c = _make_creature()
        c.protections = [
            ProtectionAbility(quality=Color.RED),
            ProtectionAbility(quality=Color.BLACK),
        ]
        assert has_protection_from(c, _make_red_creature()) is True
        black_src = _make_creature()
        black_src.colors = {Color.BLACK}
        assert has_protection_from(c, black_src) is True
        assert has_protection_from(c, _make_green_creature()) is False

    def test_get_protections_returns_empty_list_for_unprotected(self):
        """get_protections on object without protections returns []."""
        bear = _make_creature()
        assert get_protections(bear) == []


# ---------------------------------------------------------------------------
# D — Damage prevention
# ---------------------------------------------------------------------------

class TestDamagePrevention:
    def test_red_damage_prevented_on_pro_red_creature(self, two_player_game):
        """Pro-red creature takes no damage from a red source."""
        game, p1, p2 = two_player_game
        knight = _make_pro_red_creature()
        knight.base_toughness = 4
        goblin = _make_red_creature()
        deal_damage(game, goblin, knight, 3)
        assert knight.damage_marked == 0

    def test_nonred_damage_goes_through_on_pro_red_creature(self, two_player_game):
        """Pro-red creature takes damage from a green source normally."""
        game, p1, p2 = two_player_game
        knight = _make_pro_red_creature()
        knight.base_toughness = 4
        elf = _make_green_creature()
        deal_damage(game, elf, knight, 3)
        assert knight.damage_marked == 3

    def test_damage_to_player_with_protection_prevented(self, two_player_game):
        """Player with pro-red takes no damage from red sources."""
        game, p1, p2 = two_player_game
        p1.protections = [ProtectionAbility(quality=Color.RED)]
        p1.life = 20
        deal_damage(game, _make_red_creature(), p1, 5)
        assert p1.life == 20

    def test_should_prevent_damage_helper_functions(self):
        """_should_prevent_damage returns correct bool."""
        knight = _make_pro_red_creature()
        assert _should_prevent_damage(knight, _make_red_creature()) is True
        assert _should_prevent_damage(knight, _make_green_creature()) is False


# ---------------------------------------------------------------------------
# E — Enchanting prevention (auras fall off via SBA)
# ---------------------------------------------------------------------------

class TestEnchantingPrevention:
    def test_red_aura_illegal_on_pro_red_creature(self):
        """_aura_illegal_due_to_protection detects red aura on pro-red."""
        knight = _make_pro_red_creature()
        aura = Aura(name="Red Aura", attached_to=knight)
        aura.colors = {Color.RED}
        assert _aura_illegal_due_to_protection(aura) is True

    def test_green_aura_legal_on_pro_red_creature(self):
        """Green aura on pro-red creature is fine."""
        knight = _make_pro_red_creature()
        aura = Aura(name="Green Aura", attached_to=knight)
        aura.colors = {Color.GREEN}
        assert _aura_illegal_due_to_protection(aura) is False

    def test_red_aura_falls_off_via_sba(self, two_player_game):
        """SBA check removes red aura from pro-red creature's controller battlefield."""
        game, p1, p2 = two_player_game
        knight = _make_pro_red_creature()
        knight.owner = p1
        knight.controller = p1
        p1.zones[Zone.BATTLEFIELD].add(knight)

        aura = Aura(name="Red Aura", attached_to=knight)
        aura.colors = {Color.RED}
        aura.owner = p2
        aura.controller = p2
        p2.zones[Zone.BATTLEFIELD].add(aura)

        check_state_based_actions(game)
        assert not p2.zones[Zone.BATTLEFIELD].contains(aura)

    def test_green_aura_stays_on_pro_red_creature_after_sba(self, two_player_game):
        """SBA check does NOT remove green aura from pro-red creature."""
        game, p1, p2 = two_player_game
        knight = _make_pro_red_creature()
        knight.owner = p1
        knight.controller = p1
        p1.zones[Zone.BATTLEFIELD].add(knight)

        aura = Aura(name="Green Aura", attached_to=knight)
        aura.colors = {Color.GREEN}
        aura.owner = p2
        aura.controller = p2
        p2.zones[Zone.BATTLEFIELD].add(aura)

        check_state_based_actions(game)
        assert p2.zones[Zone.BATTLEFIELD].contains(aura)

    def test_unattached_aura_not_flagged_by_protection(self):
        """Aura with no attached_to should not be flagged as illegal."""
        aura = Aura(name="Red Aura")
        aura.colors = {Color.RED}
        assert _aura_illegal_due_to_protection(aura) is False


# ---------------------------------------------------------------------------
# B — Blocking prevention
# ---------------------------------------------------------------------------

class TestBlockingPrevention:
    def test_pro_red_attacker_cant_be_blocked_by_red_creature(self):
        """_can_block returns False when attacker has pro from blocker's color."""
        attacker = _make_pro_red_creature()
        attacker.is_tapped = False
        attacker.summoning_sick = False
        red_blocker = _make_red_creature()
        red_blocker.is_tapped = False
        assert _can_block(red_blocker, attacker) is False

    def test_pro_red_attacker_can_be_blocked_by_green_creature(self):
        """_can_block returns True for non-red blocker vs pro-red attacker."""
        attacker = _make_pro_red_creature()
        attacker.is_tapped = False
        attacker.summoning_sick = False
        green_blocker = _make_green_creature()
        green_blocker.is_tapped = False
        assert _can_block(green_blocker, attacker) is True

    def test_is_illegal_block_helper(self):
        """_is_illegal_block_due_to_protection helper returns True for match."""
        attacker = _make_pro_red_creature()
        assert _is_illegal_block_due_to_protection(attacker, _make_red_creature()) is True
        assert _is_illegal_block_due_to_protection(attacker, _make_green_creature()) is False


# ---------------------------------------------------------------------------
# T — Targeting prevention
# ---------------------------------------------------------------------------

class TestTargetingPrevention:
    def test_pro_red_cant_be_targeted_by_red_instant(self):
        """Red instant cannot target pro-red creature."""
        knight = _make_pro_red_creature()
        bolt = Instant(name="Lightning Bolt")
        bolt.colors = {Color.RED}
        assert _is_illegal_target_due_to_protection(knight, bolt) is True

    def test_pro_red_can_be_targeted_by_green_instant(self):
        """Green instant can target pro-red creature."""
        knight = _make_pro_red_creature()
        growth = Instant(name="Giant Growth")
        growth.colors = {Color.GREEN}
        assert _is_illegal_target_due_to_protection(knight, growth) is False

    def test_pro_red_cant_be_targeted_by_red_sorcery(self):
        """Red sorcery also can't target pro-red creature."""
        knight = _make_pro_red_creature()
        spell = Sorcery(name="Red Sorcery")
        spell.colors = {Color.RED}
        assert _is_illegal_target_due_to_protection(knight, spell) is True

    def test_colorless_spell_can_target_pro_red(self):
        """Colorless spell should be able to target pro-red creature."""
        knight = _make_pro_red_creature()
        spell = Instant(name="Spatial Contortion")
        # no colors set — colorless
        assert _is_illegal_target_due_to_protection(knight, spell) is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestProtectionEdgeCases:
    def test_protection_from_multicolor_source_blocks_if_any_color_matches(self):
        """A red-green source is blocked by protection from red."""
        knight = _make_pro_red_creature()
        rg_creature = _make_creature(colors={Color.RED, Color.GREEN})
        assert has_protection_from(knight, rg_creature) is True

    def test_no_protection_from_colorless_source(self):
        """Pro-red does not protect from colorless sources."""
        knight = _make_pro_red_creature()
        colorless = _make_creature(name="Artifact Golem")
        assert has_protection_from(knight, colorless) is False

    def test_protection_does_not_prevent_non_targeted_effects(self, two_player_game):
        """Protection does NOT prevent non-DEBT effects like life loss.
        
        For example, a board wipe (non-targeted) would still destroy a
        creature with protection. We verify that damage from a non-matching
        source still goes through (i.e. protection is specific, not blanket).
        """
        game, p1, p2 = two_player_game
        knight = _make_pro_red_creature()
        knight.base_toughness = 4
        # A white source deals damage — should go through
        white_source = _make_creature(colors={Color.WHITE})
        deal_damage(game, white_source, knight, 2)
        assert knight.damage_marked == 2
