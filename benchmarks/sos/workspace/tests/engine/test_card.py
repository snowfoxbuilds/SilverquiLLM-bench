"""Tests for engine/card.py — Card base classes and CardImpl interface.

Verifies:
- GameObject auto-incrementing object_id across instances.
- CardImpl field defaults and explicit construction.
- CardImpl hook methods return appropriate defaults (empty lists, None, False, etc.).
- Creature: base_power/base_toughness, computed power/toughness properties,
  damage_marked default, is_tapped default, summoning_sick default, combat flags.
- Creature power/toughness with +1/+1 and -1/-1 counters.
- Instant and Sorcery: construction with correct card types, no extra fields.
- Enchantment: attached_to default None, apply/on_enchant/on_detach methods exist.
- Artifact: construction with ARTIFACT card type.
- ArtifactCreature: has both ARTIFACT and CREATURE card types plus creature features.
- Planeswalker: starting_loyalty, loyalty counter, get_loyalty_abilities.
- Land: can_cast returns False, get_mana_abilities returns a list.
- ManaCost cmc accessed via card's mana_cost attribute.
- Keyword enum flags on creatures.
- Supporting dataclasses: Mode, ActivatedAbility, LoyaltyAbility, ManaAbility,
  ContinuousEffect can be instantiated with expected fields.
"""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.engine.card import (
    ActivatedAbility,
    Artifact,
    ArtifactCreature,
    CardImpl,
    ContinuousEffect,
    Creature,
    Enchantment,
    GameObject,
    Instant,
    Land,
    LoyaltyAbility,
    ManaAbility,
    Mode,
    Planeswalker,
    Sorcery,
)
from benchmarks.sos.workspace.engine.game_state import GameState
from benchmarks.sos.workspace.engine.player import DeterministicPlayer
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, ManaType, Supertype


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_game_object_id() -> None:
    """Reset the GameObject auto-increment counter before each test."""
    GameObject.reset_id_counter()


def _make_player(name: str = "TestPlayer") -> DeterministicPlayer:
    """Create a DeterministicPlayer with an empty script."""
    return DeterministicPlayer(name, script=[])


def _make_game() -> GameState:
    """Create a minimal 2-player GameState for method calls that require it."""
    p1 = DeterministicPlayer("P1", script=["pass"] * 50)
    p2 = DeterministicPlayer("P2", script=["pass"] * 50)
    return GameState([p1, p2])


# ---------------------------------------------------------------------------
# GameObject — auto-incrementing object_id
# ---------------------------------------------------------------------------

class TestGameObject:
    """Verify GameObject auto-incrementing IDs and owner/controller defaults."""

    def test_auto_incrementing_ids(self) -> None:
        """Two GameObjects created in sequence should have different, increasing IDs."""
        a = GameObject()
        b = GameObject()
        assert a.object_id != b.object_id
        assert b.object_id == a.object_id + 1

    def test_first_id_is_one_after_reset(self) -> None:
        """After reset, the first ID should be 1."""
        obj = GameObject()
        assert obj.object_id == 1

    def test_owner_defaults_to_none(self) -> None:
        """Owner should default to None when not provided."""
        obj = GameObject()
        assert obj.owner is None

    def test_controller_defaults_to_owner(self) -> None:
        """Controller should default to owner when not explicitly set."""
        player = _make_player()
        obj = GameObject(owner=player)
        assert obj.controller is player

    def test_controller_can_differ_from_owner(self) -> None:
        """Controller can be set independently from owner."""
        owner = _make_player("Owner")
        ctrl = _make_player("Controller")
        obj = GameObject(owner=owner, controller=ctrl)
        assert obj.owner is owner
        assert obj.controller is ctrl


# ---------------------------------------------------------------------------
# CardImpl — field defaults and construction
# ---------------------------------------------------------------------------

