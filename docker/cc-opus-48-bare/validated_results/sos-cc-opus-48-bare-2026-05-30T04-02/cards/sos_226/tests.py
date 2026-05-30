"""Tests for SOS 226 — Silverquill, the Disputant (casualty granting)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
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


class TestSilverquillProperties:
    def test_name(self) -> None:
        assert SilverquillTheDisputant().name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        assert SilverquillTheDisputant().mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_power_toughness(self) -> None:
        c = SilverquillTheDisputant()
        assert c.base_power == 4
        assert c.base_toughness == 4

    def test_keywords(self) -> None:
        c = SilverquillTheDisputant()
        assert Keyword.FLYING in c.keywords
        assert Keyword.VIGILANCE in c.keywords

    def test_types(self) -> None:
        c = SilverquillTheDisputant()
        assert CardType.CREATURE in c.card_types
        assert Supertype.LEGENDARY in c.supertypes
        assert {"Elder", "Dragon"} <= c.subtypes


class TestSilverquillCasualty:
    def _setup(self, use_casualty: bool):
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        silver = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Fodder", owner=p1, controller=p1, base_power=1, base_toughness=1
        )
        fodder.card_types = {CardType.CREATURE}
        zap = _Zap(owner=p1, controller=p1)
        set_board_state(
            game, 0, battlefield=[silver, fodder], hand=[zap], mana={ManaType.RED: 1}
        )
        # set_board_state doesn't register triggers; do it explicitly.
        silver.register_triggers(game)
        # Script casualty decision: yes/no then which creature to sacrifice.
        if use_casualty:
            p1._script.extend([True, fodder])
        else:
            p1._script.extend([False])
        return game, p1, p2, silver, fodder, zap

    def test_casualty_copies_spell(self) -> None:
        game, p1, p2, silver, fodder, zap = self._setup(use_casualty=True)
        cast_spell(game, 0, "Zap", targets=[p2])
        # Original + copy each deal 3 → 6 total.
        assert p2.life == 14
        # Fodder was sacrificed.
        assert not game.get_battlefield(p1).contains(fodder)
        assert game.get_graveyard(p1).contains(fodder)

    def test_casualty_declined(self) -> None:
        game, p1, p2, silver, fodder, zap = self._setup(use_casualty=False)
        cast_spell(game, 0, "Zap", targets=[p2])
        # Only the original resolves → 3 damage.
        assert p2.life == 17
        assert game.get_battlefield(p1).contains(fodder)

    def test_no_casualty_without_silverquill(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        zap = _Zap(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[zap], mana={ManaType.RED: 1})
        cast_spell(game, 0, "Zap", targets=[p2])
        assert p2.life == 17
