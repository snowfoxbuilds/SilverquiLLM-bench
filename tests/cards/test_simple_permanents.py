"""Tests for cards/fdn/_legacy/simple_permanents.py — Simple enchantments and artifacts.

All 5 permanents are from the MTG Foundations (FDN) set with Scryfall-verified data.

Verifies:
- Each permanent has the correct name, mana_cost, card types, and base class.
- **Pacifism**: attaches to creature, prevents attacking/blocking through the
  combat system (_can_attack/_can_block enforcement), continuous effect registration.
- **Pacifism aura removal**: when Pacifism leaves the battlefield, its restrictions
  no longer apply and the creature can attack and block again.
- **Untamed Hunger**: attaches to creature, gives +2/+1 (layer 7c) and menace (layer 6).
- **Unflinching Courage**: +2/+2 (layer 7c), trample and lifelink (layer 6).
- **Hedron Archive**: mana rock, tap ability adds 2 colorless mana.
- **Goblin Oriflamme**: non-aura enchantment, attacking creatures get +1/+0 (layer 7c).
- **Aura attachment**: auras attach to target on resolution via chosen_targets.
- **SBA**: aura goes to graveyard if attached creature dies/leaves battlefield.
- **Registry**: register_simple_permanents() registers all 5 correctly.
- **Metadata**: oracle_text, rarity, type_line accuracy.
"""

from __future__ import annotations

import pytest

from cards.fdn._legacy.simple_permanents import (
    GoblinOriflamme,
    HedronArchive,
    Pacifism,
    UntamedHunger,
    UnflinchingCourage,
    register_simple_permanents,
)
from cards.registry import CardRegistry
from engine.card import Artifact, Aura, Creature, Enchantment
from engine.combat import _can_attack, _can_block
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
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
# Permanent attribute verification — parameterized tests
# ---------------------------------------------------------------------------

_PERMANENT_ATTRS = [
    # (class, name, cost_str, expected_card_type, base_class, is_aura)
    (Pacifism, "Pacifism", "{1}{W}", CardType.ENCHANTMENT, Aura, True),
    (UntamedHunger, "Untamed Hunger", "{2}{B}", CardType.ENCHANTMENT, Aura, True),
    (UnflinchingCourage, "Unflinching Courage", "{1}{G}{W}", CardType.ENCHANTMENT, Aura, True),
    (HedronArchive, "Hedron Archive", "{4}", CardType.ARTIFACT, Artifact, False),
    (GoblinOriflamme, "Goblin Oriflamme", "{1}{R}", CardType.ENCHANTMENT, Enchantment, False),
]


class TestPermanentAttributes:
    """Verify each permanent has the correct name, mana cost, card type, and base class."""

    @pytest.mark.parametrize(
        "cls,expected_name,cost_str,expected_type,base_class,is_aura",
        _PERMANENT_ATTRS,
        ids=[s[1] for s in _PERMANENT_ATTRS],
    )
    def test_permanent_attributes(
        self, cls, expected_name, cost_str, expected_type, base_class, is_aura
    ) -> None:
        perm = cls()
        assert perm.name == expected_name
        assert perm.mana_cost == ManaCost.parse(cost_str)
        assert expected_type in perm.card_types
        assert isinstance(perm, base_class)
        assert getattr(perm, "is_aura", False) == is_aura

    @pytest.mark.parametrize(
        "cls,expected_name",
        [(Pacifism, "Pacifism"), (UntamedHunger, "Untamed Hunger"),
         (UnflinchingCourage, "Unflinching Courage")],
        ids=["Pacifism", "Untamed Hunger", "Unflinching Courage"],
    )
    def test_aura_subtype(self, cls, expected_name) -> None:
        """Auras should have 'Aura' in their subtypes."""
        perm = cls()
        assert "Aura" in perm.subtypes


# ---------------------------------------------------------------------------
# Pacifism — can't attack or block (layer 6)
# ---------------------------------------------------------------------------

