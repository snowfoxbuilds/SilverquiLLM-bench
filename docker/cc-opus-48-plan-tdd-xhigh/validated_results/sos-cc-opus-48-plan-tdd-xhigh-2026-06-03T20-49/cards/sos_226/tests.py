"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Sorcery
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, cast_spell, set_board_state


class _Lifebloom(Sorcery):
    """A no-target sorcery: gain 2 life on resolve."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Lifebloom")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 2


def _bear(name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2)


def _setup(control_silverquill=True, extra_bf=None):
    game = create_game()
    p0 = game.players[0]
    bf = []
    sq = None
    if control_silverquill:
        sq = SilverquillTheDisputant(owner=None)
        bf.append(sq)
    if extra_bf:
        bf.extend(extra_bf)
    set_board_state(game, 0, hand=[_Lifebloom(owner=None)], battlefield=bf,
                    mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1}, life=20)
    if sq is not None:
        sq.register_triggers(game)
    return game, p0, sq


class TestProperties:
    def test_is_creature(self):
        assert isinstance(SilverquillTheDisputant(owner=None), Creature)

    def test_name(self):
        assert SilverquillTheDisputant(owner=None).name == "Silverquill, the Disputant"

    def test_mana_cost(self):
        assert SilverquillTheDisputant(owner=None).mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_power_toughness(self):
        c = SilverquillTheDisputant(owner=None)
        assert c.base_power == 4 and c.base_toughness == 4

    def test_keywords(self):
        kw = SilverquillTheDisputant(owner=None).keywords
        assert Keyword.FLYING in kw and Keyword.VIGILANCE in kw

    def test_legendary(self):
        assert Supertype.LEGENDARY in SilverquillTheDisputant(owner=None).supertypes


class TestCasualty:
    def test_sacrifice_copies_spell(self):
        bear = _bear()
        game, p0, sq = _setup(extra_bf=[bear])
        p0._script.append(True)   # apply casualty?
        p0._script.append(bear)   # sacrifice the bear
        cast_spell(game, 0, "Lifebloom")
        # Original + copy both gained 2 life.
        assert p0.life == 24
        assert bear in p0.zones[Zone.GRAVEYARD].get_all()

    def test_decline_casualty_no_copy(self):
        bear = _bear()
        game, p0, sq = _setup(extra_bf=[bear])
        p0._script.append(False)  # decline casualty
        cast_spell(game, 0, "Lifebloom")
        assert p0.life == 22  # only the original resolved
        assert bear not in p0.zones[Zone.GRAVEYARD].get_all()

    def test_no_silverquill_no_casualty(self):
        bear = _bear()
        game, p0, sq = _setup(control_silverquill=False, extra_bf=[bear])
        cast_spell(game, 0, "Lifebloom")
        assert p0.life == 22
        assert bear not in p0.zones[Zone.GRAVEYARD].get_all()
