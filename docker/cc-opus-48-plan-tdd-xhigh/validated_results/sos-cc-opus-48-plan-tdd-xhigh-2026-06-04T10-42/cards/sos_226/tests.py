"""Tests for SOS 226 — Silverquill, the Disputant (casualty 1 on I/S)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import cast_spell, create_game, set_board_state


class _Bolt(Instant):
    """Test instant: deal 2 damage to target player on resolve."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{0}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list[Any]:
        from engine.types import TargetRequirement

        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        chosen = getattr(self, "chosen_targets", None) or []
        if chosen:
            deal_damage(game, self, chosen[0], 2)


class TestSilverquillProperties:
    def test_is_creature(self) -> None:
        assert isinstance(SilverquillTheDisputant(owner=None), Creature)

    def test_name(self) -> None:
        assert SilverquillTheDisputant(owner=None).name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        assert SilverquillTheDisputant(owner=None).mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_pt(self) -> None:
        c = SilverquillTheDisputant(owner=None)
        assert c.base_power == 4
        assert c.base_toughness == 4

    def test_keywords(self) -> None:
        c = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in c.keywords
        assert Keyword.VIGILANCE in c.keywords

    def test_legendary_dragon(self) -> None:
        c = SilverquillTheDisputant(owner=None)
        assert Supertype.LEGENDARY in c.supertypes
        assert "Dragon" in c.subtypes
        assert "Elder" in c.subtypes


def _bear(name: str = "Bear") -> Creature:
    b = Creature(name=name, base_power=2, base_toughness=2)
    b.card_types = {CardType.CREATURE}
    return b


class TestSilverquillCasualty:
    def test_sacrifice_copies_spell(self) -> None:
        # caster scripts: yes-to-casualty, then choose the bear as victim.
        game = create_game(scripts=([True, None], []))
        p0, p1 = game.players
        silver = SilverquillTheDisputant(owner=p0, controller=p0)
        bear = _bear()
        set_board_state(game, 0, battlefield=[silver, bear], hand=[_Bolt(owner=p0, controller=p0)])
        silver.register_triggers(game)
        # Fix the victim reference now that the bear has been placed.
        p0._script[1] = bear

        cast_spell(game, 0, "Bolt", targets=[p1])

        # Original + copy each deal 2 → 4 total.
        assert p1.life == 16
        # The bear was sacrificed.
        assert game.get_graveyard(p0).contains(bear)
        assert not game.get_battlefield(p0).contains(bear)

    def test_decline_casualty_no_copy(self) -> None:
        game = create_game(scripts=([False], []))
        p0, p1 = game.players
        silver = SilverquillTheDisputant(owner=p0, controller=p0)
        bear = _bear()
        set_board_state(game, 0, battlefield=[silver, bear], hand=[_Bolt(owner=p0, controller=p0)])
        silver.register_triggers(game)

        cast_spell(game, 0, "Bolt", targets=[p1])

        # Only the original resolved → 2 damage.
        assert p1.life == 18
        assert game.get_battlefield(p0).contains(bear)
