"""Reference test for FDN 38 — Faebloom Trick.

Pattern 1 — targeted spell, but with an *optional* ("up to one") target. The
spell always creates two Faerie tokens; its reflexive "when you do, tap target
creature an opponent controls" is modelled as an optional TargetRequirement so
the spell stays castable (and still makes tokens) when there is no opponent
creature. Targeting is intent-style via ``cast_spell(targets=...)``.
"""

from __future__ import annotations

from cards.fdn.fdn_38.card_impl import FaebloomTrick
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


def _bear(p, name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _faeries(game, player):
    bf = game.get_battlefield(player)
    return [o for o in bf.get_all() if getattr(o, "name", None) == "Faerie"]


class TestFaebloomTrickProperties:
    def test_static_data(self):
        c = FaebloomTrick(owner=None)
        assert c.name == "Faebloom Trick"
        assert c.mana_cost == ManaCost.parse("{2}{U}")
        assert CardType.INSTANT in c.card_types

    def test_target_is_optional_requirement(self):
        c = FaebloomTrick(owner=None, controller=None)
        specs = c.get_targets(create_game())
        assert len(specs) == 1
        assert isinstance(specs[0], TargetRequirement)
        assert specs[0].zone == Zone.BATTLEFIELD
        assert specs[0].optional is True


class TestFaebloomTrickResolve:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        trick = FaebloomTrick(owner=p1, controller=p1)
        their_bear = _bear(p2, "Their Bear")
        set_board_state(game, 0, hand=[trick], mana={ManaType.BLUE: 3})
        set_board_state(game, 1, battlefield=[their_bear])
        return game, p1, p2, trick, their_bear

    def test_creates_two_flying_faeries_and_taps_target(self):
        game, p1, p2, trick, their_bear = self._setup()
        cast_spell(game, 0, "Faebloom Trick", targets=[their_bear])
        faeries = _faeries(game, p1)
        assert len(faeries) == 2
        for f in faeries:
            assert (f.base_power, f.base_toughness) == (1, 1)
            assert Keyword.FLYING & f.keywords
        # Reflexive trigger tapped the chosen opponent creature.
        assert their_bear.is_tapped is True

    def test_cost_is_paid(self):
        game, p1, p2, trick, their_bear = self._setup()
        cast_spell(game, 0, "Faebloom Trick", targets=[their_bear])
        assert p1.mana_pool.total() == 0

    def test_castable_with_no_target_still_makes_tokens(self):
        """Optional target: with no opponent creature the spell still resolves
        and makes both tokens; nothing is tapped."""
        game = create_game()
        p1, p2 = game.players
        trick = FaebloomTrick(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[trick], mana={ManaType.BLUE: 3})
        cast_spell(game, 0, "Faebloom Trick")  # no targets available/needed
        assert len(_faeries(game, p1)) == 2
