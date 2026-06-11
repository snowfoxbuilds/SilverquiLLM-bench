"""Tests for Silverquill, the Disputant (sos_226)."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestBolt(Instant):
    """Deals 2 damage to target player."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Test Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game):
        from engine.types import TargetRequirement
        return [TargetRequirement(
            filter_fn=lambda obj: hasattr(obj, "life"),
            description="target player",
            zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game):
        from engine.game import deal_damage
        chosen = getattr(self, "chosen_targets", None)
        if chosen and chosen[0] is not None:
            deal_damage(game, self, chosen[0], 2)


def _setup(game, extra_battlefield=()):
    sq = SilverquillTheDisputant()
    set_board_state(game, 0, battlefield=[sq, *extra_battlefield],
                    hand=[TestBolt(owner=None)], mana={ManaType.RED: 1})
    sq.register_triggers(game)  # set_board_state skips ETB hooks
    return sq


class TestSilverquillTheDisputant:
    def test_keywords(self):
        kw = SilverquillTheDisputant().keywords
        assert Keyword.FLYING in kw and Keyword.VIGILANCE in kw

    def test_casualty_sacrifice_copies_spell(self):
        game = create_game()
        p0, p1 = game.players
        goat = Creature(name="Goat", base_power=1, base_toughness=1)
        _setup(game, [goat])
        p0._script.append(goat)  # casualty answer
        cast_spell(game, 0, "Test Bolt", targets=[p1])
        assert p1.life == 16  # original + copy
        assert p0.zones[Zone.GRAVEYARD].contains(goat)

    def test_decline_casualty_no_copy(self):
        game = create_game()
        p0, p1 = game.players
        goat = Creature(name="Goat", base_power=1, base_toughness=1)
        _setup(game, [goat])
        p0._script.append(None)  # decline
        cast_spell(game, 0, "Test Bolt", targets=[p1])
        assert p1.life == 18
        assert game.get_battlefield(p0).contains(goat)

    def test_no_eligible_creature_no_prompt(self):
        game = create_game()
        p0, p1 = game.players
        wall = Creature(name="Wall", base_power=0, base_toughness=2)
        _setup(game, [wall])
        cast_spell(game, 0, "Test Bolt", targets=[p1])
        assert p1.life == 18
        assert game.get_battlefield(p0).contains(wall)

    def test_opponents_spells_unaffected(self):
        game = create_game()
        p0, p1 = game.players
        sq = SilverquillTheDisputant()
        goat = Creature(name="Goat", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[sq, goat])
        sq.register_triggers(game)
        set_board_state(game, 1, hand=[TestBolt(owner=None)], mana={ManaType.RED: 1})
        cast_spell(game, 1, "Test Bolt", targets=[p0])
        assert p0.life == 18  # single resolution, no copy, no prompt

    def test_creature_spells_unaffected(self):
        game = create_game()
        p0, p1 = game.players
        sq = SilverquillTheDisputant()
        goat = Creature(name="Goat", base_power=1, base_toughness=1)
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{2}"),
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[sq, goat], hand=[bear],
                        mana={ManaType.COLORLESS: 2})
        sq.register_triggers(game)
        cast_spell(game, 0, "Bear")
        assert game.get_battlefield(p0).contains(goat)  # never sacrificed
        assert game.get_battlefield(p0).contains(bear)