class TestPacifism:
    """Pacifism aura debuff — prevents the enchanted creature from attacking or blocking."""

    def test_pacifism_attaches_to_creature_on_resolve(self) -> None:
        """Pacifism.on_resolve sets attached_to to the target creature."""
        game = _make_game()
        p1, p2 = game.players

        creature = _make_creature(owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])

        pacifism = Pacifism(owner=p1, controller=p1)
        pacifism.chosen_targets = [creature]
        p1.zones[Zone.BATTLEFIELD].add(pacifism)
        pacifism.on_resolve(game)

        assert pacifism.attached_to is creature

    def test_pacifism_prevents_creature_from_attacking(self) -> None:
        """After Pacifism resolves and effects are applied, the creature cannot
        be declared as an attacker (combat system enforces the restriction)."""
        game = _make_game()
        p1, p2 = game.players

        creature = _make_creature(owner=p2, controller=p2)
        creature.summoning_sick = False
        set_board_state(game, 1, battlefield=[creature])

        pacifism = Pacifism(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[pacifism])
        pacifism.chosen_targets = [creature]
        pacifism.on_resolve(game)

        # Apply continuous effects
        game.effect_manager.apply_all(game)

        # The creature should be ineligible to attack per the combat system
        assert _can_attack(creature) is False

    def test_pacifism_prevents_creature_from_blocking(self) -> None:
        """After Pacifism resolves and effects are applied, the creature cannot
        be declared as a blocker (combat system enforces the restriction)."""
        game = _make_game()
        p1, p2 = game.players

        creature = _make_creature(owner=p2, controller=p2)
        creature.summoning_sick = False
        set_board_state(game, 1, battlefield=[creature])

        pacifism = Pacifism(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[pacifism])
        pacifism.chosen_targets = [creature]
        pacifism.on_resolve(game)

        game.effect_manager.apply_all(game)

        # Create a dummy attacker to test blocking against
        dummy_attacker = _make_creature(name="Dummy", owner=p1, controller=p1)
        assert _can_block(creature, dummy_attacker) is False

    def test_pacifism_can_cast_requires_creature(self) -> None:
        """Pacifism.can_cast returns False when no creatures on battlefield."""
        game = _make_game()
        pacifism = Pacifism()
        # No creatures on battlefield
        assert pacifism.can_cast(game) is False

    def test_pacifism_can_cast_with_creature(self) -> None:
        """Pacifism.can_cast returns True when a creature exists on battlefield."""
        game = _make_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[creature])
        pacifism = Pacifism()
        assert pacifism.can_cast(game) is True

    def test_pacifism_effect_removed_when_aura_leaves_battlefield(self) -> None:
        """When Pacifism leaves the battlefield, its restrictions should no longer
        apply — the creature should be able to attack and block again."""
        game = _make_game()
        p1, p2 = game.players

        creature = _make_creature(owner=p2, controller=p2)
        creature.summoning_sick = False
        set_board_state(game, 1, battlefield=[creature])

        pacifism = Pacifism(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[pacifism])
        pacifism.chosen_targets = [creature]
        pacifism.on_resolve(game)

        # Apply effects — creature should be restricted
        game.effect_manager.apply_all(game)
        assert _can_attack(creature) is False, "Creature should not be able to attack with Pacifism"

        # Remove Pacifism from the battlefield (simulating destruction)
        p1.zones[Zone.BATTLEFIELD].remove(pacifism)
        p1.zones[Zone.GRAVEYARD].add(pacifism)

        # Re-apply effects — the aura's apply function checks _is_on_battlefield
        # and should no-op since Pacifism is gone; reset clears the flags
        game.effect_manager.apply_all(game)

        # The creature should now be able to attack and block
        assert _can_attack(creature) is True, "Creature should be able to attack after Pacifism removed"

        dummy_attacker = _make_creature(name="Dummy", owner=p1, controller=p1)
        assert _can_block(creature, dummy_attacker) is True, "Creature should be able to block after Pacifism removed"


# ---------------------------------------------------------------------------
# Untamed Hunger — +2/+1 and menace (layer 7c / layer 6)
# ---------------------------------------------------------------------------

class TestUntamedHunger:
    """Untamed Hunger aura buff — gives +2/+1 and menace."""

    def test_untamed_hunger_gives_plus_2_1(self) -> None:
        """Enchanted creature gets +2/+1 after effects are applied."""
        game = _make_game()
        p1 = game.players[0]

        creature = _make_creature(owner=p1, controller=p1, power=2, toughness=3)
        set_board_state(game, 0, battlefield=[creature])

        aura = UntamedHunger(owner=p1, controller=p1)
        p1.zones[Zone.BATTLEFIELD].add(aura)
        aura.chosen_targets = [creature]
        aura.on_resolve(game)

        game.effect_manager.apply_all(game)

        assert creature.power == 4   # 2 + 2
        assert creature.toughness == 4  # 3 + 1

    def test_untamed_hunger_grants_menace(self) -> None:
        """Enchanted creature gains the menace keyword after effects are applied."""
        game = _make_game()
        p1 = game.players[0]

        creature = _make_creature(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[creature])

        aura = UntamedHunger(owner=p1, controller=p1)
        p1.zones[Zone.BATTLEFIELD].add(aura)
        aura.chosen_targets = [creature]
        aura.on_resolve(game)

        game.effect_manager.apply_all(game)

        assert Keyword.MENACE & creature.keywords

    def test_untamed_hunger_attaches_correctly(self) -> None:
        """Untamed Hunger sets attached_to on resolution."""
        game = _make_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[creature])

        aura = UntamedHunger(owner=p1, controller=p1)
        p1.zones[Zone.BATTLEFIELD].add(aura)
        aura.chosen_targets = [creature]
        aura.on_resolve(game)

        assert aura.attached_to is creature


