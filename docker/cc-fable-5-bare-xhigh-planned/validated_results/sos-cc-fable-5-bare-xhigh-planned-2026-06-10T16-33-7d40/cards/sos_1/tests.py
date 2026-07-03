"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import TestSetupError as SetupError
from test_utils import (
    cast_spell,
    create_game,
    create_game as _cg,
    declare_attackers,
    set_board_state,
)


def _vanilla_instant(name: str = "Spark") -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{R}"))


class TestTheDawningArchaicProperties:
    def test_static_data(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")
        assert Keyword.REACH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes
        assert card.base_power == 7 and card.base_toughness == 7


class TestCostReduction:
    def test_one_less_per_instant_sorcery_in_graveyard(self) -> None:
        game = create_game()
        set_board_state(
            game, 0,
            hand=[TheDawningArchaic(owner=None)],
            graveyard=[_vanilla_instant(f"I{i}") for i in range(4)]
            + [Creature(name="DeadBear", base_power=2, base_toughness=2)],
            mana={ManaType.COLORLESS: 6},
        )
        # {10} - 4 (creature card does not count) = {6}
        cast_spell(game, 0, "The Dawning Archaic")
        bf_names = [c.name for c in game.players[0].zones[Zone.BATTLEFIELD].get_all()]
        assert "The Dawning Archaic" in bf_names
        assert game.players[0].mana_pool.total() == 0

    def test_insufficient_mana_with_reduction_fails(self) -> None:
        game = create_game()
        set_board_state(
            game, 0,
            hand=[TheDawningArchaic(owner=None)],
            graveyard=[_vanilla_instant(f"I{i}") for i in range(4)],
            mana={ManaType.COLORLESS: 5},
        )
        with pytest.raises(SetupError):
            cast_spell(game, 0, "The Dawning Archaic")

    def test_reduction_clamps_at_zero(self) -> None:
        game = create_game()
        set_board_state(
            game, 0,
            hand=[TheDawningArchaic(owner=None)],
            graveyard=[_vanilla_instant(f"I{i}") for i in range(12)],
        )
        # 12 instants > {10}: cast for free, clamped at 0 (not negative).
        cast_spell(game, 0, "The Dawning Archaic")
        bf_names = [c.name for c in game.players[0].zones[Zone.BATTLEFIELD].get_all()]
        assert "The Dawning Archaic" in bf_names


class TestAttackTrigger:
    def _setup(self, graveyard, scripts):
        game = _cg(scripts=scripts)
        archaic = TheDawningArchaic(owner=None)
        set_board_state(game, 0, battlefield=[archaic], graveyard=graveyard)
        archaic.summoning_sick = False
        archaic.register_triggers(game)
        return game, archaic

    def test_attack_casts_only_instant_and_exiles_it(self) -> None:
        spark = _vanilla_instant()
        game, archaic = self._setup(
            [spark], (["pass", "pass"], ["pass", "pass"])
        )
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)

        p0 = game.players[0]
        assert spark in p0.zones[Zone.EXILE].get_all()
        assert spark not in p0.zones[Zone.GRAVEYARD].get_all()
        assert game.stack.is_empty()

    def test_attack_with_empty_graveyard_does_nothing(self) -> None:
        game, archaic = self._setup(
            [Creature(name="DeadBear", base_power=2, base_toughness=2)],
            (["pass", "pass"], ["pass", "pass"]),
        )
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        assert game.stack.is_empty()
        gy_names = [c.name for c in game.players[0].zones[Zone.GRAVEYARD].get_all()]
        assert gy_names == ["DeadBear"]

    def test_may_decline_with_multiple_candidates(self) -> None:
        a, b = _vanilla_instant("A"), _vanilla_instant("B")
        # p0 script: pass (priority), None (decline choose_card)
        game, archaic = self._setup(
            [a, b], (["pass", None], ["pass"])
        )
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        p0 = game.players[0]
        gy = p0.zones[Zone.GRAVEYARD].get_all()
        assert a in gy and b in gy
        assert len(p0.zones[Zone.EXILE]) == 0

    def test_chooses_among_multiple_candidates(self) -> None:
        a, b = _vanilla_instant("A"), _vanilla_instant("B")
        # p0 script: pass, choose b, then pass for the freecast spell
        game, archaic = self._setup(
            [a, b], (["pass", b, "pass"], ["pass", "pass"])
        )
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        p0 = game.players[0]
        assert b in p0.zones[Zone.EXILE].get_all()
        assert a in p0.zones[Zone.GRAVEYARD].get_all()
