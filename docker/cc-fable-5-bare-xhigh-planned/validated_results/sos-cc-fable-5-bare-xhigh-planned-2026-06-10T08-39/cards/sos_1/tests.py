"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from engine.card import Creature, Instant, Sorcery
from engine.stack import priority_loop
from engine.types import Keyword, ManaType, Zone
from cards.sos.sos_1.card_impl import TheDawningArchaic
from test_utils import create_game, declare_attackers, set_board_state


class TestCostReduction:
    def test_reduced_by_graveyard_instants_and_sorceries(self) -> None:
        """4 instant/sorcery cards in graveyard → castable for {6}."""
        game = create_game()
        card = TheDawningArchaic()
        gy = [Instant(name=f"I{i}") for i in range(2)] + [
            Sorcery(name=f"S{i}") for i in range(2)
        ]
        set_board_state(game, 0, hand=[card], graveyard=gy,
                        mana={ManaType.COLORLESS: 6})
        from test_utils import cast_spell
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.players[0].zones[Zone.BATTLEFIELD].contains(card)
        assert game.players[0].mana_pool.total() == 0

    def test_non_spell_cards_do_not_reduce(self) -> None:
        """Creature cards in the graveyard don't reduce the cost."""
        game = create_game()
        card = TheDawningArchaic()
        gy = [Creature(name="Dead Bear", base_power=2, base_toughness=2)]
        set_board_state(game, 0, hand=[card], graveyard=gy,
                        mana={ManaType.COLORLESS: 9})
        from test_utils import cast_spell, TestSetupError
        import pytest
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "The Dawning Archaic")

    def test_reduction_clamps_at_zero_generic(self) -> None:
        """12 spells in graveyard → whole {10} cost is reduced away."""
        game = create_game()
        card = TheDawningArchaic()
        gy = [Instant(name=f"I{i}") for i in range(12)]
        set_board_state(game, 0, hand=[card], graveyard=gy, mana={})
        from test_utils import cast_spell
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.players[0].zones[Zone.BATTLEFIELD].contains(card)

    def test_has_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic().keywords


class TestAttackTrigger:
    def test_attack_casts_sole_spell_from_graveyard_then_exiles_it(self) -> None:
        """Single instant in graveyard is auto-cast for free; after it
        resolves it goes to exile instead of the graveyard."""
        game = create_game(scripts=(["pass"] * 6, ["pass"] * 6))
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        spark = Instant(name="Spark")
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spark])
        archaic.summoning_sick = False
        archaic.register_triggers(game)
        declare_attackers(game, ["The Dawning Archaic"])
        # attack trigger is on the stack; resolve everything
        priority_loop(game)
        assert p1.zones[Zone.EXILE].contains(spark)
        assert not p1.zones[Zone.GRAVEYARD].contains(spark)

    def test_attack_with_empty_graveyard_does_nothing(self) -> None:
        game = create_game(scripts=(["pass"] * 4, ["pass"] * 4))
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        set_board_state(game, 0, battlefield=[archaic])
        archaic.summoning_sick = False
        archaic.register_triggers(game)
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        assert len(p1.zones[Zone.EXILE]) == 0
        assert len(p1.zones[Zone.GRAVEYARD]) == 0

    def test_attack_choice_among_multiple_spells(self) -> None:
        """With two candidates the controller picks one; the other stays."""
        spark = Instant(name="Spark")
        bolt = Instant(name="Bolt")
        # p1 script: pass on the trigger, then the choose_card answer, then passes
        game = create_game(scripts=(["pass", bolt] + ["pass"] * 6, ["pass"] * 6))
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spark, bolt])
        archaic.summoning_sick = False
        archaic.register_triggers(game)
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        assert p1.zones[Zone.EXILE].contains(bolt)
        assert p1.zones[Zone.GRAVEYARD].contains(spark)

    def test_decline_keeps_spell_in_graveyard(self) -> None:
        """Returning None from the choice declines the 'may' cast."""
        spark = Instant(name="Spark")
        bolt = Instant(name="Bolt")
        game = create_game(scripts=(["pass", None] + ["pass"] * 4, ["pass"] * 4))
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spark, bolt])
        archaic.summoning_sick = False
        archaic.register_triggers(game)
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        assert p1.zones[Zone.GRAVEYARD].contains(spark)
        assert p1.zones[Zone.GRAVEYARD].contains(bolt)
        assert len(p1.zones[Zone.EXILE]) == 0
