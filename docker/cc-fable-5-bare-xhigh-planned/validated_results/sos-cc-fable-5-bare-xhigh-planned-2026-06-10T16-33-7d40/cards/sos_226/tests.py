"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


class GainOne(Instant):
    """Test instant with no targets: you gain 1 life."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Gain One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 1


class Zap(Instant):
    """Test instant: deal 2 damage to target creature."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        chosen = getattr(self, "chosen_targets", None)
        if chosen and chosen[0] is not None:
            deal_damage(game, self, chosen[0], 2)


def _setup(scripts, battlefield_extra=None, hand=None, mana=None):
    game = create_game(scripts=scripts)
    sq = SilverquillTheDisputant(owner=None)
    bf = [sq] + (battlefield_extra or [])
    set_board_state(game, 0, battlefield=bf, hand=hand or [], mana=mana or {})
    sq.register_triggers(game)
    return game, sq


class TestSilverquillProperties:
    def test_static_data(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert card.base_power == 4 and card.base_toughness == 4


class TestCasualty:
    def test_sacrifice_copies_the_spell(self) -> None:
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, sq = _setup(
            scripts=([bear], []),
            battlefield_extra=[bear],
            hand=[GainOne(owner=None)],
            mana={ManaType.WHITE: 1},
        )
        p0 = game.players[0]
        cast_spell(game, 0, "Gain One")
        # Copy + original both resolved: +2 life; bear sacrificed.
        assert p0.life == 22
        assert bear in p0.zones[Zone.GRAVEYARD].get_all()
        assert bear not in p0.zones[Zone.BATTLEFIELD].get_all()
        assert game.stack.is_empty()

    def test_decline_no_copy(self) -> None:
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, sq = _setup(
            scripts=([None], []),
            battlefield_extra=[bear],
            hand=[GainOne(owner=None)],
            mana={ManaType.WHITE: 1},
        )
        p0 = game.players[0]
        cast_spell(game, 0, "Gain One")
        assert p0.life == 21
        assert bear in p0.zones[Zone.BATTLEFIELD].get_all()

    def test_silverquill_itself_can_be_the_casualty(self) -> None:
        # Only other creature is a 0-power wall (not a legal casualty);
        # Silverquill (4 power) is, and is scripted as the sacrifice.
        wall = Creature(name="Wall", base_power=0, base_toughness=3)
        game, sq = _setup(
            scripts=([], []),
            battlefield_extra=[wall],
            hand=[GainOne(owner=None)],
            mana={ManaType.WHITE: 1},
        )
        game.players[0]._script.append(sq)
        p0 = game.players[0]
        cast_spell(game, 0, "Gain One")
        assert p0.life == 22
        assert sq in p0.zones[Zone.GRAVEYARD].get_all()
        assert wall in p0.zones[Zone.BATTLEFIELD].get_all()

    def test_creature_spells_do_not_get_casualty(self) -> None:
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        newbear = Creature(
            name="NewBear", base_power=2, base_toughness=2,
            mana_cost=ManaCost.parse("{G}"),
        )
        game, sq = _setup(
            scripts=([], []),
            battlefield_extra=[bear],
            hand=[newbear],
            mana={ManaType.GREEN: 1},
        )
        cast_spell(game, 0, "NewBear")
        p0 = game.players[0]
        assert bear in p0.zones[Zone.BATTLEFIELD].get_all()
        bf_names = [c.name for c in p0.zones[Zone.BATTLEFIELD].get_all()]
        assert "NewBear" in bf_names

    def test_copy_may_choose_new_targets(self) -> None:
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        ox_a = Creature(name="OxA", base_power=3, base_toughness=3)
        ox_b = Creature(name="OxB", base_power=3, base_toughness=3)
        # p0 script (consumed during trigger resolution):
        # choose_card -> bear (sacrifice), choose_yes_no -> True,
        # choose_target -> ox_b (new target for the copy).
        game, sq = _setup(
            scripts=([bear, True, ox_b], []),
            battlefield_extra=[bear],
            hand=[Zap(owner=None)],
            mana={ManaType.RED: 1},
        )
        set_board_state(game, 1, battlefield=[ox_a, ox_b])
        cast_spell(game, 0, "Zap", targets=[ox_a])
        # Copy (new target OxB) resolves first, then the original hits OxA.
        assert ox_a.damage_marked == 2
        assert ox_b.damage_marked == 2

    def test_opponent_spells_do_not_trigger(self) -> None:
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, sq = _setup(scripts=([], []), battlefield_extra=[bear])
        set_board_state(
            game, 1, hand=[GainOne(owner=None)], mana={ManaType.WHITE: 1}
        )
        p1 = game.players[1]
        cast_spell(game, 1, "Gain One")
        assert p1.life == 21
        assert bear in game.players[0].zones[Zone.BATTLEFIELD].get_all()
