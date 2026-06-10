"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


class LifeRush(Instant):
    """Test instant: you gain 3 life (no targets)."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Life Rush")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 3


class TestBolt(Instant):
    """Test instant: deal 2 damage to any target."""

    __test__ = False  # not a pytest class

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Test Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def get_targets(self, game):
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life")
                or hasattr(obj, "damage_marked"),
                description="any target",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game):
        from engine.game import deal_damage

        chosen = getattr(self, "chosen_targets", None) or []
        if chosen and chosen[0] is not None:
            deal_damage(game, self, chosen[0], 2)


def _game_with_silverquill(p1_script, extra_battlefield=None):
    game = create_game(scripts=(list(p1_script), []))
    sq = SilverquillTheDisputant()
    set_board_state(
        game, 0, hand=[sq],
        mana={ManaType.WHITE: 1, ManaType.BLACK: 1, ManaType.COLORLESS: 2},
    )
    cast_spell(game, 0, "Silverquill, the Disputant")
    if extra_battlefield:
        bf = game.get_battlefield(game.players[0])
        for c in extra_battlefield:
            c.owner = c.controller = game.players[0]
            bf.add(c)
    return game


class TestSilverquill:
    def test_keywords(self):
        card = SilverquillTheDisputant()
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords

    def test_casualty_copies_spell(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game = _game_with_silverquill([True, bear], [bear])
        p1 = game.players[0]
        set_board_state(game, 0, hand=[LifeRush()], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Life Rush")
        # Original + copy both resolved: +6 life. Bear was sacrificed.
        assert p1.life == 26
        assert game.get_graveyard(p1).contains(bear)
        assert not game.get_battlefield(p1).contains(bear)

    def test_casualty_declined(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game = _game_with_silverquill([False], [bear])
        p1 = game.players[0]
        set_board_state(game, 0, hand=[LifeRush()], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Life Rush")
        assert p1.life == 23  # resolved once
        assert game.get_battlefield(p1).contains(bear)

    def test_silverquill_itself_is_legal_casualty(self):
        game = _game_with_silverquill([])
        p1 = game.players[0]
        sq = game.get_battlefield(p1).get_all()[0]
        p1._script.extend([True, sq])
        set_board_state(game, 0, hand=[LifeRush()], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Life Rush")
        assert p1.life == 26  # copy still made
        assert game.get_graveyard(p1).contains(sq)

    def test_no_creature_with_power_one(self):
        # A power-reducing effect leaves only power-0 creatures: no casualty
        # question is even asked (empty script would otherwise raise).
        wall = Creature(name="Wall", base_power=0, base_toughness=4)
        game = _game_with_silverquill([], [wall])
        p1 = game.players[0]
        sq = game.get_battlefield(p1).get_all()[0]
        sq.modified_power = 0  # simulate a -4/-0 effect
        set_board_state(game, 0, hand=[LifeRush()], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Life Rush")
        assert p1.life == 23
        assert game.get_battlefield(p1).contains(wall)

    def test_copy_may_choose_new_targets(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game = _game_with_silverquill([], [bear])
        p1, p2 = game.players
        # Script: sacrifice yes, bear, new targets yes, new target = p1.
        p1._script.extend([True, bear, True, p1])
        set_board_state(game, 0, hand=[TestBolt()], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Test Bolt", targets=[p2])
        # Copy (new target p1) resolves first, then original hits p2.
        assert p1.life == 18
        assert p2.life == 18

    def test_opponent_spells_do_not_trigger(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game = _game_with_silverquill([], [bear])
        p2 = game.players[1]
        set_board_state(game, 1, hand=[LifeRush()], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 1, "Life Rush")
        assert p2.life == 23  # resolved once; no casualty offered
        assert game.get_battlefield(game.players[0]).contains(bear)
