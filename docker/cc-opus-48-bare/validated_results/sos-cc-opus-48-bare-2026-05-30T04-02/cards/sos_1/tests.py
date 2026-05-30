"""Tests for SOS 1 — The Dawning Archaic (cost reduction + attack recast)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Instant
from engine.events import AttacksTriggeredEvent
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    TargetRequirement,
    Zone,
)
from test_utils import cast_spell, create_game, set_board_state


class _Zap(Instant):
    """Test instant: deal 3 damage to the chosen target (any target)."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: True,
                description="any target",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        targets = getattr(self, "chosen_targets", None) or []
        if targets:
            deal_damage(game, self, targets[0], 3)


def _resolve_all(game: Any) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestArchaicProperties:
    def test_name(self) -> None:
        assert TheDawningArchaic().name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic().mana_cost == ManaCost.parse("{10}")

    def test_power_toughness(self) -> None:
        c = TheDawningArchaic()
        assert c.base_power == 7
        assert c.base_toughness == 7

    def test_keywords_and_types(self) -> None:
        c = TheDawningArchaic()
        assert Keyword.REACH in c.keywords
        assert CardType.CREATURE in c.card_types
        assert Supertype.LEGENDARY in c.supertypes
        assert "Avatar" in c.subtypes


class TestArchaicCostReduction:
    def test_reduction_counts_instants_and_sorceries(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        gy = [_Zap(owner=p1, controller=p1) for _ in range(3)]
        set_board_state(game, 0, graveyard=gy)
        assert archaic.cost_reduction(game) == 3

    def test_casts_for_reduced_cost(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        gy = [_Zap(owner=p1, controller=p1) for _ in range(4)]
        # {10} - 4 instants = {6}; provide exactly 6 mana.
        set_board_state(
            game, 0, hand=[archaic], graveyard=gy, mana={ManaType.COLORLESS: 6}
        )
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(p1).contains(archaic)


class TestArchaicAttackRecast:
    def _setup(self):
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        zap = _Zap(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[zap])
        archaic.register_triggers(game)
        return game, p1, p2, archaic, zap

    def test_recast_from_graveyard_exiles_after(self) -> None:
        game, p1, p2, archaic, zap = self._setup()
        # Script: yes, choose zap, then target p2 for the zap.
        p1._script.extend([True, zap, p2])
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        )
        _resolve_all(game)
        # Zap dealt 3 damage and was exiled (not put in graveyard).
        assert p2.life == 17
        assert p1.zones[Zone.EXILE].contains(zap)
        assert not game.get_graveyard(p1).contains(zap)

    def test_decline_leaves_card_in_graveyard(self) -> None:
        game, p1, p2, archaic, zap = self._setup()
        p1._script.extend([False])
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        )
        _resolve_all(game)
        assert p2.life == 20
        assert game.get_graveyard(p1).contains(zap)
        assert not p1.zones[Zone.EXILE].contains(zap)

    def test_no_trigger_for_other_attacker(self) -> None:
        game, p1, p2, archaic, zap = self._setup()
        from engine.card import Creature

        other = Creature(
            name="Other", owner=p1, controller=p1, base_power=2, base_toughness=2
        )
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=other, attacker=other)
        )
        # Archaic's trigger should not fire for a different attacker.
        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(zap)