# ---------------------------------------------------------------------------
# Unflinching Courage — +2/+2, trample, lifelink (layer 7c / layer 6)
# ---------------------------------------------------------------------------

class TestUnflinchingCourage:
    """Unflinching Courage aura buff — gives +2/+2, trample, and lifelink."""

    def test_unflinching_courage_gives_plus_2_2(self) -> None:
        """Enchanted creature gets +2/+2 after effects are applied."""
        game = _make_game()
        p1 = game.players[0]

        creature = _make_creature(owner=p1, controller=p1, power=1, toughness=1)
        set_board_state(game, 0, battlefield=[creature])

        aura = UnflinchingCourage(owner=p1, controller=p1)
        p1.zones[Zone.BATTLEFIELD].add(aura)
        aura.chosen_targets = [creature]
        aura.on_resolve(game)

        game.effect_manager.apply_all(game)

        assert creature.power == 3   # 1 + 2
        assert creature.toughness == 3  # 1 + 2

    def test_unflinching_courage_grants_trample_and_lifelink(self) -> None:
        """Enchanted creature gains trample and lifelink."""
        game = _make_game()
        p1 = game.players[0]

        creature = _make_creature(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[creature])

        aura = UnflinchingCourage(owner=p1, controller=p1)
        p1.zones[Zone.BATTLEFIELD].add(aura)
        aura.chosen_targets = [creature]
        aura.on_resolve(game)

        game.effect_manager.apply_all(game)

        assert Keyword.TRAMPLE & creature.keywords
        assert Keyword.LIFELINK & creature.keywords

    def test_unflinching_courage_attaches_correctly(self) -> None:
        """Unflinching Courage sets attached_to on resolution."""
        game = _make_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[creature])

        aura = UnflinchingCourage(owner=p1, controller=p1)
        p1.zones[Zone.BATTLEFIELD].add(aura)
        aura.chosen_targets = [creature]
        aura.on_resolve(game)

        assert aura.attached_to is creature


# ---------------------------------------------------------------------------
# Hedron Archive — mana rock, {T}: Add {C}{C}
# ---------------------------------------------------------------------------

class TestHedronArchive:
    """Hedron Archive mana rock — tap to add 2 colorless mana."""

    def test_hedron_archive_is_artifact(self) -> None:
        """Hedron Archive should be an Artifact with the ARTIFACT card type."""
        ha = HedronArchive()
        assert isinstance(ha, Artifact)
        assert CardType.ARTIFACT in ha.card_types

    def test_hedron_archive_mana_ability_adds_2_colorless(self) -> None:
        """Tapping Hedron Archive should add 2 colorless mana to controller's pool."""
        game = _make_game()
        p1 = game.players[0]

        ha = HedronArchive(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ha])

        mana_abilities = ha.get_mana_abilities()
        assert len(mana_abilities) >= 1

        ability = mana_abilities[0]
        # Pay the tap cost
        cost_paid = ability.cost(game, ha)
        assert cost_paid is True
        assert ha.is_tapped is True

        # Produce the mana
        ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) >= 2

    def test_hedron_archive_cant_tap_when_already_tapped(self) -> None:
        """Hedron Archive mana ability can't be activated when already tapped."""
        game = _make_game()
        p1 = game.players[0]

        ha = HedronArchive(owner=p1, controller=p1)
        ha.is_tapped = True
        set_board_state(game, 0, battlefield=[ha])

        mana_abilities = ha.get_mana_abilities()
        ability = mana_abilities[0]
        cost_paid = ability.cost(game, ha)
        assert cost_paid is False

    def test_hedron_archive_activated_ability_adds_mana(self) -> None:
        """Hedron Archive also exposes the mana ability via get_activated_abilities."""
        game = _make_game()
        p1 = game.players[0]

        ha = HedronArchive(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ha])

        abilities = ha.get_activated_abilities()
        assert len(abilities) >= 1
        ability = abilities[0]
        assert ability.is_mana_ability is True

        # Activate: pay cost then apply effect
        assert ability.cost(game, ha) is True
        ability.effect(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) >= 2


