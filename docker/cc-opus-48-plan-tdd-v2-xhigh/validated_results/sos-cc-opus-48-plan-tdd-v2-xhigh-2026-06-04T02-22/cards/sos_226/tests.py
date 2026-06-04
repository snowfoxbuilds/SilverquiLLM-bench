"""Tests for SOS 226 — Silverquill, the Disputant (Casualty grant)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class LifeGainBolt(Instant):
    """Test-only instant: controller gains 3 life on resolve (no targets)."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Life Gain Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 3


def _silverquill_board(scripts):
    game = create_game(scripts=scripts)
    p1, p2 = game.players
    silver = SilverquillTheDisputant(owner=p1, controller=p1)
    sac = Creature(name="Goblin", owner=p1, controller=p1,
                   base_power=2, base_toughness=2)
    sac.card_types = {CardType.CREATURE}
    bolt = LifeGainBolt(owner=p1, controller=p1)
    set_board_state(game, 0, battlefield=[silver, sac], hand=[bolt],
                    mana={ManaType.RED: 1}, life=20)
    silver.register_triggers(game)
    return game, p1, p2, silver, sac, bolt


class TestProperties:
    def test_is_creature(self) -> None:
        c = SilverquillTheDisputant(owner=None)
        assert isinstance(c, Creature)

    def test_name_cost_pt(self) -> None:
        c = SilverquillTheDisputant(owner=None)
        assert c.name == "Silverquill, the Disputant"
        assert c.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert c.base_power == 4
        assert c.base_toughness == 4

    def test_keywords(self) -> None:
        c = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in c.keywords
        assert Keyword.VIGILANCE in c.keywords


class TestCasualtyGrant:
    def test_paying_casualty_copies_the_spell(self) -> None:
        # Script: pay casualty? yes; sacrifice which creature -> the Goblin.
        game, p1, p2, silver, sac, bolt = _silverquill_board(
            scripts=([True, "SAC"], [])
        )
        # Replace the "SAC" sentinel with the actual creature object.
        p1._script[1] = sac

        cast_spell(game, 0, "Life Gain Bolt")

        # Resolved twice (original + copy): +3 +3 = +6 life.
        assert p1.life == 26
        # The Goblin was sacrificed.
        assert sac in p1.zones[Zone.GRAVEYARD].get_all()
        assert sac not in p1.zones[Zone.BATTLEFIELD].get_all()

    def test_declining_casualty_does_not_copy(self) -> None:
        game, p1, p2, silver, sac, bolt = _silverquill_board(
            scripts=([False], [])
        )
        cast_spell(game, 0, "Life Gain Bolt")

        assert p1.life == 23  # resolved once
        assert sac in p1.zones[Zone.BATTLEFIELD].get_all()  # not sacrificed

    def test_creature_spell_does_not_trigger_casualty(self) -> None:
        # A creature cast must not offer casualty, so the script stays full.
        game, p1, p2, silver, sac, bolt = _silverquill_board(
            scripts=([True, "unused"], [])
        )
        dummy = Creature(name="Vanilla", owner=p1, controller=p1,
                         base_power=1, base_toughness=1)
        dummy.mana_cost = ManaCost.parse("{R}")
        p1.zones[Zone.HAND].add(dummy)
        set_board_state(game, 0, mana={ManaType.RED: 1})
        before = p1.remaining_choices

        cast_spell(game, 0, "Vanilla")

        assert p1.remaining_choices == before  # no casualty prompt consumed
        assert dummy in p1.zones[Zone.BATTLEFIELD].get_all()

    def test_opponents_spell_does_not_trigger(self) -> None:
        game, p1, p2, silver, sac, bolt = _silverquill_board(
            scripts=([True, "unused"], [])
        )
        opp_bolt = LifeGainBolt(owner=p2, controller=p2)
        p2.zones[Zone.HAND].add(opp_bolt)
        set_board_state(game, 1, mana={ManaType.RED: 1}, life=20)
        before = p1.remaining_choices

        cast_spell(game, 1, "Life Gain Bolt")

        assert p1.remaining_choices == before  # p1's casualty not offered
        assert p2.life == 23  # resolved once only