class TestCardImplFields:
    """Verify CardImpl stores fields and applies sensible defaults."""

    def test_name_stored(self) -> None:
        """CardImpl should store the name passed at construction."""
        card = CardImpl(name="Lightning Bolt")
        assert card.name == "Lightning Bolt"

    def test_name_defaults_to_empty_string(self) -> None:
        """CardImpl name defaults to empty string."""
        card = CardImpl()
        assert card.name == ""

    def test_mana_cost_stored(self) -> None:
        """CardImpl should store the ManaCost passed at construction."""
        mc = ManaCost(generic=2, pips={ManaType.RED: 1})
        card = CardImpl(name="Test", mana_cost=mc)
        assert card.mana_cost is mc

    def test_mana_cost_defaults_to_empty_manacost(self) -> None:
        """Default mana_cost should be an empty ManaCost with cmc 0."""
        card = CardImpl()
        assert isinstance(card.mana_cost, ManaCost)
        assert card.mana_cost.cmc == 0

    def test_card_types_stored(self) -> None:
        """Explicitly provided card_types should be stored."""
        card = CardImpl(card_types={CardType.CREATURE, CardType.ARTIFACT})
        assert card.card_types == {CardType.CREATURE, CardType.ARTIFACT}

    def test_card_types_defaults_to_empty_set(self) -> None:
        """Default card_types should be an empty set."""
        card = CardImpl()
        assert card.card_types == set()

    def test_subtypes_stored(self) -> None:
        """Explicitly provided subtypes should be stored."""
        card = CardImpl(subtypes={"Elf", "Warrior"})
        assert card.subtypes == {"Elf", "Warrior"}

    def test_subtypes_defaults_to_empty_set(self) -> None:
        """Default subtypes should be an empty set."""
        card = CardImpl()
        assert card.subtypes == set()

    def test_supertypes_stored(self) -> None:
        """Explicitly provided supertypes should be stored."""
        card = CardImpl(supertypes={Supertype.LEGENDARY})
        assert card.supertypes == {Supertype.LEGENDARY}

    def test_supertypes_defaults_to_empty_set(self) -> None:
        """Default supertypes should be an empty set."""
        card = CardImpl()
        assert card.supertypes == set()

    def test_keywords_stored(self) -> None:
        """Explicitly provided keywords should be stored."""
        kw = Keyword.FLYING | Keyword.TRAMPLE
        card = CardImpl(keywords=kw)
        assert card.keywords == kw

    def test_keywords_defaults_to_empty_flag(self) -> None:
        """Default keywords should be an empty Keyword flag (no keywords)."""
        card = CardImpl()
        assert card.keywords == Keyword(0)
        assert not card.keywords  # falsy

    def test_rules_text_stored(self) -> None:
        """Explicitly provided rules_text should be stored."""
        card = CardImpl(rules_text="Deal 3 damage to any target.")
        assert card.rules_text == "Deal 3 damage to any target."

    def test_rules_text_defaults_to_empty_string(self) -> None:
        """Default rules_text should be an empty string."""
        card = CardImpl()
        assert card.rules_text == ""

    def test_inherits_game_object_id(self) -> None:
        """CardImpl instances should get unique IDs from GameObject."""
        c1 = CardImpl(name="A")
        c2 = CardImpl(name="B")
        assert c1.object_id == 1
        assert c2.object_id == 2

    def test_owner_and_controller_passed_through(self) -> None:
        """Owner and controller should be accessible on CardImpl."""
        p = _make_player()
        card = CardImpl(name="Test", owner=p)
        assert card.owner is p
        assert card.controller is p


# ---------------------------------------------------------------------------
# CardImpl — default hook methods
# ---------------------------------------------------------------------------

class TestCardImplDefaultMethods:
    """Verify that CardImpl hook methods return appropriate defaults."""

    def test_can_cast_returns_true_by_default(self) -> None:
        """Base CardImpl.can_cast should return True."""
        game = _make_game()
        card = CardImpl()
        assert card.can_cast(game) is True

    def test_on_cast_returns_none(self) -> None:
        """on_cast should complete without error and return None."""
        game = _make_game()
        card = CardImpl()
        result = card.on_cast(game)
        assert result is None

    def test_on_resolve_returns_none(self) -> None:
        """on_resolve should complete without error and return None."""
        game = _make_game()
        card = CardImpl()
        result = card.on_resolve(game)
        assert result is None

    def test_get_targets_returns_empty_list(self) -> None:
        """get_targets should return an empty list by default."""
        game = _make_game()
        card = CardImpl()
        assert card.get_targets(game) == []

    def test_register_triggers_returns_none(self) -> None:
        """register_triggers should complete without error."""
        game = _make_game()
        card = CardImpl()
        result = card.register_triggers(game)
        assert result is None

    def test_register_replacement_effects_returns_none(self) -> None:
        """register_replacement_effects should complete without error."""
        game = _make_game()
        card = CardImpl()
        result = card.register_replacement_effects(game)
        assert result is None

    def test_get_activated_abilities_returns_empty_list(self) -> None:
        """get_activated_abilities should return an empty list by default."""
        card = CardImpl()
        assert card.get_activated_abilities() == []

    def test_get_modes_returns_empty_list(self) -> None:
        """get_modes should return an empty list by default."""
        card = CardImpl()
        assert card.get_modes() == []


