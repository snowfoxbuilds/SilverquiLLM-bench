"""Tests for cards/fdn/_legacy/simple_spells.py — Simple instants and sorceries.

All 10 spells are from the MTG Foundations (FDN) set with Scryfall-verified data.

Verifies:
- Each spell has the correct name, mana_cost, card types (Instant vs Sorcery), colors.
- Burst Lightning: deals 2 damage to a creature and to a player (via cast_spell pipeline).
- Incinerating Blast: deals 6 damage to target creature (via cast_spell pipeline).
- Giant Growth: gives +3/+3 until end of turn (continuous effect, layer 7c).
- Quick Study: controller draws 2 cards.
- Hero's Downfall: destroys target creature or planeswalker (goes to graveyard).
- Negate: counters a noncreature spell; can_cast blocks empty stack and creature spells.
- Cancel: counters any spell on the stack; can_cast blocks empty stack.
- Disenchant: destroys target artifact or enchantment.
- Pilfer: target opponent reveals hand, controller chooses nonland card to discard.
- Cemetery Recruitment: returns a creature card from graveyard to hand; can_cast blocks empty graveyard.
- register_simple_spells() registers all 10 in the registry.
- Registry metadata accuracy (oracle_text, rarity, type_line, set_code).
"""

from __future__ import annotations

import pytest

from cards.fdn._legacy.simple_spells import (
    BurstLightning,
    Cancel,
    CemeteryRecruitment,
    Disenchant,
    GiantGrowth,
    HerosDownfall,
    IncineratingBlast,
    Negate,
    Pilfer,
    QuickStudy,
    register_simple_spells,
)
from cards.registry import CardRegistry
from engine.card import Artifact, Creature, Enchantment, Instant, Sorcery
from engine.casting import CastingError
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from tests.test_utils import cast_spell, create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(
    *,
    phase: Phase = Phase.PRECOMBAT_MAIN,
) -> GameState:
    """Create a minimal 2-player GameState at the specified phase."""
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    game = GameState([p1, p2])
    game.phase = phase
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0
    return game


def _make_creature(
    name: str = "Test Creature",
    power: int = 2,
    toughness: int = 3,
    owner: DeterministicPlayer | None = None,
    controller: DeterministicPlayer | None = None,
) -> Creature:
    """Create a minimal creature for testing."""
    return Creature(
        name=name,
        base_power=power,
        base_toughness=toughness,
        owner=owner,
        controller=controller,
    )


# ---------------------------------------------------------------------------
# Spell attribute verification — parameterized
# ---------------------------------------------------------------------------

_SPELL_ATTRS = [
    # (class, name, cost_str, card_type, base_class)
    (BurstLightning, "Burst Lightning", "{R}", CardType.INSTANT, Instant),
    (IncineratingBlast, "Incinerating Blast", "{4}{R}", CardType.SORCERY, Sorcery),
    (GiantGrowth, "Giant Growth", "{G}", CardType.INSTANT, Instant),
    (QuickStudy, "Quick Study", "{2}{U}", CardType.INSTANT, Instant),
    (HerosDownfall, "Hero's Downfall", "{1}{B}{B}", CardType.INSTANT, Instant),
    (Negate, "Negate", "{1}{U}", CardType.INSTANT, Instant),
    (Cancel, "Cancel", "{1}{U}{U}", CardType.INSTANT, Instant),
    (Disenchant, "Disenchant", "{1}{W}", CardType.INSTANT, Instant),
    (Pilfer, "Pilfer", "{1}{B}", CardType.SORCERY, Sorcery),
    (CemeteryRecruitment, "Cemetery Recruitment", "{1}{B}", CardType.SORCERY, Sorcery),
]


class TestSpellAttributes:
    """Verify each spell has the correct name, mana cost, card type, and base class."""

    @pytest.mark.parametrize(
        "cls,expected_name,cost_str,expected_type,base_class",
        _SPELL_ATTRS,
        ids=[s[1] for s in _SPELL_ATTRS],
    )
    def test_spell_attributes(
        self, cls, expected_name, cost_str, expected_type, base_class
    ) -> None:
        spell = cls()
        assert spell.name == expected_name
        assert spell.mana_cost == ManaCost.parse(cost_str)
        assert expected_type in spell.card_types
        assert isinstance(spell, base_class)


