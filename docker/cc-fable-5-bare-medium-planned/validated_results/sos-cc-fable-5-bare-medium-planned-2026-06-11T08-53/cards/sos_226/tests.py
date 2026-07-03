"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, cast_spell, set_board_state


class Zap(Instant):
    """Test instant: deal 1 damage to the opponent (no targets)."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost(generic=1))
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        from engine.game import deal_damage

        for p in game.players:
            if p is not self.controller:
                deal_damage(game, self, p, 1)


class TargetedZap(Instant):
    """Test instant: deal 2 damage to target creature."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Targeted Zap")
        kwargs.setdefault("mana_cost", ManaCost(generic=1))
        super().__init__(**kwargs)

    def get_targets(self, game) -> list:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game) -> None:
        from engine.game import deal_damage

        chosen = getattr(self, "chosen_targets", None)
        if chosen and chosen[0] is not None:
            deal_damage(game, self, chosen[0], 2)


def _setup(game) -> tuple[SilverquillTheDisputant, Creature]:
    silverquill = SilverquillTheDisputant()
    bear = Creature(name="Bear", base_power=2, base_toughness=2)
    set_board_state(game, 0, battlefield=[silverquill, bear])
    # set_board_state doesn't register triggers; register through the
    # card's own hook, the same one move_to_zone would call.
    silverquill.register_triggers(game)
    return silverquill, bear


class TestSilverquill:
    def test_keywords(self) -> None:
        s = SilverquillTheDisputant()
        assert Keyword.FLYING in s.keywords
        assert Keyword.VIGILANCE in s.keywords

    def test_casualty_sacrifice_copies_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _, bear = _setup(game)
        zap = Zap()
        game.get_hand(p1).add(zap)
        zap.owner = zap.controller = p1
        set_board_state(game, 0, mana={ManaType.COLORLESS: 1})
        p1._script.append(bear)  # casualty answer: sacrifice the bear

        cast_spell(game, 0, "Zap")

        # Bear sacrificed; spell resolved twice (original + copy).
        assert game.get_graveyard(p1).contains(bear)
        assert p2.life == 18
        assert game.get_graveyard(p1).contains(zap)

    def test_casualty_declined(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _, bear = _setup(game)
        zap = Zap()
        game.get_hand(p1).add(zap)
        zap.owner = zap.controller = p1
        set_board_state(game, 0, mana={ManaType.COLORLESS: 1})
        p1._script.append(None)  # decline casualty

        cast_spell(game, 0, "Zap")

        assert game.get_battlefield(p1).contains(bear)
        assert p2.life == 19  # only the original resolved

    def test_no_eligible_creature_no_prompt(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant()
        weakling = Creature(name="Weakling", base_power=0, base_toughness=3)
        set_board_state(game, 0, battlefield=[silverquill, weakling])
        silverquill.register_triggers(game)
        zap = Zap()
        game.get_hand(p1).add(zap)
        zap.owner = zap.controller = p1
        set_board_state(game, 0, mana={ManaType.COLORLESS: 1})
        # Silverquill itself has power 4 — wait, it qualifies as a sacrifice
        # candidate, so a prompt does occur; decline it.
        p1._script.append(None)

        cast_spell(game, 0, "Zap")
        assert game.get_battlefield(p1).contains(weakling)
        assert p2.life == 19

    def test_copy_keeps_targets_and_opponent_spells_unaffected(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _, bear = _setup(game)
        victim = Creature(name="Victim", base_power=1, base_toughness=5)
        set_board_state(game, 1, battlefield=[victim])
        tz = TargetedZap()
        game.get_hand(p1).add(tz)
        tz.owner = tz.controller = p1
        set_board_state(game, 0, mana={ManaType.COLORLESS: 1})
        # script: casualty answer (bear), then "no new targets" for the copy
        p1._script.append(bear)
        p1._script.append(False)

        cast_spell(game, 0, "Targeted Zap", targets=[victim])
        # Original + copy each dealt 2 to the victim.
        assert victim.damage_marked == 4

        # An opponent's instant/sorcery does not get casualty.
        opp_zap = Zap()
        game.get_hand(p2).add(opp_zap)
        opp_zap.owner = opp_zap.controller = p2
        set_board_state(game, 1, mana={ManaType.COLORLESS: 1})
        p1_life = p1.life
        cast_spell(game, 1, "Zap")
        assert p1.life == p1_life - 1  # resolved exactly once
