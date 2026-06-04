"""Tests for SOS 1 — The Dawning Archaic (graveyard affinity + attack free-cast)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.casting import CastingError
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from engine.zones import move_to_zone
from test_utils import TestSetupError as _TestSetupError
from test_utils import (
    _resolve_top_of_stack,
    cast_spell,
    create_game,
    declare_attackers,
    set_board_state,
)


class _Spark(Instant):
    """No-target test instant; resolving it is a no-op (something to recast)."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Spark")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        pass


def _sorcery(name: str) -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse("{1}"))


def _instant(name: str) -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{1}"))


class TestDawningArchaicProperties:
    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_power_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7 and card.base_toughness == 7

    def test_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords

    def test_legendary_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert CardType.CREATURE in card.card_types


class TestDawningArchaicCostReduction:
    def test_reduced_by_instants_and_sorceries_in_graveyard(self) -> None:
        archaic = TheDawningArchaic(owner=None)
        game = create_game()
        p1, _ = game.players
        # 3 I/S in graveyard -> {10} costs {7}.
        gy = [_sorcery("S1"), _instant("I1"), _sorcery("S2")]
        set_board_state(game, 0, hand=[archaic], graveyard=gy,
                        mana={ManaType.COLORLESS: 7})
        cast_spell(game, 0, "The Dawning Archaic")
        _resolve_top_of_stack(game)
        assert archaic in game.get_battlefield(p1).get_all()

    def test_not_reduced_below_full_cost_without_graveyard(self) -> None:
        archaic = TheDawningArchaic(owner=None)
        game = create_game()
        # Empty graveyard -> full {10}; only 7 mana available -> cannot pay.
        set_board_state(game, 0, hand=[archaic], graveyard=[],
                        mana={ManaType.COLORLESS: 7})
        try:
            cast_spell(game, 0, "The Dawning Archaic")
        except (CastingError, _TestSetupError):
            pass
        else:
            raise AssertionError("expected failure — cost should not be reduced")


class TestDawningArchaicAttackTrigger:
    def _attack(self, game, archaic) -> None:
        move_to_zone(game, archaic, Zone.HAND, Zone.BATTLEFIELD)
        archaic.summoning_sick = False
        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_top_of_stack(game)

    def test_free_casts_and_exiles_the_spell(self) -> None:
        archaic = TheDawningArchaic(owner=None)
        spark = _Spark(owner=None)
        # Script: yes to the trigger, then choose Spark to recast.
        game = create_game(scripts=([True, spark], []))
        p1, _ = game.players
        set_board_state(game, 0, hand=[archaic], graveyard=[spark])
        self._attack(game, archaic)
        # Spark was cast for free and, on resolution, exiled instead of
        # returning to the graveyard.
        assert spark in game.players[0].zones[Zone.EXILE].get_all()
        assert spark not in game.get_graveyard(p1).get_all()

    def test_decline_leaves_spell_in_graveyard(self) -> None:
        archaic = TheDawningArchaic(owner=None)
        spark = _Spark(owner=None)
        game = create_game(scripts=([False], []))
        p1, _ = game.players
        set_board_state(game, 0, hand=[archaic], graveyard=[spark])
        self._attack(game, archaic)
        assert spark in game.get_graveyard(p1).get_all()
        assert spark not in game.players[0].zones[Zone.EXILE].get_all()

    def test_no_instant_or_sorcery_no_effect(self) -> None:
        archaic = TheDawningArchaic(owner=None)
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        game = create_game(scripts=([], []))
        p1, _ = game.players
        # Only a creature card in the graveyard -> no castable target.
        set_board_state(game, 0, hand=[archaic], graveyard=[creature])
        self._attack(game, archaic)
        assert creature in game.get_graveyard(p1).get_all()
        assert game.stack.is_empty()