# ---------------------------------------------------------------------------
# Burst Lightning — 2 damage to any target (via cast_spell pipeline)
# ---------------------------------------------------------------------------

class TestBurstLightning:
    """Burst Lightning deals 2 damage to a creature or a player."""

    def test_burst_lightning_deals_2_to_creature(self) -> None:
        """Cast Burst Lightning targeting a creature; verify 2 damage marked."""
        game = _make_game()
        p1, p2 = game.players

        creature = _make_creature(owner=p2, controller=p2, toughness=5)
        set_board_state(game, 1, battlefield=[creature])

        bolt = BurstLightning(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[bolt], mana={ManaType.RED: 1})

        cast_spell(game, 0, "Burst Lightning", targets=[creature])

        assert creature.damage_marked == 2

    def test_burst_lightning_deals_2_to_player(self) -> None:
        """Cast Burst Lightning targeting the opponent; verify 2 life lost."""
        game = _make_game()
        p1, p2 = game.players

        bolt = BurstLightning(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[bolt], mana={ManaType.RED: 1})

        cast_spell(game, 0, "Burst Lightning", targets=[p2])

        assert p2.life == 18  # 20 - 2


# ---------------------------------------------------------------------------
# Incinerating Blast — 6 damage to target creature (via cast_spell pipeline)
# ---------------------------------------------------------------------------

class TestIncineratingBlast:
    """Incinerating Blast deals 6 damage to target creature."""

    def test_incinerating_blast_deals_6_to_creature(self) -> None:
        """Cast Incinerating Blast targeting a creature; verify 6 damage marked."""
        game = _make_game()
        p1, p2 = game.players

        creature = _make_creature(name="Big Creature", owner=p2, controller=p2,
                                  power=4, toughness=7)
        set_board_state(game, 1, battlefield=[creature])

        blast = IncineratingBlast(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[blast], mana={ManaType.RED: 1, ManaType.COLORLESS: 4})

        cast_spell(game, 0, "Incinerating Blast", targets=[creature])

        assert creature.damage_marked == 6


# ---------------------------------------------------------------------------
# Giant Growth — +3/+3 until end of turn (via cast_spell pipeline)
# ---------------------------------------------------------------------------

class TestGiantGrowth:
    """Giant Growth gives +3/+3 until end of turn via continuous effect."""

    def test_giant_growth_adds_3_3(self) -> None:
        """Cast Giant Growth on a 2/2 creature; verify P/T becomes 5/5."""
        game = _make_game()
        p1 = game.players[0]

        creature = _make_creature(owner=p1, controller=p1, power=2, toughness=2)
        set_board_state(game, 0, battlefield=[creature])

        spell = GiantGrowth(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.GREEN: 1})

        cast_spell(game, 0, "Giant Growth", targets=[creature])

        # After resolution, the effect is registered; apply it
        game.effect_manager.apply_all(game)

        assert creature.power == 5  # 2 + 3
        assert creature.toughness == 5  # 2 + 3

    def test_giant_growth_wears_off_at_cleanup(self) -> None:
        """After cleanup (remove_expired), the +3/+3 buff is gone."""
        game = _make_game()
        p1 = game.players[0]

        creature = _make_creature(owner=p1, controller=p1, power=2, toughness=2)
        set_board_state(game, 0, battlefield=[creature])

        spell = GiantGrowth(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.GREEN: 1})

        cast_spell(game, 0, "Giant Growth", targets=[creature])

        game.effect_manager.apply_all(game)
        assert creature.power == 5

        # Simulate cleanup — remove expired effects and reapply
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert creature.power == 2  # Back to original
        assert creature.toughness == 2


# ---------------------------------------------------------------------------
# Quick Study — draw 2 cards (via cast_spell pipeline)
# ---------------------------------------------------------------------------