# ---------------------------------------------------------------------------
# Creature
# ---------------------------------------------------------------------------

class TestCreature:
    """Verify Creature construction, defaults, and properties."""

    def test_base_power_toughness_stored(self) -> None:
        """Creature should store base_power and base_toughness."""
        c = Creature(name="Bear", base_power=2, base_toughness=2)
        assert c.base_power == 2
        assert c.base_toughness == 2

    def test_power_property_equals_base_without_counters(self) -> None:
        """Power property should equal base_power when no counters are present."""
        c = Creature(base_power=3, base_toughness=4)
        assert c.power == 3

    def test_toughness_property_equals_base_without_counters(self) -> None:
        """Toughness property should equal base_toughness when no counters are present."""
        c = Creature(base_power=3, base_toughness=4)
        assert c.toughness == 4

    def test_damage_marked_defaults_to_zero(self) -> None:
        """damage_marked should default to 0."""
        c = Creature()
        assert c.damage_marked == 0

    def test_is_tapped_defaults_to_false(self) -> None:
        """is_tapped should default to False."""
        c = Creature()
        assert c.is_tapped is False

    def test_summoning_sick_defaults_to_true(self) -> None:
        """summoning_sick should default to True (creatures enter with sickness)."""
        c = Creature()
        assert c.summoning_sick is True

    def test_combat_flags_default_to_false(self) -> None:
        """is_attacking and is_blocking should default to False."""
        c = Creature()
        assert c.is_attacking is False
        assert c.is_blocking is False

    def test_card_types_includes_creature(self) -> None:
        """Creature should include CREATURE in card_types by default."""
        c = Creature(name="Bear")
        assert CardType.CREATURE in c.card_types

    def test_default_base_power_toughness_zero(self) -> None:
        """base_power and base_toughness should default to 0."""
        c = Creature()
        assert c.base_power == 0
        assert c.base_toughness == 0


class TestCreatureCounters:
    """Verify creature power/toughness with +1/+1 and -1/-1 counters."""

    def test_plus_one_counters_increase_power_and_toughness(self) -> None:
        """+1/+1 counters should increase both power and toughness."""
        c = Creature(base_power=2, base_toughness=2)
        c.plus_one_counters = 3
        assert c.power == 5
        assert c.toughness == 5

    def test_minus_one_counters_decrease_power_and_toughness(self) -> None:
        """-1/-1 counters should decrease both power and toughness."""
        c = Creature(base_power=4, base_toughness=4)
        c.minus_one_counters = 2
        assert c.power == 2
        assert c.toughness == 2

    def test_mixed_counters(self) -> None:
        """Both counter types should combine correctly."""
        c = Creature(base_power=3, base_toughness=3)
        c.plus_one_counters = 2
        c.minus_one_counters = 1
        # power = 3 + 2 - 1 = 4
        assert c.power == 4
        assert c.toughness == 4

    def test_counters_can_reduce_below_zero(self) -> None:
        """Counters should be able to reduce power/toughness below zero."""
        c = Creature(base_power=1, base_toughness=1)
        c.minus_one_counters = 3
        assert c.power == -2
        assert c.toughness == -2

    def test_counters_default_to_zero(self) -> None:
        """plus_one_counters and minus_one_counters should default to 0."""
        c = Creature()
        assert c.plus_one_counters == 0
        assert c.minus_one_counters == 0


class TestCreatureKeywords:
    """Verify Keyword enum flags on creatures."""

    def test_creature_with_single_keyword(self) -> None:
        """A creature should store a single keyword correctly."""
        c = Creature(name="Flyer", keywords=Keyword.FLYING, base_power=2, base_toughness=2)
        assert Keyword.FLYING in c.keywords

    def test_creature_with_multiple_keywords(self) -> None:
        """A creature should store combined keywords via bitwise OR."""
        kw = Keyword.FLYING | Keyword.TRAMPLE | Keyword.LIFELINK
        c = Creature(name="Angel", keywords=kw, base_power=4, base_toughness=4)
        assert Keyword.FLYING in c.keywords
        assert Keyword.TRAMPLE in c.keywords
        assert Keyword.LIFELINK in c.keywords
        assert Keyword.DEATHTOUCH not in c.keywords

    def test_creature_with_no_keywords(self) -> None:
        """A vanilla creature should have empty keyword flags."""
        c = Creature(name="Vanilla Bear", base_power=2, base_toughness=2)
        assert not c.keywords  # falsy empty flag


