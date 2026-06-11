"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import cast_spell, create_game, declare_attackers, set_board_state


class TestProperties:
    def test_static_data(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")
        assert card.base_power == 7 and card.base_toughness == 7
        assert Keyword.REACH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes


class TestCostReduction:
    def test_one_less_per_instant_sorcery_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic()
        set_board_state(
            game, 0,
            hand=[card],
            graveyard=[
                Instant(name="I1", mana_cost=ManaCost.parse("{U}")),
                Sorcery(name="S1", mana_cost=ManaCost.parse("{R}")),
                Instant(name="I2", mana_cost=ManaCost.parse("{U}")),
                Creature(name="Dead Bear", base_power=2, base_toughness=2),
            ],
        )
        assert get_cost_reduction(game, card, p1) == 3

        # End to end: {10} - 3 = {7}
        set_board_state(game, 0, mana={ManaType.COLORLESS: 7})
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(p1).contains(card)
        assert p1.mana_pool.total() == 0

    def test_reduction_clamps_at_zero_generic(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic()
        graveyard = [
            Instant(name=f"I{i}", mana_cost=ManaCost.parse("{U}"))
            for i in range(12)
        ]
        set_board_state(game, 0, hand=[card], graveyard=graveyard)
        assert get_cost_reduction(game, card, p1) == 10  # clamped to generic

        cast_spell(game, 0, "The Dawning Archaic")  # free
        assert game.get_battlefield(p1).contains(card)


class TestAttackTrigger:
    def test_cast_from_graveyard_then_exile_instead(self) -> None:
        game = create_game(
            scripts=(["pass", True, "pass"], ["pass", "pass"]),
        )
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        spark = Instant(name="Spark", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spark])
        archaic.summoning_sick = False
        archaic.register_triggers(game)  # set_board_state skips ETB hooks

        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)  # resolve attack trigger, then the free spell

        assert game.get_exile(p1).contains(spark)       # exiled instead
        assert not game.get_graveyard(p1).contains(spark)
        assert game.stack.is_empty()

    def test_may_decline_leaves_spell_in_graveyard(self) -> None:
        game = create_game(
            scripts=(["pass", False], ["pass"]),
        )
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        spark = Instant(name="Spark", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spark])
        archaic.summoning_sick = False
        archaic.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)

        assert game.get_graveyard(p1).contains(spark)
        assert not game.get_exile(p1).contains(spark)

    def test_empty_graveyard_no_prompt(self) -> None:
        game = create_game(scripts=(["pass"], ["pass"]))
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        set_board_state(game, 0, battlefield=[archaic], graveyard=[])
        archaic.summoning_sick = False
        archaic.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)  # trigger resolves with no legal target — no-op

        assert game.stack.is_empty()
        # No script answers beyond the priority passes were consumed.
        assert p1.remaining_choices == 0
