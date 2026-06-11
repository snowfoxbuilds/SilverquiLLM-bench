"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, cast_spell, set_board_state


class LifeProbe(Instant):
    """Test-local instant: you gain 1 life."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Life Probe")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 1


class Zap(Instant):
    """Test-local instant: deal 2 damage to any target."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def get_targets(self, game):
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    hasattr(obj, "life")
                    or CardType.CREATURE in getattr(obj, "card_types", set())
                ),
                description="any target",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game):
        from engine.game import deal_damage

        chosen = getattr(self, "chosen_targets", None)
        if chosen and chosen[0] is not None:
            deal_damage(game, self, chosen[0], 2)


def _setup(game, extra_battlefield=()):
    p1 = game.players[0]
    sq = SilverquillTheDisputant(owner=p1)
    set_board_state(game, 0, battlefield=[sq, *extra_battlefield])
    sq.register_triggers(game)
    return sq


class TestCasualty:
    def test_sacrifice_copies_the_spell(self):
        """Sacrificing the bear copies Life Probe: gain 2 life total."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _setup(game, [bear])
        probe = LifeProbe(owner=p1)
        set_board_state(game, 0, hand=[probe], mana={ManaType.COLORLESS: 1})
        p1._script.append(bear)  # casualty: sacrifice the bear
        cast_spell(game, 0, "Life Probe")

        assert p1.life == 22
        assert p1.zones[Zone.GRAVEYARD].contains(bear)
        assert not game.get_battlefield(p1).contains(bear)

    def test_decline_no_copy(self):
        """Declining casualty resolves the spell once; bear survives."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _setup(game, [bear])
        probe = LifeProbe(owner=p1)
        set_board_state(game, 0, hand=[probe], mana={ManaType.COLORLESS: 1})
        p1._script.append(None)
        cast_spell(game, 0, "Life Probe")

        assert p1.life == 21
        assert game.get_battlefield(p1).contains(bear)

    def test_no_power_one_creature_no_prompt(self):
        """With no power>=1 creature to offer, casualty is skipped entirely
        (no prompt is consumed) and the spell resolves once."""
        game = create_game()
        p1 = game.players[0]
        wall = Creature(name="Wall", base_power=0, base_toughness=4)
        sq = _setup(game, [wall])
        sq.minus_one_counters = 4  # Silverquill is now power 0
        probe = LifeProbe(owner=p1)
        set_board_state(game, 0, hand=[probe], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Life Probe")  # empty script — no prompt expected
        assert p1.life == 21
        assert game.get_battlefield(p1).contains(wall)

    def test_copy_may_choose_new_targets(self):
        """Copy retargets to the caster; original hits the opponent."""
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _setup(game, [bear])
        zap = Zap(owner=p1)
        set_board_state(game, 0, hand=[zap], mana={ManaType.COLORLESS: 1})
        # After the cast target (p2): sacrifice bear, yes to new targets, p1.
        p1._script.append(bear)
        p1._script.append(True)
        p1._script.append(p1)
        cast_spell(game, 0, "Zap", targets=[p2])

        assert p1.life == 18  # copy hit p1
        assert p2.life == 18  # original hit p2

    def test_opponent_spells_unaffected(self):
        """An opponent's instant does not get casualty."""
        game = create_game()
        p1, p2 = game.players
        _setup(game)
        probe = LifeProbe(owner=p2)
        opp_bear = Creature(name="Opp Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[opp_bear], hand=[probe],
                        mana={ManaType.COLORLESS: 1})
        cast_spell(game, 1, "Life Probe")  # no prompts consumed
        assert p2.life == 21
        assert game.get_battlefield(p2).contains(opp_bear)

    def test_keywords(self):
        sq = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in sq.keywords
        assert Keyword.VIGILANCE in sq.keywords
