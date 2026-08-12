"""Regression test for FDN 224 — Gnarlid Colony.

The crash surface is ``get_continuous_effects``: it built a
``ContinuousEffect`` with three errors on one line — ``Layer.ABILITY_ADDING``
and ``SubLayer.DEFAULT`` (neither is a real enum member) passed via a
misspelled ``sub_layer=`` kwarg. This test drives ``get_continuous_effects``
and asserts the effect constructs at ``Layer.ABILITY`` and grants trample to
creatures with a +1/+1 counter.
"""

from __future__ import annotations

from cards.fdn.fdn_224.card_impl import GnarlidColony
from engine.card import Creature
from engine.continuous_effects import Layer
from engine.types import Keyword, ManaCost, Zone
from engine.zones import move_to_zone
from test_utils import create_game, set_board_state


class TestGnarlidColonyProperties:
    def test_name_and_cost(self) -> None:
        card = GnarlidColony(owner=None)
        assert card.name == "Gnarlid Colony"
        assert card.mana_cost == ManaCost.parse("{1}{G}")
        assert (card.base_power, card.base_toughness) == (2, 2)


class TestGnarlidColonyKickerEntry:
    """Kicker: enters with two +1/+1 counters if it was kicked (rule 614.1c)."""

    def test_kicked_enters_as_four_four(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GnarlidColony(owner=p1, controller=p1)
        card.kicked = True
        set_board_state(game, 0, hand=[card])
        move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)
        assert card.plus_one_counters == 2
        assert card.power == 4
        assert card.toughness == 4

    def test_unkicked_enters_as_two_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GnarlidColony(owner=p1, controller=p1)
        # kicked defaults to False; no evidence => no counters fabricated.
        set_board_state(game, 0, hand=[card])
        move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)
        assert card.plus_one_counters == 0
        assert card.power == 2
        assert card.toughness == 2


class TestGnarlidColonyContinuousEffect:
    """The previously-crashing get_continuous_effects path."""

    def test_effect_constructs_at_ability_layer(self) -> None:
        card = GnarlidColony(owner=None)
        effects = card.get_continuous_effects()  # must not raise
        assert len(effects) == 1
        assert effects[0].layer is Layer.ABILITY
        assert effects[0].sublayer is None

    def test_grants_trample_to_creatures_with_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        gnarlid = GnarlidColony(owner=p1, controller=p1)
        buffed = Creature(name="Beast", subtypes={"Beast"}, base_power=1, base_toughness=1)
        plain = Creature(name="Bear", subtypes={"Bear"}, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[gnarlid, buffed, plain])
        from engine.game import add_counter
        add_counter(game, buffed, "+1/+1", 1)

        for eff in gnarlid.get_continuous_effects():
            game.effect_manager.add(eff)
        game.effect_manager.apply_all(game)

        assert Keyword.TRAMPLE in buffed.keywords
        assert Keyword.TRAMPLE not in plain.keywords
