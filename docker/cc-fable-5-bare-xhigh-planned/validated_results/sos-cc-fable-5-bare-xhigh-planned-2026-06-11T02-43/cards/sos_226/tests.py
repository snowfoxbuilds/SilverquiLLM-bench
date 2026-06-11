"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import cast_spell, create_game, set_board_state


class _Zap(Instant):
    """Test instant: deal 2 damage to any target."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
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

        chosen = getattr(self, "chosen_targets", None) or []
        if chosen and chosen[0] is not None:
            deal_damage(game, self, chosen[0], 2)


def _setup(p1_script: list[Any]) -> Any:
    game = create_game(scripts=(p1_script, []))
    silverquill = SilverquillTheDisputant()
    bear = Creature(name="Bear", base_power=2, base_toughness=2)
    set_board_state(game, 0, battlefield=[silverquill, bear],
                    hand=[_Zap()], mana={ManaType.RED: 1})
    silverquill.register_triggers(game)  # set_board_state skips ETB hooks
    return game, silverquill, bear


class TestProperties:
    def test_static_data(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert card.base_power == 4 and card.base_toughness == 4
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords


class TestCasualty:
    def test_sacrifice_copies_spell(self) -> None:
        # Script: sacrifice the bear, keep the same targets for the copy.
        game, sq, bear = _setup([])
        p1, p2 = game.players
        p1._script.extend([bear, False])

        cast_spell(game, 0, "Zap", targets=[p2])

        assert game.get_graveyard(p1).contains(bear)   # sacrificed
        assert p2.life == 16                            # original + copy = 4
        # The copy never changes zones — only the real card is in the yard.
        zaps_in_gy = [c for c in game.get_graveyard(p1).get_all()
                      if c.name == "Zap"]
        assert len(zaps_in_gy) == 1

    def test_decline_no_copy(self) -> None:
        game, sq, bear = _setup([])
        p1, p2 = game.players
        p1._script.extend([None])  # decline the casualty

        cast_spell(game, 0, "Zap", targets=[p2])

        assert game.get_battlefield(p1).contains(bear)
        assert p2.life == 18  # only the original resolved

    def test_copy_may_choose_new_targets(self) -> None:
        game, sq, bear = _setup([])
        p1, p2 = game.players
        # sacrifice bear, choose new targets: the copy hits p1 instead.
        p1._script.extend([bear, True, p1])

        cast_spell(game, 0, "Zap", targets=[p2])

        assert p2.life == 18  # original
        assert p1.life == 18  # retargeted copy

    def test_no_eligible_creature_no_prompt(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant()
        weakling = Creature(name="Weakling", base_power=0, base_toughness=3)
        set_board_state(game, 0, battlefield=[silverquill, weakling],
                        hand=[_Zap()], mana={ManaType.RED: 1})
        silverquill.register_triggers(game)
        # Silverquill itself is normally an eligible casualty; simulate a
        # -4/-0 effect so no creature has power >= 1.
        silverquill.modified_power = 0

        cast_spell(game, 0, "Zap", targets=[p2])

        assert p2.life == 18                      # no copy
        assert game.get_battlefield(p1).contains(weakling)
        assert p1.remaining_choices == 0          # never prompted

    def test_opponent_spells_do_not_trigger(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[silverquill, bear])
        silverquill.register_triggers(game)
        set_board_state(game, 1, hand=[_Zap()], mana={ManaType.RED: 1})

        cast_spell(game, 1, "Zap", targets=[p1])

        assert p1.life == 18                      # single resolution
        assert game.get_battlefield(p1).contains(bear)
        assert p1.remaining_choices == 0
