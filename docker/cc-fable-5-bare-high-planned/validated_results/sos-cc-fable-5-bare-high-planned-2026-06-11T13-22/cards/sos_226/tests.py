"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


class Zap(Instant):
    """Local probe instant: deal 2 damage to target player."""

    def __init__(self, **kw: Any) -> None:
        kw.setdefault("name", "Zap")
        kw.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kw)

    def get_targets(self, game):
        return [TargetRequirement(
            filter_fn=lambda o: hasattr(o, "life") and hasattr(o, "zones"),
            description="target player",
            zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game):
        from engine.game import deal_damage

        target = (getattr(self, "chosen_targets", None) or [None])[0]
        if target is not None:
            deal_damage(game, self, target, 2)


def _setup(extra_battlefield=None):
    game = create_game()
    sq = SilverquillTheDisputant(owner=None)
    bf = [sq] + (extra_battlefield or [])
    set_board_state(game, 0, battlefield=bf, hand=[Zap()],
                    mana={ManaType.RED: 1})
    sq.register_triggers(game)
    return game, sq


class TestSilverquillCasualty:
    def test_sacrifice_copies_spell(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, sq = _setup([bear])
        p1, p2 = game.players
        # Script after target: choose bear for casualty, decline new targets.
        p1._script.extend([bear, False])

        cast_spell(game, 0, "Zap", targets=[p2])

        assert p1.zones[Zone.GRAVEYARD].contains(bear)      # sacrificed
        assert p2.life == 16                                # original + copy

    def test_decline_casualty_no_copy(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, sq = _setup([bear])
        p1, p2 = game.players
        p1._script.extend([None])  # decline the sacrifice

        cast_spell(game, 0, "Zap", targets=[p2])

        assert p1.zones[Zone.BATTLEFIELD].contains(bear)
        assert p2.life == 18                                # only the original

    def test_no_power_one_creature_no_prompt(self):
        # Drop Silverquill's own power to 0 so there is no creature with
        # power >= 1 — the casualty prompt must be skipped entirely
        # (no script entry is consumed) and the spell resolves once.
        wall = Creature(name="Wall", base_power=0, base_toughness=4)
        game, sq = _setup([wall])
        p1, p2 = game.players
        sq.minus_one_counters = 4

        cast_spell(game, 0, "Zap", targets=[p2])
        assert p2.life == 18
        assert p1.zones[Zone.BATTLEFIELD].contains(wall)

    def test_copy_may_choose_new_targets(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, sq = _setup([bear])
        p1, p2 = game.players
        # casualty: bear; new targets: yes; new target: p1 itself.
        p1._script.extend([bear, True, p1])

        cast_spell(game, 0, "Zap", targets=[p2])

        assert p2.life == 18   # original hits p2
        assert p1.life == 18   # copy redirected to p1

    def test_opponent_spell_does_not_trigger(self):
        game, sq = _setup()
        p1, p2 = game.players
        set_board_state(game, 1, hand=[Zap()], mana={ManaType.RED: 1})

        cast_spell(game, 1, "Zap", targets=[p1])

        assert p1.life == 18  # only one resolution, no casualty prompt
        assert Keyword.VIGILANCE in sq.keywords and Keyword.FLYING in sq.keywords