class TestQuickStudy:
    """Quick Study draws 2 cards for the controller."""

    def test_quick_study_draws_two_cards(self) -> None:
        """Cast Quick Study; verify controller's hand grows by 2."""
        game = _make_game()
        p1 = game.players[0]

        # Put 3 cards in library for drawing
        lib_cards = []
        for i in range(3):
            card = Creature(name=f"Library Card {i}", owner=p1, controller=p1)
            lib_cards.append(card)

        spell = QuickStudy(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 1, ManaType.COLORLESS: 2})

        # Add library cards (set_board_state doesn't have a library param)
        for c in lib_cards:
            p1.zones[Zone.LIBRARY].add(c)

        initial_hand_size = 1  # Just the spell card itself — but it will be cast
        initial_lib_size = len(p1.zones[Zone.LIBRARY].get_all())

        cast_spell(game, 0, "Quick Study")

        # After casting, spell left hand, then 2 cards drawn from library
        assert len(p1.zones[Zone.HAND].get_all()) == 2
        assert len(p1.zones[Zone.LIBRARY].get_all()) == initial_lib_size - 2


# ---------------------------------------------------------------------------
# Hero's Downfall — destroy target creature or planeswalker
# ---------------------------------------------------------------------------

class TestHerosDownfall:
    """Hero's Downfall destroys target creature, moving it to graveyard."""

    def test_heros_downfall_destroys_creature(self) -> None:
        """Cast Hero's Downfall targeting a creature; creature ends up in graveyard."""
        game = _make_game()
        p1, p2 = game.players

        creature = _make_creature(name="Victim", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])

        spell = HerosDownfall(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLACK: 2, ManaType.COLORLESS: 1})

        cast_spell(game, 0, "Hero's Downfall", targets=[creature])

        # Creature should be off the battlefield
        assert not p2.zones[Zone.BATTLEFIELD].contains(creature)
        # Creature should be in owner's graveyard
        assert p2.zones[Zone.GRAVEYARD].contains(creature)


# ---------------------------------------------------------------------------
# Negate — counter target noncreature spell
# ---------------------------------------------------------------------------

class TestNegate:
    """Negate counters noncreature spells; cannot counter creature spells."""

    def test_negate_get_targets_includes_noncreature_on_stack(self) -> None:
        """Negate should find noncreature spells on the stack as valid targets."""
        from engine.stack import StackObject

        game = _make_game()
        p1, p2 = game.players

        # Put a sorcery (noncreature) on the stack
        sorcery = Sorcery(name="Some Sorcery", owner=p2, controller=p2)
        stack_obj = StackObject(source=sorcery, controller=p2)
        game.stack.push(stack_obj)

        negate = Negate(owner=p1, controller=p1)
        targets = negate.get_targets(game)

        assert len(targets) >= 1  # Has a target requirement
        # The filter should accept the stack object
        assert targets[0].filter_fn(stack_obj) is True

    def test_negate_get_targets_excludes_creature_spell(self) -> None:
        """Negate should not find creature spells as valid targets."""
        from engine.stack import StackObject

        game = _make_game()
        p1, p2 = game.players

        creature = Creature(name="Some Creature", owner=p2, controller=p2)
        stack_obj = StackObject(source=creature, controller=p2)
        game.stack.push(stack_obj)

        negate = Negate(owner=p1, controller=p1)
        targets = negate.get_targets(game)

        # Should have no valid targets (or filter rejects the creature spell)
        if targets:
            assert targets[0].filter_fn(stack_obj) is False
        else:
            assert targets == []

    def test_negate_can_cast_blocks_empty_stack(self) -> None:
        """Negate's can_cast returns False when the stack is empty."""
        game = _make_game()
        p1 = game.players[0]

        negate = Negate(owner=p1, controller=p1)
        assert negate.can_cast(game) is False

    def test_negate_can_cast_blocks_creature_spell_only(self) -> None:
        """Negate's can_cast returns False when only creature spells on stack."""
        from engine.stack import StackObject

        game = _make_game()
        p1, p2 = game.players

        creature = Creature(name="Bear", owner=p2, controller=p2)
        stack_obj = StackObject(source=creature, controller=p2)
        game.stack.push(stack_obj)

        negate = Negate(owner=p1, controller=p1)
        assert negate.can_cast(game) is False


# ---------------------------------------------------------------------------
# Cancel — counter target spell
# ---------------------------------------------------------------------------