# ---------------------------------------------------------------------------
# Instant / Sorcery
# ---------------------------------------------------------------------------

class TestInstant:
    """Verify Instant construction."""

    def test_instant_card_type(self) -> None:
        """Instant should have INSTANT in card_types by default."""
        spell = Instant(name="Lightning Bolt")
        assert CardType.INSTANT in spell.card_types

    def test_instant_stores_name_and_mana_cost(self) -> None:
        """Instant should store name and mana_cost."""
        mc = ManaCost(pips={ManaType.RED: 1})
        spell = Instant(name="Lightning Bolt", mana_cost=mc)
        assert spell.name == "Lightning Bolt"
        assert spell.mana_cost is mc

    def test_instant_inherits_game_object_id(self) -> None:
        """Instant should get an auto-incremented object_id."""
        spell = Instant(name="Bolt")
        assert spell.object_id >= 1


class TestSorcery:
    """Verify Sorcery construction."""

    def test_sorcery_card_type(self) -> None:
        """Sorcery should have SORCERY in card_types by default."""
        spell = Sorcery(name="Wrath of God")
        assert CardType.SORCERY in spell.card_types

    def test_sorcery_stores_name(self) -> None:
        """Sorcery should store the name."""
        spell = Sorcery(name="Day of Judgment")
        assert spell.name == "Day of Judgment"


# ---------------------------------------------------------------------------
# Enchantment
# ---------------------------------------------------------------------------

class TestEnchantment:
    """Verify Enchantment construction and aura support."""

    def test_enchantment_card_type(self) -> None:
        """Enchantment should have ENCHANTMENT in card_types by default."""
        ench = Enchantment(name="Pacifism")
        assert CardType.ENCHANTMENT in ench.card_types

    def test_attached_to_defaults_to_none(self) -> None:
        """attached_to should default to None."""
        ench = Enchantment(name="Pacifism")
        assert ench.attached_to is None

    def test_attached_to_can_be_set(self) -> None:
        """attached_to can be set to a specific target."""
        target = Creature(name="Bear", base_power=2, base_toughness=2)
        ench = Enchantment(name="Pacifism", attached_to=target)
        assert ench.attached_to is target

    def test_apply_continuous_effect_callable(self) -> None:
        """apply_continuous_effect should be callable without error."""
        game = _make_game()
        ench = Enchantment(name="Test")
        result = ench.apply_continuous_effect(game)
        assert result is None

    def test_on_enchant_callable(self) -> None:
        """on_enchant should be callable without error."""
        game = _make_game()
        ench = Enchantment(name="Test")
        result = ench.on_enchant(game)
        assert result is None

    def test_on_detach_callable(self) -> None:
        """on_detach should be callable without error."""
        game = _make_game()
        ench = Enchantment(name="Test")
        result = ench.on_detach(game)
        assert result is None


# ---------------------------------------------------------------------------
# Artifact / ArtifactCreature
# ---------------------------------------------------------------------------

class TestArtifact:
    """Verify Artifact construction."""

    def test_artifact_card_type(self) -> None:
        """Artifact should have ARTIFACT in card_types by default."""
        art = Artifact(name="Sol Ring")
        assert CardType.ARTIFACT in art.card_types

    def test_artifact_stores_name(self) -> None:
        """Artifact should store the name."""
        art = Artifact(name="Sol Ring")
        assert art.name == "Sol Ring"