# ---------------------------------------------------------------------------
# Goblin Oriflamme — attacking creatures +1/+0 (layer 7c)
# ---------------------------------------------------------------------------

class TestGoblinOriflamme:
    """Goblin Oriflamme — non-aura enchantment, attacking creatures get +1/+0."""

    def test_goblin_oriflamme_is_non_aura_enchantment(self) -> None:
        """Goblin Oriflamme should be an Enchantment but NOT an Aura."""
        go = GoblinOriflamme()
        assert isinstance(go, Enchantment)
        assert CardType.ENCHANTMENT in go.card_types
        assert getattr(go, "is_aura", True) is False

    def test_goblin_oriflamme_buffs_attacking_creature(self) -> None:
        """An attacking creature controlled by Oriflamme's controller gets +1/+0."""
        game = _make_game()
        p1 = game.players[0]

        creature = _make_creature(owner=p1, controller=p1, power=2, toughness=2)
        creature.is_attacking = True
        set_board_state(game, 0, battlefield=[creature])

        oriflamme = GoblinOriflamme(owner=p1, controller=p1)
        p1.zones[Zone.BATTLEFIELD].add(oriflamme)
        oriflamme.on_resolve(game)

        game.effect_manager.apply_all(game)

        assert creature.power == 3   # 2 + 1
        assert creature.toughness == 2  # unchanged

    def test_goblin_oriflamme_does_not_buff_non_attacking(self) -> None:
        """A non-attacking creature should not get the +1/+0 bonus."""
        game = _make_game()
        p1 = game.players[0]

        creature = _make_creature(owner=p1, controller=p1, power=2, toughness=2)
        creature.is_attacking = False
        set_board_state(game, 0, battlefield=[creature])

        oriflamme = GoblinOriflamme(owner=p1, controller=p1)
        p1.zones[Zone.BATTLEFIELD].add(oriflamme)
        oriflamme.on_resolve(game)

        game.effect_manager.apply_all(game)

        assert creature.power == 2  # no bonus
        assert creature.toughness == 2

    def test_goblin_oriflamme_does_not_buff_opponent_attacker(self) -> None:
        """An attacking creature controlled by the opponent should NOT get the bonus."""
        game = _make_game()
        p1, p2 = game.players

        enemy_creature = _make_creature(owner=p2, controller=p2, power=3, toughness=3)
        enemy_creature.is_attacking = True
        set_board_state(game, 1, battlefield=[enemy_creature])

        oriflamme = GoblinOriflamme(owner=p1, controller=p1)
        p1.zones[Zone.BATTLEFIELD].add(oriflamme)
        oriflamme.on_resolve(game)

        game.effect_manager.apply_all(game)

        assert enemy_creature.power == 3  # no bonus from opponent's Oriflamme


# ---------------------------------------------------------------------------
# Aura attachment and SBA — aura falls off when creature leaves
# ---------------------------------------------------------------------------

class TestAuraSBA:
    """Test that SBAs correctly move auras to graveyard when their target leaves."""

    def test_aura_goes_to_graveyard_when_creature_removed(self) -> None:
        """When the attached creature is removed from battlefield, SBAs should
        move the aura to its owner's graveyard."""
        game = _make_game()
        p1, p2 = game.players

        creature = _make_creature(owner=p2, controller=p2, power=2, toughness=2)
        set_board_state(game, 1, battlefield=[creature])

        pacifism = Pacifism(owner=p1, controller=p1)
        p1.zones[Zone.BATTLEFIELD].add(pacifism)
        pacifism.chosen_targets = [creature]
        pacifism.on_resolve(game)

        assert pacifism.attached_to is creature

        # Remove the creature from the battlefield
        p2.zones[Zone.BATTLEFIELD].remove(creature)
        p2.zones[Zone.GRAVEYARD].add(creature)

        # Run SBAs — aura should go to graveyard
        resolve_state_based_actions(game)

        assert not p1.zones[Zone.BATTLEFIELD].contains(pacifism)
        assert p1.zones[Zone.GRAVEYARD].contains(pacifism)

    def test_aura_with_none_attached_goes_to_graveyard(self) -> None:
        """An aura on the battlefield with attached_to=None should be moved to graveyard by SBAs."""
        game = _make_game()
        p1 = game.players[0]

        pacifism = Pacifism(owner=p1, controller=p1)
        pacifism.attached_to = None
        p1.zones[Zone.BATTLEFIELD].add(pacifism)

        resolve_state_based_actions(game)

        assert not p1.zones[Zone.BATTLEFIELD].contains(pacifism)
        assert p1.zones[Zone.GRAVEYARD].contains(pacifism)

    def test_non_aura_enchantment_survives_sba(self) -> None:
        """Goblin Oriflamme (non-aura enchantment) should NOT be removed by aura SBAs."""
        game = _make_game()
        p1 = game.players[0]

        oriflamme = GoblinOriflamme(owner=p1, controller=p1)
        p1.zones[Zone.BATTLEFIELD].add(oriflamme)
        oriflamme.on_resolve(game)

        resolve_state_based_actions(game)

        # Non-aura enchantment should still be on battlefield
        assert p1.zones[Zone.BATTLEFIELD].contains(oriflamme)


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