class TestCancel:
    """Cancel counters any spell on the stack."""

    def test_cancel_get_targets_includes_any_spell(self) -> None:
        """Cancel should find any spell on the stack (creature or noncreature)."""
        from engine.stack import StackObject

        game = _make_game()
        p1, p2 = game.players

        creature = Creature(name="Some Creature", owner=p2, controller=p2)
        stack_obj = StackObject(source=creature, controller=p2)
        game.stack.push(stack_obj)

        cancel = Cancel(owner=p1, controller=p1)
        targets = cancel.get_targets(game)

        assert len(targets) >= 1
        assert targets[0].filter_fn(stack_obj) is True

    def test_cancel_counters_spell_to_graveyard(self) -> None:
        """When Cancel counters a spell, the spell's card goes to its owner's graveyard."""
        from engine.stack import StackObject

        game = _make_game()
        p1, p2 = game.players

        # Put a sorcery on the stack
        sorcery = Sorcery(name="Target Sorcery", owner=p2, controller=p2)
        p2.zones[Zone.STACK].add(sorcery)
        stack_obj = StackObject(source=sorcery, controller=p2)
        game.stack.push(stack_obj)

        cancel = Cancel(owner=p1, controller=p1)
        cancel.chosen_targets = [stack_obj]
        cancel.on_resolve(game)

        # The sorcery should be in p2's graveyard
        assert p2.zones[Zone.GRAVEYARD].contains(sorcery)
        # The stack object should be removed from the stack
        for remaining in game.stack.objects():
            assert remaining is not stack_obj

    def test_cancel_can_cast_blocks_empty_stack(self) -> None:
        """Cancel's can_cast returns False when the stack is empty."""
        game = _make_game()
        p1 = game.players[0]

        cancel = Cancel(owner=p1, controller=p1)
        assert cancel.can_cast(game) is False


# ---------------------------------------------------------------------------
# Disenchant — destroy target artifact or enchantment
# ---------------------------------------------------------------------------

class TestDisenchant:
    """Disenchant destroys target artifact or enchantment."""

    def test_disenchant_destroys_artifact(self) -> None:
        """Cast Disenchant targeting an artifact; artifact goes to graveyard."""
        game = _make_game()
        p1, p2 = game.players

        artifact = Artifact(name="Test Artifact", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[artifact])

        spell = Disenchant(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1})

        cast_spell(game, 0, "Disenchant", targets=[artifact])

        assert not p2.zones[Zone.BATTLEFIELD].contains(artifact)
        assert p2.zones[Zone.GRAVEYARD].contains(artifact)

    def test_disenchant_destroys_enchantment(self) -> None:
        """Cast Disenchant targeting an enchantment; enchantment goes to graveyard."""
        game = _make_game()
        p1, p2 = game.players

        enchantment = Enchantment(name="Test Enchantment", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[enchantment])

        spell = Disenchant(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1})

        cast_spell(game, 0, "Disenchant", targets=[enchantment])

        assert not p2.zones[Zone.BATTLEFIELD].contains(enchantment)
        assert p2.zones[Zone.GRAVEYARD].contains(enchantment)


# ---------------------------------------------------------------------------
# Pilfer — target opponent reveals hand; you choose nonland card to discard
# ---------------------------------------------------------------------------

class TestPilfer:
    """Pilfer forces opponent to discard a nonland card chosen by controller."""

    def test_pilfer_discards_nonland_from_opponent(self) -> None:
        """Cast Pilfer targeting opponent; controller chooses a nonland card."""
        game = _make_game()
        p1, p2 = game.players

        # Give p2 a nonland card in hand
        victim_card = Creature(name="Hand Creature", owner=p2, controller=p2)
        p2.zones[Zone.HAND].add(victim_card)

        spell = Pilfer(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1})

        # Script p1 to choose victim_card when asked what to discard from p2
        p1._script.append(victim_card)

        cast_spell(game, 0, "Pilfer", targets=[p2])

        assert not p2.zones[Zone.HAND].contains(victim_card)
        assert p2.zones[Zone.GRAVEYARD].contains(victim_card)


# ---------------------------------------------------------------------------
# Cemetery Recruitment — return creature from graveyard to hand
# ---------------------------------------------------------------------------

