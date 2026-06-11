"""Tests for SOS 226 — Silverquill, the Disputant (casualty 1 via E1 + copy)."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import (
    CardType, Keyword, ManaCost, ManaType, Supertype, TargetRequirement, Zone,
)
from test_utils import create_game, cast_spell, set_board_state


class Bolt(Instant):
    """Deal 3 damage to target player."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game):
        return [TargetRequirement(
            filter_fn=lambda o: o in game.players,
            description="target player", zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game):
        from engine.game import deal_damage
        t = (getattr(self, "chosen_targets", None) or [None])[0]
        if t is not None:
            deal_damage(game, self, t, 3)


def _setup(p0_battlefield):
    game = create_game()
    p0, p1 = game.players
    sq = SilverquillTheDisputant(owner=None)
    set_board_state(game, 0, battlefield=[sq] + p0_battlefield)
    sq.register_triggers(game)
    return game, p0, p1, sq


class TestProperties:
    def test_basic(self):
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert card.base_power == 4 and card.base_toughness == 4
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert Supertype.LEGENDARY in card.supertypes


class TestCasualty:
    def test_pay_casualty_copies_spell(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p0, p1, sq = _setup([bear])
        set_board_state(game, 0, hand=[Bolt(owner=None)], mana={ManaType.RED: 1})
        p0._script.append(bear)  # casualty: sacrifice the bear
        cast_spell(game, 0, "Bolt", targets=[p1])
        assert p1.life == 14  # 3 + 3 (copy)
        assert game.get_graveyard(p0).contains(bear)

    def test_decline_casualty(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p0, p1, sq = _setup([bear])
        set_board_state(game, 0, hand=[Bolt(owner=None)], mana={ManaType.RED: 1})
        p0._script.append(None)  # decline
        cast_spell(game, 0, "Bolt", targets=[p1])
        assert p1.life == 17  # only the original resolved
        assert game.get_battlefield(p0).contains(bear)

    def test_power_zero_creature_cannot_pay(self):
        wall = Creature(name="Wall", base_power=0, base_toughness=3)
        game, p0, p1, sq = _setup([wall])
        set_board_state(game, 0, hand=[Bolt(owner=None)], mana={ManaType.RED: 1})
        p0._script.append(wall)  # illegal: power 0 — must be rejected
        cast_spell(game, 0, "Bolt", targets=[p1])
        assert p1.life == 17
        assert game.get_battlefield(p0).contains(wall)

    def test_opponent_cast_has_no_casualty(self):
        game, p0, p1, sq = _setup([])
        set_board_state(game, 1, hand=[Bolt(owner=None)], mana={ManaType.RED: 1})
        cast_spell(game, 1, "Bolt", targets=[p0])
        assert p0.life == 17  # no copy — Silverquill belongs to p0, not p1

    def test_can_sacrifice_self(self):
        # With only Silverquill in play, it is itself a legal casualty.
        game, p0, p1, sq = _setup([])
        set_board_state(game, 0, hand=[Bolt(owner=None)], mana={ManaType.RED: 1})
        p0._script.append(sq)  # sacrifice Silverquill itself
        cast_spell(game, 0, "Bolt", targets=[p1])
        assert p1.life == 14  # copy still made (casualty paid before resolve)
        assert game.get_graveyard(p0).contains(sq)