class TestArtifactCreature:
    """Verify ArtifactCreature combines artifact and creature features."""

    def test_has_both_artifact_and_creature_card_types(self) -> None:
        """ArtifactCreature should include both ARTIFACT and CREATURE card types."""
        ac = ArtifactCreature(name="Ornithopter", base_power=0, base_toughness=2)
        assert CardType.ARTIFACT in ac.card_types
        assert CardType.CREATURE in ac.card_types

    def test_has_creature_power_toughness(self) -> None:
        """ArtifactCreature should have creature power/toughness properties."""
        ac = ArtifactCreature(name="Ornithopter", base_power=0, base_toughness=2)
        assert ac.base_power == 0
        assert ac.base_toughness == 2
        assert ac.power == 0
        assert ac.toughness == 2

    def test_has_creature_combat_flags(self) -> None:
        """ArtifactCreature should have creature combat state attributes."""
        ac = ArtifactCreature(name="Ornithopter")
        assert ac.is_tapped is False
        assert ac.summoning_sick is True
        assert ac.is_attacking is False
        assert ac.is_blocking is False
        assert ac.damage_marked == 0

    def test_artifact_creature_counters(self) -> None:
        """ArtifactCreature should support +1/+1 and -1/-1 counters."""
        ac = ArtifactCreature(name="Test", base_power=1, base_toughness=1)
        ac.plus_one_counters = 2
        assert ac.power == 3
        assert ac.toughness == 3


# ---------------------------------------------------------------------------
# Planeswalker
# ---------------------------------------------------------------------------

class TestPlaneswalker:
    """Verify Planeswalker construction and loyalty."""

    def test_planeswalker_card_type(self) -> None:
        """Planeswalker should have PLANESWALKER in card_types by default."""
        pw = Planeswalker(name="Jace", starting_loyalty=4)
        assert CardType.PLANESWALKER in pw.card_types

    def test_starting_loyalty_stored(self) -> None:
        """starting_loyalty should be stored as provided."""
        pw = Planeswalker(name="Jace", starting_loyalty=4)
        assert pw.starting_loyalty == 4

    def test_loyalty_equals_starting_loyalty(self) -> None:
        """loyalty should initially equal starting_loyalty."""
        pw = Planeswalker(name="Jace", starting_loyalty=5)
        assert pw.loyalty == 5

    def test_loyalty_can_be_modified(self) -> None:
        """loyalty counter can be incremented and decremented."""
        pw = Planeswalker(name="Jace", starting_loyalty=4)
        pw.loyalty += 1
        assert pw.loyalty == 5
        pw.loyalty -= 3
        assert pw.loyalty == 2

    def test_get_loyalty_abilities_returns_empty_list(self) -> None:
        """Default get_loyalty_abilities should return an empty list."""
        pw = Planeswalker(name="Jace", starting_loyalty=4)
        assert pw.get_loyalty_abilities() == []

    def test_starting_loyalty_defaults_to_zero(self) -> None:
        """starting_loyalty should default to 0 if not provided."""
        pw = Planeswalker(name="TestPW")
        assert pw.starting_loyalty == 0
        assert pw.loyalty == 0


# ---------------------------------------------------------------------------
# Land
# ---------------------------------------------------------------------------

class TestLand:
    """Verify Land construction and special behavior."""

    def test_land_card_type(self) -> None:
        """Land should have LAND in card_types by default."""
        land = Land(name="Forest")
        assert CardType.LAND in land.card_types

    def test_can_cast_returns_false(self) -> None:
        """Land.can_cast should always return False (lands are played, not cast)."""
        game = _make_game()
        land = Land(name="Forest")
        assert land.can_cast(game) is False

    def test_get_mana_abilities_returns_list(self) -> None:
        """get_mana_abilities should return a list (empty by default)."""
        land = Land(name="Forest")
        result = land.get_mana_abilities()
        assert isinstance(result, list)
        assert result == []

    def test_land_stores_name(self) -> None:
        """Land should store the name."""
        land = Land(name="Island")
        assert land.name == "Island"

    def test_land_with_supertypes(self) -> None:
        """Land can have supertypes like BASIC."""
        land = Land(name="Forest", supertypes={Supertype.BASIC})
        assert Supertype.BASIC in land.supertypes


# ---------------------------------------------------------------------------
# ManaCost CMC via card
# ---------------------------------------------------------------------------

