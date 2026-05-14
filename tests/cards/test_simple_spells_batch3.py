"""Tests for cards/fdn/_legacy/simple_spells_batch3.py — Targeted instants and sorceries.

All 18 spells are from the MTG Foundations (FDN) set.

Verifies:
- Each spell has the correct name, mana cost, card type (Instant vs Sorcery).
- Each spell's get_targets() returns correct TargetRequirement(s).
- Each spell's on_resolve() applies the correct effect on the target.
- Spells with no valid target do nothing on resolve.
- Registry registration and metadata accuracy.
"""

from __future__ import annotations

import pytest

from cards.fdn._legacy.simple_spells_batch3 import (
    BakeIntoAPie,
    BiteDown,
    BrokenWings,
    DivineResilience,
    EatenAlive,
    EssenceScatter,
    FakeYourOwnDeath,
    FellingBlow,
    FleetingDistraction,
    FleetingFlight,
    JoustThrough,
    LuminousRebuke,
    MakeYourMove,
    RunAwayTogether,
    SnakeskinVeil,
    StrokeOfMidnight,
    SureStrike,
    Zombify,
    register_simple_spells_batch3,
)
from cards.registry import CardRegistry
from engine.card import Artifact, Creature, Enchantment, Instant, Sorcery
from engine.game_state import GameState
from engine.player import DeterministicPlayer
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
# Spell attribute verification — parameterized
# ---------------------------------------------------------------------------

