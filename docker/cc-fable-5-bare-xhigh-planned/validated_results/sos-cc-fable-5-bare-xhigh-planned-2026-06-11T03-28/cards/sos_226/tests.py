"""Tests for SOS 226 — Silverquill, the Disputant (casualty 1)."""

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
from test_utils import create_game, set_board_state, cast_spell


class _Zap(Instant):
    """Helper instant: controller gains 1 life on resolution."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 1


class _Sting(Instant):
    """Helper targeted instant: deal 1 damage to target creature."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sting")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list:
        return [TargetRequirement(
            filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
            description="target creature",
            zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage
        targets = getattr(self, "chosen_targets", None) or []
        if targets and targets[0] is not None:
            deal_damage(game, self, targets[0], 1)


def _setup(game, extra_battlefield=None):
    p1 = game.players[0]
    sq = SilverquillTheDisputant(owner=p1)
    battlefield = [sq] + (extra_battlefield or [])
    set_board_state(game, 0, battlefield=battlefield)
    # set_board_state bypasses move_to_zone; register triggers explicitly.
    sq.register_triggers(game)
    return sq


class TestSilverquillProperties:
    def test_static_data(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert card.base_power == 4
        assert card.base_toughness == 4
        assert Supertype.LEGENDARY in card.supertypes


class TestSilverquillCasualty:
    def test_sacrifice_copies_the_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _setup(game, [bear])
        spell = _Zap(owner=p1)
        game.get_hand(p1).add(spell)
        p1.mana_pool.add(ManaType.RED, 1)
        p1._script.extend([bear])  # casualty: sacrifice the bear
        cast_spell(game, 0, "Zap")
        # Original + copy each gain 1 life; bear is sacrificed.
        assert p1.life == 22
        assert game.get_graveyard(p1).contains(bear)
        assert not game.get_battlefield(p1).contains(bear)

    def test_decline_no_copy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _setup(game, [bear])
        spell = _Zap(owner=p1)
        game.get_hand(p1).add(spell)
        p1.mana_pool.add(ManaType.RED, 1)
        p1._script.extend([None])  # decline casualty
        cast_spell(game, 0, "Zap")
        assert p1.life == 21
        assert game.get_battlefield(p1).contains(bear)

    def test_no_power_one_creature_no_prompt(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wall = Creature(name="Wall", base_power=0, base_toughness=3)
        sq = _setup(game, [wall])
        # Shrink Silverquill to power 0 so NO creature has power >= 1:
        # casualty simply can't be taken and no prompt is issued.
        sq.minus_one_counters = 4
        spell = _Zap(owner=p1)
        game.get_hand(p1).add(spell)
        p1.mana_pool.add(ManaType.RED, 1)
        cast_spell(game, 0, "Zap")
        assert p1.life == 21
        assert p1.remaining_choices == 0
        assert game.get_battlefield(p1).contains(wall)

    def test_opponents_spells_not_affected(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _setup(game)
        bear = Creature(name="Opp Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        spell = _Zap(owner=p2)
        game.get_hand(p2).add(spell)
        p2.mana_pool.add(ManaType.RED, 1)
        cast_spell(game, 1, "Zap")
        # No casualty prompt fired for the opponent; spell resolved once.
        assert p2.life == 21
        assert p2.remaining_choices == 0
        assert game.get_battlefield(p2).contains(bear)

    def test_copy_may_choose_new_targets(self) -> None:
        game = create_game()
        p1, p2 = game.players
        sac_bear = Creature(name="Sac Bear", base_power=2, base_toughness=2)
        _setup(game, [sac_bear])
        t1 = Creature(name="Target One", base_power=3, base_toughness=3)
        t2 = Creature(name="Target Two", base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        spell = _Sting(owner=p1)
        game.get_hand(p1).add(spell)
        p1.mana_pool.add(ManaType.RED, 1)
        # Script order: cast target (t1) is prepended by cast_spell; then
        # the trigger pops: choose_card(sac_bear), choose_yes_no(True),
        # choose_target(t2) for the copy.
        p1._script.extend([sac_bear, True, t2])
        cast_spell(game, 0, "Sting", targets=[t1])
        assert t1.damage_marked == 1
        assert t2.damage_marked == 1
        assert game.get_graveyard(p1).contains(sac_bear)
