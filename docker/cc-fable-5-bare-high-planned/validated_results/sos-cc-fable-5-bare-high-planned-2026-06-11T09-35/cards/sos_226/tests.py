"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state, cast_spell


class _LifeZap(Instant):
    """Test instant with no targets: you gain 2 life."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Life Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 2


class _Bolt(Instant):
    """Test instant: deal 2 damage to any target."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Bolt"),
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game):
        return [TargetRequirement(
            filter_fn=lambda obj: (
                CardType.CREATURE in getattr(obj, "card_types", set())
                or hasattr(obj, "life")
            ),
            description="any target",
            zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game):
        from engine.game import deal_damage
        chosen = getattr(self, "chosen_targets", None)
        if chosen and chosen[0] is not None:
            deal_damage(game, self, chosen[0], 2)


def _setup(game, extra_battlefield=None, hand=None, mana=None):
    sq = SilverquillTheDisputant(owner=None)
    bf = [sq] + (extra_battlefield or [])
    set_board_state(game, 0, battlefield=bf, hand=hand or [], mana=mana or {})
    sq.register_triggers(game)
    return sq


class TestSilverquillStatic:
    def test_card_data(self):
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert card.base_power == 4 and card.base_toughness == 4


class TestSilverquillCasualty:
    def test_sacrifice_copies_the_spell(self):
        """Sac the bear → Life Zap resolves twice (+4 life), bear dies."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _setup(game, extra_battlefield=[bear], hand=[_LifeZap()],
               mana={ManaType.COLORLESS: 1})
        p1._script.append(bear)  # casualty choice
        cast_spell(game, 0, "Life Zap")

        assert p1.life == 24, "original + copy each gain 2"
        assert p1.zones[Zone.GRAVEYARD].contains(bear)

    def test_decline_no_copy(self):
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _setup(game, extra_battlefield=[bear], hand=[_LifeZap()],
               mana={ManaType.COLORLESS: 1})
        p1._script.append(None)  # decline casualty
        cast_spell(game, 0, "Life Zap")

        assert p1.life == 22, "only the original resolves"
        assert p1.zones[Zone.BATTLEFIELD].contains(bear)

    def test_targeted_spell_copy_keeps_targets(self):
        """Copy resolves on the same target when new targets are declined."""
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        _setup(game, extra_battlefield=[bear], hand=[_Bolt()],
               mana={ManaType.RED: 1})
        # Script order: target (cast) is prepended by cast_spell; then
        # casualty choose_card, then choose_yes_no for new targets.
        p1._script.append(bear)   # sacrifice the bear
        p1._script.append(False)  # keep the original target
        cast_spell(game, 0, "Bolt", targets=[p2])

        assert p2.life == 16, "2 from copy + 2 from original"
        assert p1.zones[Zone.GRAVEYARD].contains(bear)

    def test_opponent_spells_do_not_trigger(self):
        """An opponent's instant has no casualty from your Silverquill."""
        game = create_game()
        p1, p2 = game.players
        _setup(game, extra_battlefield=[
            Creature(name="Bear", base_power=2, base_toughness=2)])
        zap = _LifeZap()
        set_board_state(game, 1, hand=[zap], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 1, "Life Zap")  # empty p2 script — no prompt expected

        assert p2.life == 22
        assert p1.life == 20

    def test_creature_spells_do_not_trigger(self):
        """Casting a creature spell never asks for casualty."""
        game = create_game()
        p1 = game.players[0]
        wolf = Creature(name="Wolf", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{1}"))
        _setup(game, hand=[wolf], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Wolf")  # empty script — would raise if prompted

        assert p1.zones[Zone.BATTLEFIELD].contains(wolf)