_SPELL_ATTRS = [
    # (class, name, cost_str, card_type, base_class)
    (JoustThrough, "Joust Through", "{W}", CardType.INSTANT, Instant),
    (LuminousRebuke, "Luminous Rebuke", "{4}{W}", CardType.INSTANT, Instant),
    (MakeYourMove, "Make Your Move", "{2}{W}", CardType.INSTANT, Instant),
    (StrokeOfMidnight, "Stroke of Midnight", "{2}{W}", CardType.INSTANT, Instant),
    (BakeIntoAPie, "Bake into a Pie", "{2}{B}{B}", CardType.INSTANT, Instant),
    (EatenAlive, "Eaten Alive", "{B}", CardType.SORCERY, Sorcery),
    (BrokenWings, "Broken Wings", "{2}{G}", CardType.INSTANT, Instant),
    (EssenceScatter, "Essence Scatter", "{1}{U}", CardType.INSTANT, Instant),
    (RunAwayTogether, "Run Away Together", "{1}{U}", CardType.INSTANT, Instant),
    (SureStrike, "Sure Strike", "{1}{R}", CardType.INSTANT, Instant),
    (SnakeskinVeil, "Snakeskin Veil", "{G}", CardType.INSTANT, Instant),
    (FleetingDistraction, "Fleeting Distraction", "{U}", CardType.INSTANT, Instant),
    (DivineResilience, "Divine Resilience", "{W}", CardType.INSTANT, Instant),
    (FleetingFlight, "Fleeting Flight", "{W}", CardType.INSTANT, Instant),
    (FakeYourOwnDeath, "Fake Your Own Death", "{1}{B}", CardType.INSTANT, Instant),
    (BiteDown, "Bite Down", "{1}{G}", CardType.INSTANT, Instant),
    (FellingBlow, "Felling Blow", "{2}{G}", CardType.SORCERY, Sorcery),
    (Zombify, "Zombify", "{3}{B}", CardType.SORCERY, Sorcery),
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
# Targeting — verify get_targets() returns TargetRequirement(s)
# ---------------------------------------------------------------------------

class TestGetTargets:
    """Verify get_targets() returns TargetRequirement with correct zone/filter."""

    def test_joust_through_targets_creature(self) -> None:
        game = _make_game()
        p2 = game.players[1]
        creature = _make_creature(owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])

        spell = JoustThrough(owner=game.players[0], controller=game.players[0])
        targets = spell.get_targets(game)
        assert len(targets) == 1
        assert targets[0].zone == Zone.BATTLEFIELD
        assert targets[0].filter_fn(creature) is True

    def test_luminous_rebuke_targets_creature(self) -> None:
        game = _make_game()
        p2 = game.players[1]
        creature = _make_creature(owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])

        spell = LuminousRebuke(owner=game.players[0], controller=game.players[0])
        targets = spell.get_targets(game)
        assert len(targets) == 1
        assert targets[0].filter_fn(creature) is True

    def test_make_your_move_targets_artifact(self) -> None:
        game = _make_game()
        p2 = game.players[1]
        art = Artifact(name="Test Artifact", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[art])

        spell = MakeYourMove(owner=game.players[0], controller=game.players[0])
        targets = spell.get_targets(game)
        assert len(targets) == 1
        assert targets[0].filter_fn(art) is True

    def test_make_your_move_rejects_small_creature(self) -> None:
        """Creatures with power < 4 should not be valid targets."""
        game = _make_game()
        p2 = game.players[1]
        small = _make_creature(owner=p2, controller=p2, power=3, toughness=3)
        set_board_state(game, 1, battlefield=[small])

        spell = MakeYourMove(owner=game.players[0], controller=game.players[0])
        targets = spell.get_targets(game)
        assert len(targets) == 1
        assert targets[0].filter_fn(small) is False

    def test_make_your_move_accepts_big_creature(self) -> None:
        """Creatures with power >= 4 should be valid targets."""
        game = _make_game()
        p2 = game.players[1]
        big = _make_creature(owner=p2, controller=p2, power=4, toughness=4)
        set_board_state(game, 1, battlefield=[big])

        spell = MakeYourMove(owner=game.players[0], controller=game.players[0])
        targets = spell.get_targets(game)
        assert len(targets) == 1
        assert targets[0].filter_fn(big) is True

    def test_stroke_of_midnight_targets_nonland(self) -> None:
        game = _make_game()
        p2 = game.players[1]
        creature = _make_creature(owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])

        spell = StrokeOfMidnight(owner=game.players[0], controller=game.players[0])
        targets = spell.get_targets(game)
        assert len(targets) == 1
        assert targets[0].filter_fn(creature) is True

    def test_broken_wings_targets_creature_with_flying(self) -> None:
        game = _make_game()
        p2 = game.players[1]
        flyer = _make_creature(owner=p2, controller=p2, name="Flyer")
        flyer.keywords = Keyword.FLYING
        nonflyer = _make_creature(owner=p2, controller=p2, name="Walker")
        set_board_state(game, 1, battlefield=[flyer, nonflyer])

        spell = BrokenWings(owner=game.players[0], controller=game.players[0])
        targets = spell.get_targets(game)
        assert len(targets) == 1
        assert targets[0].filter_fn(flyer) is True
        assert targets[0].filter_fn(nonflyer) is False

    def test_run_away_together_returns_two_target_reqs(self) -> None:
        """Run Away Together needs two target creatures."""
        game = _make_game()
        p1, p2 = game.players
        c1 = _make_creature(owner=p1, controller=p1, name="C1")
        c2 = _make_creature(owner=p2, controller=p2, name="C2")
        set_board_state(game, 0, battlefield=[c1])
        set_board_state(game, 1, battlefield=[c2])

        spell = RunAwayTogether(owner=p1, controller=p1)
        targets = spell.get_targets(game)
        assert len(targets) == 2

    def test_bite_down_returns_two_target_reqs(self) -> None:
        """Bite Down needs your creature + opponent's creature/PW."""
        game = _make_game()
        p1, p2 = game.players
        c1 = _make_creature(owner=p1, controller=p1, name="Mine")
        c2 = _make_creature(owner=p2, controller=p2, name="Theirs")
        set_board_state(game, 0, battlefield=[c1])
        set_board_state(game, 1, battlefield=[c2])

        spell = BiteDown(owner=p1, controller=p1)
        targets = spell.get_targets(game)
        assert len(targets) == 2

    def test_felling_blow_returns_two_target_reqs(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        c1 = _make_creature(owner=p1, controller=p1, name="Mine")
        c2 = _make_creature(owner=p2, controller=p2, name="Theirs")
        set_board_state(game, 0, battlefield=[c1])
        set_board_state(game, 1, battlefield=[c2])

        spell = FellingBlow(owner=p1, controller=p1)
        targets = spell.get_targets(game)
        assert len(targets) == 2

    def test_zombify_targets_creature_in_graveyard(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        dead = _make_creature(owner=p1, controller=p1, name="Dead Guy")
        set_board_state(game, 0, graveyard=[dead])

        spell = Zombify(owner=p1, controller=p1)
        targets = spell.get_targets(game)
        assert len(targets) == 1
        assert targets[0].zone == Zone.GRAVEYARD
        assert targets[0].filter_fn(dead) is True

    def test_zombify_no_targets_empty_graveyard(self) -> None:
        game = _make_game()
        p1 = game.players[0]

        spell = Zombify(owner=p1, controller=p1)
        targets = spell.get_targets(game)
        assert targets == []


# ---------------------------------------------------------------------------
# Burn — Joust Through
# ---------------------------------------------------------------------------

class TestJoustThrough:
    """Joust Through deals 3 damage to target creature; controller gains 1 life."""

    def test_deals_3_damage(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2, toughness=5)
        set_board_state(game, 1, battlefield=[creature])

        spell = JoustThrough(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1})
        cast_spell(game, 0, "Joust Through", targets=[creature])

        assert creature.damage_marked == 3

    def test_controller_gains_1_life(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2, toughness=5)
        set_board_state(game, 1, battlefield=[creature])

        spell = JoustThrough(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1})
        cast_spell(game, 0, "Joust Through", targets=[creature])

        assert p1.life == 21

    def test_no_target_does_nothing(self) -> None:
        """If target is None, on_resolve should not crash."""
        game = _make_game()
        p1 = game.players[0]
        spell = JoustThrough(owner=p1, controller=p1)
        spell.chosen_targets = []
        spell.on_resolve(game)  # Should not raise