class TestRegisterSimplePermanents:
    """Verify register_simple_permanents registers all 5 FDN permanents."""

    def test_registers_all_five(self) -> None:
        registry = CardRegistry()
        register_simple_permanents(registry)
        assert len(registry) == 5

    def test_registered_names(self) -> None:
        registry = CardRegistry()
        register_simple_permanents(registry)
        expected_names = {
            "Pacifism", "Untamed Hunger", "Unflinching Courage",
            "Hedron Archive", "Goblin Oriflamme",
        }
        assert set(registry.list_all()) == expected_names

    def test_create_instance_produces_correct_types(self) -> None:
        """Registry instances should be of the correct card subclass."""
        registry = CardRegistry()
        register_simple_permanents(registry)
        player = DeterministicPlayer("TestPlayer", [])

        # Auras
        for name in ["Pacifism", "Untamed Hunger", "Unflinching Courage"]:
            instance = registry.create_instance(name, owner=player)
            assert isinstance(instance, Aura), f"{name} should be an Aura"

        # Artifact
        instance = registry.create_instance("Hedron Archive", owner=player)
        assert isinstance(instance, Artifact), "Hedron Archive should be Artifact"

        # Non-aura enchantment
        instance = registry.create_instance("Goblin Oriflamme", owner=player)
        assert isinstance(instance, Enchantment), "Goblin Oriflamme should be Enchantment"
        assert not isinstance(instance, Aura), "Goblin Oriflamme should not be Aura"

    def test_registry_metadata_set_code_is_fdn(self) -> None:
        """All permanents should be registered with set_code 'fdn'."""
        registry = CardRegistry()
        register_simple_permanents(registry)
        for name in registry.list_all():
            _cls, meta = registry.get(name)
            assert meta.set_code == "fdn", f"{name} set_code should be 'fdn'"

    def test_registry_metadata_type_line_auras(self) -> None:
        """Aura type lines should include 'Enchantment — Aura'."""
        registry = CardRegistry()
        register_simple_permanents(registry)
        for name in ["Pacifism", "Untamed Hunger", "Unflinching Courage"]:
            _cls, meta = registry.get(name)
            assert "Enchantment" in meta.type_line
            assert "Aura" in meta.type_line

    def test_registry_metadata_hedron_archive(self) -> None:
        """Hedron Archive metadata should have correct type and oracle text."""
        registry = CardRegistry()
        register_simple_permanents(registry)
        _cls, meta = registry.get("Hedron Archive")
        assert meta.type_line == "Artifact"
        assert "{T}: Add {C}{C}" in meta.oracle_text
        assert meta.colors == []  # colorless

    def test_registry_metadata_rarity(self) -> None:
        """Spot-check rarity for a common and an uncommon permanent."""
        registry = CardRegistry()
        register_simple_permanents(registry)
        _cls, meta_common = registry.get("Pacifism")
        assert meta_common.rarity == "common"
        _cls, meta_uncommon = registry.get("Hedron Archive")
        assert meta_uncommon.rarity == "uncommon"

    def test_registry_metadata_oracle_text_pacifism(self) -> None:
        """Pacifism oracle text should mention can't attack or block."""
        registry = CardRegistry()
        register_simple_permanents(registry)
        _cls, meta = registry.get("Pacifism")
        assert "can't attack or block" in meta.oracle_text

    def test_registry_metadata_goblin_oriflamme(self) -> None:
        """Goblin Oriflamme metadata should have correct type and oracle text."""
        registry = CardRegistry()
        register_simple_permanents(registry)
        _cls, meta = registry.get("Goblin Oriflamme")
        assert meta.type_line == "Enchantment"
        assert "+1/+0" in meta.oracle_text
        assert meta.colors == ["R"]
