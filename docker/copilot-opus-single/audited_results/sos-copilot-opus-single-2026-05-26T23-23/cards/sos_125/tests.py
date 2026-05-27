"""Tests for SOS 125 — Molten-Core Maestro.

Molten-Core Maestro is a 2/2 Goblin Bard for {1}{R} with Menace.
Opus ability: Whenever you cast an instant or sorcery spell, put a +1/+1
counter on this creature. If five or more mana was spent to cast that spell,
add an amount of {R} equal to this creature's power.
"""

from __future__ import annotations

from cards.sos.sos_125.card_impl import MoltenCoreMaestro
from engine.card import Creature, Instant, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestMoltenCoreMaestroProperties:
    """Static card data should match the SOS 125 spec."""

    def test_is_creature(self) -> None:
        card = MoltenCoreMaestro(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = MoltenCoreMaestro(owner=None)
        assert card.name == "Molten-Core Maestro"

    def test_mana_cost(self) -> None:
        card = MoltenCoreMaestro(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{R}")

    def test_base_power(self) -> None:
        card = MoltenCoreMaestro(owner=None)
        assert card.base_power == 2

    def test_base_toughness(self) -> None:
        card = MoltenCoreMaestro(owner=None)
        assert card.base_toughness == 2

    def test_card_types(self) -> None:
        card = MoltenCoreMaestro(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_subtypes(self) -> None:
        card = MoltenCoreMaestro(owner=None)
        assert "Goblin" in card.subtypes
        assert "Bard" in card.subtypes

    def test_has_menace(self) -> None:
        card = MoltenCoreMaestro(owner=None)
        assert Keyword.MENACE in card.keywords


# ---------------------------------------------------------------------------
# Opus triggered ability — +1/+1 counter on instant/sorcery cast
# ---------------------------------------------------------------------------


class TestOpusCounterTrigger:
    """Whenever you cast an instant or sorcery spell, put a +1/+1 counter."""

    def test_gains_counter_on_instant_cast(self) -> None:
        """Casting an instant triggers the Opus ability, adding a +1/+1 counter."""
        game = create_game()
        p1 = game.players[0]

        maestro = MoltenCoreMaestro(owner=p1, controller=p1)
        game.get_battlefield(p1).add(maestro)
        maestro.register_triggers(game)

        # Create a cheap instant to cast
        bolt = Instant(
            name="Lightning Bolt",
            mana_cost=ManaCost.parse("{R}"),
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[bolt], mana={ManaType.RED: 1})

        counters_before = maestro.plus_one_counters

        from test_utils import cast_spell
        cast_spell(game, 0, "Lightning Bolt")

        assert maestro.plus_one_counters == counters_before + 1

    def test_gains_counter_on_sorcery_cast(self) -> None:
        """Casting a sorcery also triggers the Opus ability."""
        game = create_game()
        p1 = game.players[0]

        maestro = MoltenCoreMaestro(owner=p1, controller=p1)
        game.get_battlefield(p1).add(maestro)
        maestro.register_triggers(game)

        sorcery = Sorcery(
            name="Lava Axe",
            mana_cost=ManaCost.parse("{4}{R}"),
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[sorcery], mana={ManaType.RED: 5, ManaType.COLORLESS: 4})

        counters_before = maestro.plus_one_counters
        from test_utils import cast_spell
        cast_spell(game, 0, "Lava Axe")

        assert maestro.plus_one_counters == counters_before + 1

    def test_no_counter_on_creature_cast(self) -> None:
        """Casting a creature spell should NOT trigger the Opus ability."""
        game = create_game()
        p1 = game.players[0]

        maestro = MoltenCoreMaestro(owner=p1, controller=p1)
        game.get_battlefield(p1).add(maestro)
        maestro.register_triggers(game)

        bear = Creature(
            name="Grizzly Bears",
            mana_cost=ManaCost.parse("{1}{G}"),
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, hand=[bear], mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1})

        counters_before = maestro.plus_one_counters
        from test_utils import cast_spell
        cast_spell(game, 0, "Grizzly Bears")

        assert maestro.plus_one_counters == counters_before

    def test_multiple_instants_give_multiple_counters(self) -> None:
        """Each instant/sorcery cast adds a separate +1/+1 counter."""
        game = create_game()
        p1 = game.players[0]

        maestro = MoltenCoreMaestro(owner=p1, controller=p1)
        game.get_battlefield(p1).add(maestro)
        maestro.register_triggers(game)

        bolt1 = Instant(
            name="Shock",
            mana_cost=ManaCost.parse("{R}"),
            owner=p1,
            controller=p1,
        )
        bolt2 = Instant(
            name="Lightning Bolt",
            mana_cost=ManaCost.parse("{R}"),
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[bolt1, bolt2], mana={ManaType.RED: 2})

        from test_utils import cast_spell
        cast_spell(game, 0, "Shock")
        cast_spell(game, 0, "Lightning Bolt")

        assert maestro.plus_one_counters == 2


# ---------------------------------------------------------------------------
# Opus bonus — 5+ mana spent → add {R} equal to power
# ---------------------------------------------------------------------------


class TestOpusManaGeneration:
    """If 5+ mana was spent to cast the spell, add {R} equal to power."""

    def test_no_mana_added_for_cheap_spell(self) -> None:
        """Spell costing less than 5 mana should not generate red mana."""
        game = create_game()
        p1 = game.players[0]

        maestro = MoltenCoreMaestro(owner=p1, controller=p1)
        game.get_battlefield(p1).add(maestro)
        maestro.register_triggers(game)

        bolt = Instant(
            name="Lightning Bolt",
            mana_cost=ManaCost.parse("{R}"),
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[bolt], mana={ManaType.RED: 1})

        from test_utils import cast_spell
        cast_spell(game, 0, "Lightning Bolt")

        # Mana pool should not gain red mana from the Opus bonus
        # After casting bolt (costs {R}), no extra red should remain from Opus
        red_in_pool = p1.mana_pool.get(ManaType.RED)
        assert red_in_pool == 0

    def test_mana_added_for_five_mana_spell(self) -> None:
        """Spell costing exactly 5 mana should add {R} equal to creature's power."""
        game = create_game()
        p1 = game.players[0]

        maestro = MoltenCoreMaestro(owner=p1, controller=p1)
        game.get_battlefield(p1).add(maestro)
        maestro.register_triggers(game)

        # A 5-mana sorcery
        big_spell = Sorcery(
            name="Explosive Welcome",
            mana_cost=ManaCost.parse("{4}{R}"),
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[big_spell], mana={ManaType.RED: 1, ManaType.COLORLESS: 4})

        from test_utils import cast_spell
        cast_spell(game, 0, "Explosive Welcome")

        # Maestro gets a +1/+1 counter first → power becomes 3.
        # Then bonus triggers: add {R} equal to power (3).
        red_in_pool = p1.mana_pool.get(ManaType.RED)
        assert red_in_pool == 3

    def test_mana_added_for_six_mana_spell(self) -> None:
        """Spell costing 6 mana (>5) should also trigger the bonus."""
        game = create_game()
        p1 = game.players[0]

        maestro = MoltenCoreMaestro(owner=p1, controller=p1)
        game.get_battlefield(p1).add(maestro)
        maestro.register_triggers(game)

        big_spell = Sorcery(
            name="Big Sorcery",
            mana_cost=ManaCost.parse("{4}{R}{R}"),
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[big_spell], mana={ManaType.RED: 2, ManaType.COLORLESS: 4})

        from test_utils import cast_spell
        cast_spell(game, 0, "Big Sorcery")

        # Maestro gets +1/+1 counter → power 3, then adds 3 {R}
        red_in_pool = p1.mana_pool.get(ManaType.RED)
        assert red_in_pool == 3

    def test_mana_reflects_current_power_with_existing_counters(self) -> None:
        """Mana generated should use the creature's power AFTER the new counter."""
        game = create_game()
        p1 = game.players[0]

        maestro = MoltenCoreMaestro(owner=p1, controller=p1)
        # Pre-existing counter: power starts at 3
        maestro.plus_one_counters = 1
        maestro._base_plus_one_counters = 1
        game.get_battlefield(p1).add(maestro)
        maestro.register_triggers(game)

        big_spell = Sorcery(
            name="Expensive Spell",
            mana_cost=ManaCost.parse("{3}{R}{R}"),
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[big_spell], mana={ManaType.RED: 2, ManaType.COLORLESS: 3})

        from test_utils import cast_spell
        cast_spell(game, 0, "Expensive Spell")

        # Power was 3 (2 base + 1 counter), then gets another +1/+1 → power 4
        # Should add 4 {R}
        red_in_pool = p1.mana_pool.get(ManaType.RED)
        assert red_in_pool == 4

    def test_four_mana_spell_no_bonus(self) -> None:
        """Exactly 4 mana spent should NOT trigger the bonus (need 5+)."""
        game = create_game()
        p1 = game.players[0]

        maestro = MoltenCoreMaestro(owner=p1, controller=p1)
        game.get_battlefield(p1).add(maestro)
        maestro.register_triggers(game)

        spell = Instant(
            name="Medium Spell",
            mana_cost=ManaCost.parse("{3}{R}"),
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[spell], mana={ManaType.RED: 1, ManaType.COLORLESS: 3})

        from test_utils import cast_spell
        cast_spell(game, 0, "Medium Spell")

        # Counter is added (power -> 3) but no mana bonus
        red_in_pool = p1.mana_pool.get(ManaType.RED)
        assert red_in_pool == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestOpusEdgeCases:
    """Edge cases for the Opus ability."""

    def test_opponent_instant_does_not_trigger(self) -> None:
        """Opponent casting an instant should NOT trigger your Maestro."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        maestro = MoltenCoreMaestro(owner=p1, controller=p1)
        game.get_battlefield(p1).add(maestro)
        maestro.register_triggers(game)

        opp_bolt = Instant(
            name="Opponent Bolt",
            mana_cost=ManaCost.parse("{R}"),
            owner=p2,
            controller=p2,
        )
        set_board_state(game, 1, hand=[opp_bolt], mana={ManaType.RED: 1})

        counters_before = maestro.plus_one_counters
        from test_utils import cast_spell
        cast_spell(game, 1, "Opponent Bolt")

        assert maestro.plus_one_counters == counters_before

    def test_power_increases_affect_subsequent_mana_generation(self) -> None:
        """After multiple counters, mana generation uses updated power."""
        game = create_game()
        p1 = game.players[0]

        maestro = MoltenCoreMaestro(owner=p1, controller=p1)
        game.get_battlefield(p1).add(maestro)
        maestro.register_triggers(game)

        # Cast a cheap spell first to get a counter
        cheap = Instant(
            name="Opt",
            mana_cost=ManaCost.parse("{U}"),
            owner=p1,
            controller=p1,
        )
        # Then cast a 5+ mana spell
        expensive = Sorcery(
            name="Big Finish",
            mana_cost=ManaCost.parse("{4}{R}"),
            owner=p1,
            controller=p1,
        )
        set_board_state(
            game, 0,
            hand=[cheap, expensive],
            mana={ManaType.BLUE: 1, ManaType.RED: 1, ManaType.COLORLESS: 4},
        )

        from test_utils import cast_spell
        cast_spell(game, 0, "Opt")
        # After Opt: maestro has 1 counter → power 3

        # Empty pool then give mana for expensive spell
        p1.mana_pool.empty()
        p1.mana_pool.add(ManaType.RED, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 4)

        cast_spell(game, 0, "Big Finish")
        # After Big Finish: maestro gets another counter → power 4
        # Mana bonus uses power 4 → adds 4 {R}
        red_in_pool = p1.mana_pool.get(ManaType.RED)
        assert red_in_pool == 4