class TestManaCostCmcViaCard:
    """Verify that a card's mana_cost.cmc reflects the total mana value."""

    def test_creature_with_mana_cost_cmc(self) -> None:
        """A creature's CMC should be accessible via mana_cost.cmc."""
        mc = ManaCost(generic=1, pips={ManaType.GREEN: 1})
        c = Creature(name="Bear", mana_cost=mc, base_power=2, base_toughness=2)
        assert c.mana_cost.cmc == 2

    def test_instant_cmc(self) -> None:
        """An instant's CMC should reflect generic + pip costs."""
        mc = ManaCost(generic=0, pips={ManaType.RED: 1})
        spell = Instant(name="Lightning Bolt", mana_cost=mc)
        assert spell.mana_cost.cmc == 1

    def test_card_with_zero_cmc(self) -> None:
        """A card with no mana cost has CMC 0."""
        card = CardImpl(name="Free Spell")
        assert card.mana_cost.cmc == 0

    def test_card_with_multi_color_cmc(self) -> None:
        """A multi-color card's CMC includes all pips and generic cost."""
        mc = ManaCost(generic=2, pips={ManaType.WHITE: 1, ManaType.BLUE: 1})
        card = CardImpl(name="Sphinx", mana_cost=mc)
        assert card.mana_cost.cmc == 4


# ---------------------------------------------------------------------------
# Supporting dataclasses
# ---------------------------------------------------------------------------

class TestSupportingDataclasses:
    """Verify supporting dataclass instantiation and field defaults."""

    def test_mode_instantiation(self) -> None:
        """Mode should be constructible with name and description."""
        m = Mode(name="Destroy target creature", description="Destroys one creature.")
        assert m.name == "Destroy target creature"
        assert m.description == "Destroys one creature."

    def test_mode_defaults(self) -> None:
        """Mode fields should default to empty strings."""
        m = Mode()
        assert m.name == ""
        assert m.description == ""

    def test_activated_ability_instantiation(self) -> None:
        """ActivatedAbility should be constructible with cost and effect callables."""
        ab = ActivatedAbility(cost=lambda g: True, effect=lambda g: None, description="Tap: draw")
        assert callable(ab.cost)
        assert callable(ab.effect)
        assert ab.description == "Tap: draw"

    def test_loyalty_ability_instantiation(self) -> None:
        """LoyaltyAbility should store loyalty_cost, effect, and description."""
        la = LoyaltyAbility(loyalty_cost=-2, effect=lambda g: None, description="Draw 2")
        assert la.loyalty_cost == -2
        assert callable(la.effect)
        assert la.description == "Draw 2"

    def test_loyalty_ability_positive_cost(self) -> None:
        """LoyaltyAbility loyalty_cost can be positive (for + abilities)."""
        la = LoyaltyAbility(loyalty_cost=1, effect=lambda g: None)
        assert la.loyalty_cost == 1

    def test_mana_ability_instantiation(self) -> None:
        """ManaAbility should store cost, mana_produced, and description."""
        ma = ManaAbility(
            cost=lambda g: True,
            mana_produced=lambda: "G",
            description="Add {G}",
        )
        assert callable(ma.cost)
        assert callable(ma.mana_produced)
        assert ma.description == "Add {G}"

    def test_continuous_effect_instantiation(self) -> None:
        """ContinuousEffect should store apply, remove, and description."""
        ce = ContinuousEffect(
            apply=lambda g: None,
            remove=lambda g: None,
            description="All creatures get +1/+1",
        )
        assert callable(ce.apply)
        assert callable(ce.remove)
        assert ce.description == "All creatures get +1/+1"

    def test_continuous_effect_defaults(self) -> None:
        """ContinuousEffect description should default to empty string."""
        ce = ContinuousEffect(apply=lambda g: None, remove=lambda g: None)
        assert ce.description == ""


# ---------------------------------------------------------------------------
# Vanilla creature — complete integration-style test
# ---------------------------------------------------------------------------

class TestVanillaCreature:
    """Integration-style test: a vanilla creature with P/T, CMC, and keywords."""

    def test_vanilla_creature_full_profile(self) -> None:
        """A vanilla 2/2 for {1}{G} should have correct P/T, CMC, empty keywords."""
        owner = _make_player("Alice")
        mc = ManaCost(generic=1, pips={ManaType.GREEN: 1})
        bear = Creature(
            name="Grizzly Bears",
            mana_cost=mc,
            card_types={CardType.CREATURE},
            subtypes={"Bear"},
            owner=owner,
            base_power=2,
            base_toughness=2,
        )
        assert bear.name == "Grizzly Bears"
        assert bear.mana_cost.cmc == 2
        assert bear.power == 2
        assert bear.toughness == 2
        assert not bear.keywords
        assert bear.subtypes == {"Bear"}
        assert CardType.CREATURE in bear.card_types
        assert bear.owner is owner
        assert bear.controller is owner