# ---------------------------------------------------------------------------
# Targeted removal — Luminous Rebuke
# ---------------------------------------------------------------------------

class TestLuminousRebuke:
    """Luminous Rebuke — {4}{W} — Destroy target creature."""

    def test_destroys_creature(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        creature = _make_creature(name="Victim", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])

        spell = LuminousRebuke(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 4})
        cast_spell(game, 0, "Luminous Rebuke", targets=[creature])

        assert not p2.zones[Zone.BATTLEFIELD].contains(creature)
        assert p2.zones[Zone.GRAVEYARD].contains(creature)


# ---------------------------------------------------------------------------
# Targeted removal — Make Your Move
# ---------------------------------------------------------------------------

class TestMakeYourMove:
    """Make Your Move — {2}{W} — Destroy target artifact, enchantment, or creature with power 4+."""

    def test_destroys_artifact(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        art = Artifact(name="Doomed Artifact", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[art])

        spell = MakeYourMove(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Make Your Move", targets=[art])

        assert not p2.zones[Zone.BATTLEFIELD].contains(art)
        assert p2.zones[Zone.GRAVEYARD].contains(art)

    def test_destroys_big_creature(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        big = _make_creature(name="Big Boy", owner=p2, controller=p2, power=5, toughness=5)
        set_board_state(game, 1, battlefield=[big])

        spell = MakeYourMove(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Make Your Move", targets=[big])

        assert not p2.zones[Zone.BATTLEFIELD].contains(big)


# ---------------------------------------------------------------------------
# Targeted removal — Stroke of Midnight
# ---------------------------------------------------------------------------

class TestStrokeOfMidnight:
    """Stroke of Midnight — Destroy target nonland permanent; controller gets 1/1 token."""

    def test_destroys_creature_creates_token(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        creature = _make_creature(name="Victim", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])

        spell = StrokeOfMidnight(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Stroke of Midnight", targets=[creature])

        # Creature destroyed
        assert not p2.zones[Zone.BATTLEFIELD].contains(creature)
        # Controller of destroyed permanent gets a 1/1 Human token
        bf_objects = p2.zones[Zone.BATTLEFIELD].get_all()
        tokens = [o for o in bf_objects if getattr(o, "is_token", False)]
        assert len(tokens) == 1
        assert tokens[0].base_power == 1
        assert tokens[0].base_toughness == 1


# ---------------------------------------------------------------------------
# Targeted removal — Bake into a Pie
# ---------------------------------------------------------------------------

class TestBakeIntoAPie:
    """Bake into a Pie — Destroy target creature; create a Food token."""

    def test_destroys_creature_creates_food(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        creature = _make_creature(name="Victim", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])

        spell = BakeIntoAPie(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLACK: 2, ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Bake into a Pie", targets=[creature])

        # Creature destroyed
        assert not p2.zones[Zone.BATTLEFIELD].contains(creature)
        # Controller of spell (p1) gets Food token
        bf_objects = p1.zones[Zone.BATTLEFIELD].get_all()
        foods = [o for o in bf_objects if getattr(o, "name", "") == "Food Token"]
        assert len(foods) == 1
        assert CardType.ARTIFACT in foods[0].card_types


# ---------------------------------------------------------------------------
# Exile — Eaten Alive
# ---------------------------------------------------------------------------

class TestEatenAlive:
    """Eaten Alive — {B} — Exile target creature or planeswalker."""

    def test_exiles_creature(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        creature = _make_creature(name="Victim", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])

        spell = EatenAlive(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLACK: 1})
        cast_spell(game, 0, "Eaten Alive", targets=[creature])

        assert not p2.zones[Zone.BATTLEFIELD].contains(creature)
        assert p2.zones[Zone.EXILE].contains(creature)


# ---------------------------------------------------------------------------
# Removal — Broken Wings
# ---------------------------------------------------------------------------

class TestBrokenWings:
    """Broken Wings — {2}{G} — Destroy target artifact, enchantment, or creature with flying."""

    def test_destroys_flying_creature(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        flyer = _make_creature(name="Flyer", owner=p2, controller=p2)
        flyer.keywords = Keyword.FLYING
        set_board_state(game, 1, battlefield=[flyer])

        spell = BrokenWings(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.GREEN: 1, ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Broken Wings", targets=[flyer])

        assert not p2.zones[Zone.BATTLEFIELD].contains(flyer)
        assert p2.zones[Zone.GRAVEYARD].contains(flyer)

    def test_destroys_enchantment(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        ench = Enchantment(name="Test Enchantment", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[ench])

        spell = BrokenWings(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.GREEN: 1, ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Broken Wings", targets=[ench])

        assert not p2.zones[Zone.BATTLEFIELD].contains(ench)


# ---------------------------------------------------------------------------
# Counter — Essence Scatter
# ---------------------------------------------------------------------------

class TestEssenceScatter:
    """Essence Scatter — {1}{U} — Counter target creature spell."""

    def test_can_cast_false_with_empty_stack(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        spell = EssenceScatter(owner=p1, controller=p1)
        assert spell.can_cast(game) is False

    def test_can_cast_true_with_creature_on_stack(self) -> None:
        from engine.stack import StackObject

        game = _make_game()
        p1, p2 = game.players
        creature = Creature(name="Bear", owner=p2, controller=p2)
        stack_obj = StackObject(source=creature, controller=p2)
        game.stack.push(stack_obj)

        spell = EssenceScatter(owner=p1, controller=p1)
        assert spell.can_cast(game) is True

    def test_can_cast_false_with_noncreature_on_stack(self) -> None:
        from engine.stack import StackObject

        game = _make_game()
        p1, p2 = game.players
        sorc = Sorcery(name="Some Sorcery", owner=p2, controller=p2)
        stack_obj = StackObject(source=sorc, controller=p2)
        game.stack.push(stack_obj)

        spell = EssenceScatter(owner=p1, controller=p1)
        assert spell.can_cast(game) is False

    def test_get_targets_includes_creature_spell(self) -> None:
        from engine.stack import StackObject

        game = _make_game()
        p1, p2 = game.players
        creature = Creature(name="Bear", owner=p2, controller=p2)
        stack_obj = StackObject(source=creature, controller=p2)
        game.stack.push(stack_obj)

        spell = EssenceScatter(owner=p1, controller=p1)
        targets = spell.get_targets(game)
        assert len(targets) == 1
        assert targets[0].filter_fn(stack_obj) is True

    def test_counters_creature_spell(self) -> None:
        from engine.stack import StackObject

        game = _make_game()
        p1, p2 = game.players
        creature = Creature(name="Bear", owner=p2, controller=p2)
        p2.zones[Zone.STACK].add(creature)
        stack_obj = StackObject(source=creature, controller=p2)
        game.stack.push(stack_obj)

        spell = EssenceScatter(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        assert p2.zones[Zone.GRAVEYARD].contains(creature)


# ---------------------------------------------------------------------------
# Bounce — Run Away Together
# ---------------------------------------------------------------------------

class TestRunAwayTogether:
    """Run Away Together — {1}{U} — Return two target creatures to owners' hands."""

    def test_bounces_two_creatures(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        c1 = _make_creature(name="Creature A", owner=p1, controller=p1)
        c2 = _make_creature(name="Creature B", owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[c1])
        set_board_state(game, 1, battlefield=[c2])

        spell = RunAwayTogether(owner=p1, controller=p1)
        spell.chosen_targets = [c1, c2]
        spell.on_resolve(game)

        assert not p1.zones[Zone.BATTLEFIELD].contains(c1)
        assert p1.zones[Zone.HAND].contains(c1)
        assert not p2.zones[Zone.BATTLEFIELD].contains(c2)
        assert p2.zones[Zone.HAND].contains(c2)


# ---------------------------------------------------------------------------
# Pump — Sure Strike
# ---------------------------------------------------------------------------

class TestSureStrike:
    """Sure Strike — {1}{R} — Target creature gets +3/+0 and first strike until EOT."""

    def test_grants_plus_3_power(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1, power=2, toughness=2)
        set_board_state(game, 0, battlefield=[creature])

        spell = SureStrike(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.RED: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Sure Strike", targets=[creature])

        game.effect_manager.apply_all(game)
        assert creature.base_power == 5  # 2 + 3

    def test_grants_first_strike(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1, power=2, toughness=2)
        set_board_state(game, 0, battlefield=[creature])

        spell = SureStrike(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.RED: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Sure Strike", targets=[creature])

        game.effect_manager.apply_all(game)
        assert Keyword.FIRST_STRIKE in creature.keywords


# ---------------------------------------------------------------------------
# Pump — Snakeskin Veil
# ---------------------------------------------------------------------------

class TestSnakeskinVeil:
    """Snakeskin Veil — {G} — +1/+1 counter and hexproof until EOT."""

    def test_adds_counter(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1, power=2, toughness=2)
        set_board_state(game, 0, battlefield=[creature])

        spell = SnakeskinVeil(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.GREEN: 1})
        cast_spell(game, 0, "Snakeskin Veil", targets=[creature])

        # +1/+1 counter increments plus_one_counters; power/toughness reflect it
        assert creature.plus_one_counters == 1
        assert creature.power == 3
        assert creature.toughness == 3

    def test_grants_hexproof(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1, power=2, toughness=2)
        set_board_state(game, 0, battlefield=[creature])

        spell = SnakeskinVeil(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.GREEN: 1})
        cast_spell(game, 0, "Snakeskin Veil", targets=[creature])

        game.effect_manager.apply_all(game)
        assert Keyword.HEXPROOF in creature.keywords


# ---------------------------------------------------------------------------
# Pump — Fleeting Distraction
# ---------------------------------------------------------------------------

class TestFleetingDistraction:
    """Fleeting Distraction — {U} — -1/-0 until EOT; draw a card."""

    def test_reduces_power(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1, power=3, toughness=3)
        set_board_state(game, 0, battlefield=[creature])

        # Need library cards for draw
        lib_card = Creature(name="Lib Card", owner=p1, controller=p1)
        p1.zones[Zone.LIBRARY].add(lib_card)

        spell = FleetingDistraction(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Fleeting Distraction", targets=[creature])

        game.effect_manager.apply_all(game)
        assert creature.base_power == 2  # 3 - 1

    def test_draws_a_card(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1, power=3, toughness=3)
        set_board_state(game, 0, battlefield=[creature])

        lib_card = Creature(name="Lib Card", owner=p1, controller=p1)
        p1.zones[Zone.LIBRARY].add(lib_card)

        spell = FleetingDistraction(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 1})

        initial_hand = len(p1.zones[Zone.HAND].get_all())  # just the spell
        cast_spell(game, 0, "Fleeting Distraction", targets=[creature])

        # Spell left hand (-1), drew card (+1); net = same
        # But spell is gone from hand and card was drawn, so hand should have 1
        assert len(p1.zones[Zone.HAND].get_all()) == 1


# ---------------------------------------------------------------------------
# Pump — Divine Resilience
# ---------------------------------------------------------------------------

class TestDivineResilience:
    """Divine Resilience — {W} — Grants indestructible until EOT."""

    def test_grants_indestructible(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1, power=2, toughness=2)
        set_board_state(game, 0, battlefield=[creature])

        spell = DivineResilience(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1})
        cast_spell(game, 0, "Divine Resilience", targets=[creature])

        game.effect_manager.apply_all(game)
        assert Keyword.INDESTRUCTIBLE in creature.keywords


# ---------------------------------------------------------------------------
# Pump — Fleeting Flight
# ---------------------------------------------------------------------------

class TestFleetingFlight:
    """Fleeting Flight — {W} — +1/+1 counter; flying until EOT."""

    def test_adds_counter(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1, power=2, toughness=2)
        set_board_state(game, 0, battlefield=[creature])

        spell = FleetingFlight(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1})
        cast_spell(game, 0, "Fleeting Flight", targets=[creature])

        assert creature.plus_one_counters == 1
        assert creature.power == 3
        assert creature.toughness == 3

    def test_grants_flying(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1, power=2, toughness=2)
        set_board_state(game, 0, battlefield=[creature])

        spell = FleetingFlight(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1})
        cast_spell(game, 0, "Fleeting Flight", targets=[creature])

        game.effect_manager.apply_all(game)
        assert Keyword.FLYING in creature.keywords


# ---------------------------------------------------------------------------
# Pump — Fake Your Own Death
# ---------------------------------------------------------------------------

class TestFakeYourOwnDeath:
    """Fake Your Own Death — {1}{B} — +2/+0 until EOT."""

    def test_grants_plus_2_power(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1, power=2, toughness=2)
        set_board_state(game, 0, battlefield=[creature])

        spell = FakeYourOwnDeath(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Fake Your Own Death", targets=[creature])

        game.effect_manager.apply_all(game)
        assert creature.base_power == 4  # 2 + 2


# ---------------------------------------------------------------------------
# Fight — Bite Down
# ---------------------------------------------------------------------------

class TestBiteDown:
    """Bite Down — {1}{G} — Your creature deals damage equal to its power to target."""

    def test_deals_damage_equal_to_power(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        my_creature = _make_creature(name="Fighter", owner=p1, controller=p1, power=4, toughness=4)
        their_creature = _make_creature(name="Target", owner=p2, controller=p2, power=2, toughness=5)
        set_board_state(game, 0, battlefield=[my_creature])
        set_board_state(game, 1, battlefield=[their_creature])

        spell = BiteDown(owner=p1, controller=p1)
        spell.chosen_targets = [my_creature, their_creature]
        spell.on_resolve(game)

        assert their_creature.damage_marked == 4  # damage = my_creature's power

    def test_no_damage_from_zero_power(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        weakling = _make_creature(name="Weakling", owner=p1, controller=p1, power=0, toughness=1)
        target = _make_creature(name="Target", owner=p2, controller=p2, power=2, toughness=5)
        set_board_state(game, 0, battlefield=[weakling])
        set_board_state(game, 1, battlefield=[target])

        spell = BiteDown(owner=p1, controller=p1)
        spell.chosen_targets = [weakling, target]
        spell.on_resolve(game)

        assert target.damage_marked == 0


# ---------------------------------------------------------------------------
# Fight — Felling Blow
# ---------------------------------------------------------------------------

class TestFellingBlow:
    """Felling Blow — {2}{G} — +1/+1 counter then one-way fight."""

    def test_adds_counter_then_deals_damage(self) -> None:
        game = _make_game()
        p1, p2 = game.players
        my_creature = _make_creature(name="Fighter", owner=p1, controller=p1, power=3, toughness=3)
        their_creature = _make_creature(name="Target", owner=p2, controller=p2, power=2, toughness=5)
        set_board_state(game, 0, battlefield=[my_creature])
        set_board_state(game, 1, battlefield=[their_creature])

        spell = FellingBlow(owner=p1, controller=p1)
        spell.chosen_targets = [my_creature, their_creature]
        spell.on_resolve(game)

        # +1/+1 counter first
        assert my_creature.plus_one_counters == 1
        assert my_creature.power == 4  # 3 + 1
        assert my_creature.toughness == 4  # 3 + 1
        # Then deals damage = new power
        assert their_creature.damage_marked == 4


# ---------------------------------------------------------------------------
# Reanimation — Zombify
# ---------------------------------------------------------------------------

class TestZombify:
    """Zombify — {3}{B} — Return target creature from graveyard to battlefield."""

    def test_returns_creature_to_battlefield(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        dead = _make_creature(name="Dead Guy", owner=p1, controller=p1, power=3, toughness=3)
        set_board_state(game, 0, graveyard=[dead])

        spell = Zombify(owner=p1, controller=p1)
        spell.chosen_targets = [dead]
        spell.on_resolve(game)

        assert p1.zones[Zone.BATTLEFIELD].contains(dead)
        assert not p1.zones[Zone.GRAVEYARD].contains(dead)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases: no target, target gone before resolve."""

    def test_luminous_rebuke_no_target_no_crash(self) -> None:
        """If chosen target is None, on_resolve does nothing."""
        game = _make_game()
        p1 = game.players[0]
        spell = LuminousRebuke(owner=p1, controller=p1)
        spell.chosen_targets = []
        spell.on_resolve(game)  # Should not raise

    def test_sure_strike_target_gone_no_crash(self) -> None:
        """If target left battlefield before resolve, spell fizzles gracefully."""
        game = _make_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1, power=2, toughness=2)
        # creature is NOT on the battlefield
        spell = SureStrike(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)  # Should not raise, no effect applied

    def test_bite_down_source_gone_no_crash(self) -> None:
        """If source creature left battlefield, Bite Down does nothing."""
        game = _make_game()
        p1, p2 = game.players
        my_creature = _make_creature(name="Fighter", owner=p1, controller=p1, power=4, toughness=4)
        their_creature = _make_creature(name="Target", owner=p2, controller=p2, power=2, toughness=5)
        # Only opponent's creature on battlefield; source creature is gone
        set_board_state(game, 1, battlefield=[their_creature])

        spell = BiteDown(owner=p1, controller=p1)
        spell.chosen_targets = [my_creature, their_creature]
        spell.on_resolve(game)

        assert their_creature.damage_marked == 0

    def test_run_away_together_one_target_gone(self) -> None:
        """If one target left, the other still gets bounced."""
        game = _make_game()
        p1, p2 = game.players
        c1 = _make_creature(name="C1", owner=p1, controller=p1)
        c2 = _make_creature(name="C2", owner=p2, controller=p2)
        # Only c2 is on the battlefield; c1 already gone
        set_board_state(game, 1, battlefield=[c2])

        spell = RunAwayTogether(owner=p1, controller=p1)
        spell.chosen_targets = [c1, c2]
        spell.on_resolve(game)

        assert p2.zones[Zone.HAND].contains(c2)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    """Verify register_simple_spells_batch3 registers all 18 cards."""

    def test_registers_all_cards(self) -> None:
        registry = CardRegistry()
        register_simple_spells_batch3(registry)

        expected_names = [
            "Joust Through",
            "Luminous Rebuke",
            "Make Your Move",
            "Stroke of Midnight",
            "Bake into a Pie",
            "Eaten Alive",
            "Broken Wings",
            "Essence Scatter",
            "Run Away Together",
            "Sure Strike",
            "Snakeskin Veil",
            "Fleeting Distraction",
            "Divine Resilience",
            "Fleeting Flight",
            "Fake Your Own Death",
            "Bite Down",
            "Felling Blow",
            "Zombify",
        ]
        for name in expected_names:
            assert registry.get(name) is not None, f"{name} not registered"

    def test_registry_count(self) -> None:
        registry = CardRegistry()
        register_simple_spells_batch3(registry)
        # Should have exactly 18 entries
        assert len(registry) == 18

    def test_registry_metadata_set_code(self) -> None:
        registry = CardRegistry()
        register_simple_spells_batch3(registry)
        entry = registry.get("Joust Through")
        assert entry is not None
        _, metadata = entry
        assert metadata.set_code == "fdn"
