"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, TargetRequirement, Zone
from test_utils import create_game, set_board_state, cast_spell


class LifeProbe(Instant):
    """Test-only untargeted instant: controller gains 1 life."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Life Probe")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 1


class ZapProbe(Instant):
    """Test-only targeted instant: deal 2 damage to any target."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap Probe")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    or hasattr(obj, "life")
                ),
                description="any target",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        chosen = getattr(self, "chosen_targets", None)
        if chosen and chosen[0] is not None:
            deal_damage(game, self, chosen[0], 2)


def _setup(game, extra_battlefield=None):
    sq = SilverquillTheDisputant(owner=None)
    bf = [sq] + (extra_battlefield or [])
    set_board_state(game, 0, battlefield=bf)
    sq.register_triggers(game)
    return sq


class TestSilverquillProperties:
    def test_static_data(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert card.base_power == 4 and card.base_toughness == 4
        assert Supertype.LEGENDARY in card.supertypes


class TestSilverquillCasualty:
    def test_sacrifice_copies_spell(self) -> None:
        """Sacrificing the bear doubles the (untargeted) spell's effect."""
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game = create_game(scripts=([bear], []))
        p1 = game.players[0]
        _setup(game, [bear])
        spell = LifeProbe()
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Life Probe")
        assert p1.life == 22  # original + copy
        assert game.get_graveyard(p1).contains(bear)
        assert not game.get_battlefield(p1).contains(bear)
        # The copy never becomes a card in any zone — only one Life Probe card.
        assert sum(1 for c in game.get_graveyard(p1).get_all()
                   if getattr(c, "name", "") == "Life Probe") == 1

    def test_decline_casualty(self) -> None:
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game = create_game(scripts=([None], []))
        p1 = game.players[0]
        _setup(game, [bear])
        spell = LifeProbe()
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Life Probe")
        assert p1.life == 21  # original only
        assert game.get_battlefield(p1).contains(bear)

    def test_no_eligible_creature_no_prompt(self) -> None:
        """No creature with power >= 1 → casualty cannot be taken, no prompt.

        Silverquill itself is normally eligible (power 4), so shrink it to
        power 0 with -1/-1 counters.
        """
        wall = Creature(name="Wall", base_power=0, base_toughness=4)
        game = create_game()  # empty scripts — any prompt would raise
        p1 = game.players[0]
        sq = _setup(game, [wall])
        sq.minus_one_counters = 4  # power 0
        spell = LifeProbe()
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Life Probe")
        assert p1.life == 21
        assert game.get_battlefield(p1).contains(wall)

    def test_copy_may_choose_new_targets(self) -> None:
        """Original zaps the opponent; the copy is retargeted at me."""
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game = create_game()
        p1, p2 = game.players
        _setup(game, [bear])
        # Consumed in order: p2 (original target, via cast_spell), bear
        # (casualty sacrifice), True (choose new targets?), p1 (new target).
        p1._script.extend([bear, True, p1])
        spell = ZapProbe()
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Zap Probe", targets=[p2])
        assert p2.life == 18  # original
        assert p1.life == 18  # retargeted copy
        assert game.get_graveyard(p1).contains(bear)

    def test_opponent_spells_do_not_trigger(self) -> None:
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game = create_game()  # any prompt would raise ScriptExhaustedError
        p1, p2 = game.players
        _setup(game, [bear])
        spell = LifeProbe()
        set_board_state(game, 1, hand=[spell], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 1, "Life Probe")
        assert p2.life == 21
        assert game.get_battlefield(p1).contains(bear)