class TestCemeteryRecruitment:
    """Cemetery Recruitment returns a creature card from graveyard to hand."""

    def test_cemetery_recruitment_returns_creature_to_hand(self) -> None:
        """Cast Cemetery Recruitment; creature moves from graveyard to hand."""
        game = _make_game()
        p1 = game.players[0]

        dead = _make_creature(name="Dead Creature", owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(dead)

        spell = CemeteryRecruitment(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1})

        cast_spell(game, 0, "Cemetery Recruitment", targets=[dead])

        assert p1.zones[Zone.HAND].contains(dead)
        assert not p1.zones[Zone.GRAVEYARD].contains(dead)

    def test_cemetery_recruitment_can_cast_blocks_empty_graveyard(self) -> None:
        """can_cast returns False when controller has no creature cards in graveyard."""
        game = _make_game()
        p1 = game.players[0]

        spell = CemeteryRecruitment(owner=p1, controller=p1)
        assert spell.can_cast(game) is False


# ---------------------------------------------------------------------------
# register_simple_spells — registration
# ---------------------------------------------------------------------------

_EXPECTED_NAMES = {
    "Burst Lightning",
    "Incinerating Blast",
    "Giant Growth",
    "Quick Study",
    "Hero's Downfall",
    "Negate",
    "Cancel",
    "Disenchant",
    "Pilfer",
    "Cemetery Recruitment",
}


class TestRegisterSimpleSpells:
    """Verify register_simple_spells registers all 10 spells in the registry."""

    def test_registers_all_ten(self) -> None:
        registry = CardRegistry()
        register_simple_spells(registry)
        assert len(registry) == 10

    def test_registered_names(self) -> None:
        registry = CardRegistry()
        register_simple_spells(registry)
        assert set(registry.list_all()) == _EXPECTED_NAMES

    def test_create_instance_produces_correct_type(self) -> None:
        """Registry create_instance should produce the correct subclass."""
        registry = CardRegistry()
        register_simple_spells(registry)
        player = DeterministicPlayer("TestPlayer", [])

        bolt = registry.create_instance("Burst Lightning", owner=player)
        assert isinstance(bolt, BurstLightning)
        assert isinstance(bolt, Instant)

        blast = registry.create_instance("Incinerating Blast", owner=player)
        assert isinstance(blast, IncineratingBlast)
        assert isinstance(blast, Sorcery)


# ---------------------------------------------------------------------------
# Registry metadata accuracy
# ---------------------------------------------------------------------------

_EXPECTED_METADATA = [
    # (name, type_line, rarity, oracle_text_substr)
    ("Burst Lightning", "Instant", "common", "2 damage"),
    ("Incinerating Blast", "Sorcery", "common", "6 damage"),
    ("Giant Growth", "Instant", "common", "+3/+3"),
    ("Quick Study", "Instant", "common", "Draw two"),
    ("Hero's Downfall", "Instant", "uncommon", "Destroy target creature"),
    ("Negate", "Instant", "common", "noncreature"),
    ("Cancel", "Instant", "common", "Counter target spell"),
    ("Disenchant", "Instant", "common", "artifact or enchantment"),
    ("Pilfer", "Sorcery", "common", "nonland"),
    ("Cemetery Recruitment", "Sorcery", "common", "graveyard"),
]


class TestRegistryMetadata:
    """Verify registry metadata (type_line, rarity, oracle_text) is accurate."""

    @pytest.mark.parametrize(
        "name,expected_type_line,expected_rarity,oracle_substr",
        _EXPECTED_METADATA,
        ids=[m[0] for m in _EXPECTED_METADATA],
    )
    def test_metadata_accuracy(
        self, name, expected_type_line, expected_rarity, oracle_substr
    ) -> None:
        registry = CardRegistry()
        register_simple_spells(registry)
        _cls, meta = registry.get(name)

        assert meta.type_line == expected_type_line
        assert meta.rarity == expected_rarity
        assert oracle_substr.lower() in meta.oracle_text.lower()
        assert meta.set_code == "fdn"

    def test_all_spells_have_no_power_toughness(self) -> None:
        """Non-creature spells should have None for power and toughness."""
        registry = CardRegistry()
        register_simple_spells(registry)
        for name in _EXPECTED_NAMES:
            _cls, meta = registry.get(name)
            assert meta.power is None, f"{name} should have power=None"
            assert meta.toughness is None, f"{name} should have toughness=None"
