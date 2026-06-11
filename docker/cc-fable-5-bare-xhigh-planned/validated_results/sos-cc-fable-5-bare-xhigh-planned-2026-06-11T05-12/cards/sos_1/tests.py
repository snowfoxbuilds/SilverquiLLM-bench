"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, declare_attackers, set_board_state


class Zap(Instant):
    """Probe instant: deal 2 damage to any target."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    hasattr(obj, "life")
                    or CardType.CREATURE in getattr(obj, "card_types", set())
                ),
                description="any target",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        chosen = getattr(self, "chosen_targets", None) or [None]
        if chosen[0] is not None:
            deal_damage(game, self, chosen[0], 2)


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
        """3 instants in graveyard (plus a creature that doesn't count) → {7}."""
        game = create_game()
        archaic = TheDawningArchaic()
        filler_creature = Creature(name="Dead Bear", base_power=2, base_toughness=2)
        set_board_state(
            game, 0,
            hand=[archaic],
            graveyard=[Zap(), Zap(), Zap(), filler_creature],
            mana={ManaType.COLORLESS: 7},
        )
        from test_utils import cast_spell

        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(game.players[0]).contains(archaic)
        assert game.players[0].mana_pool.total() == 0

    def test_reduction_clamps_at_zero_generic(self) -> None:
        """12 instants in graveyard → castable for nothing."""
        game = create_game()
        archaic = TheDawningArchaic()
        set_board_state(
            game, 0,
            hand=[archaic],
            graveyard=[Zap() for _ in range(12)],
        )
        from test_utils import cast_spell

        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(game.players[0]).contains(archaic)


class TestAttackTrigger:
    def _setup(self, graveyard: list[Any], p1_script: list[Any],
               p2_script: list[Any]) -> Any:
        game = create_game(scripts=(p1_script, p2_script))
        archaic = TheDawningArchaic()
        set_board_state(game, 0, battlefield=[archaic], graveyard=graveyard)
        archaic.register_triggers(game)
        archaic.summoning_sick = False
        return game, archaic

    def test_attack_casts_sole_spell_free_and_exiles_it(self) -> None:
        """One candidate auto-selected, cast for free, exiled after resolving."""
        zap = Zap()
        game, archaic = self._setup(
            graveyard=[zap],
            # pass (trigger on stack), target for Zap, pass (Zap on stack)
            p1_script=["pass", None, "pass"],
            p2_script=["pass", "pass"],
        )
        p1, p2 = game.players
        # Script the Zap target as p2 (replace placeholder).
        p1._script[1] = p2
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        assert p2.life == 18
        assert p1.zones[Zone.EXILE].contains(zap)
        assert not p1.zones[Zone.GRAVEYARD].contains(zap)

    def test_attack_with_empty_graveyard_is_noop(self) -> None:
        game, archaic = self._setup(
            graveyard=[],
            p1_script=["pass"],
            p2_script=["pass"],
        )
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        assert game.players[1].life == 20
        assert game.stack.is_empty()

    def test_may_decline_with_multiple_candidates(self) -> None:
        """choose_card returning None declines; spells stay in graveyard."""
        zap1, zap2 = Zap(), Zap()
        game, archaic = self._setup(
            graveyard=[zap1, zap2],
            p1_script=["pass", None],  # pass priority, then decline the cast
            p2_script=["pass"],
        )
        p1 = game.players[0]
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        assert p1.zones[Zone.GRAVEYARD].contains(zap1)
        assert p1.zones[Zone.GRAVEYARD].contains(zap2)
        assert len(p1.zones[Zone.EXILE]) == 0
