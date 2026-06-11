"""Tests for SOS 231 — Splatter Technique.

Sorcery {1}{U}{U}{R}{R}
Choose one —
• Draw four cards.
• Splatter Technique deals 4 damage to each creature and planeswalker.
"""

from __future__ import annotations

from cards.sos.sos_231.card_impl import SplatterTechnique
from engine.card import Creature, Sorcery
from engine.types import ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestSplatterTechniqueProperties:
    """Static card data should match the SOS 231 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(SplatterTechnique(owner=None), Sorcery)

    def test_name(self) -> None:
        assert SplatterTechnique(owner=None).name == "Splatter Technique"

    def test_mana_cost(self) -> None:
        assert SplatterTechnique(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}{R}{R}")


class TestSplatterTechniqueDrawMode:
    """Mode 1: Draw four cards."""

    def test_draw_four_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SplatterTechnique(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card],
                        mana={ManaType.BLUE: 2, ManaType.RED: 2, ManaType.COLORLESS: 1})
        # Put cards in library so draws succeed
        hand_before = len(game.get_hand(p1).get_all())
        card.mode = 0  # first mode: draw four
        card.on_resolve(game)
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after - hand_before >= 4


class TestSplatterTechniqueDamageMode:
    """Mode 2: Deal 4 damage to each creature and planeswalker."""

    def test_deals_4_damage_to_each_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        big = Creature(name="Hill Giant", base_power=3, base_toughness=5)
        set_board_state(game, 0, battlefield=[bear])
        set_board_state(game, 1, battlefield=[big])
        card = SplatterTechnique(owner=p1, controller=p1)
        card.mode = 1  # second mode: damage
        card.on_resolve(game)
        # 2 toughness creature should die (4 damage >= 2 toughness)
        bf0 = [c for c in game.get_battlefield(game.players[0]).get_all()
                if isinstance(c, Creature)]
        assert len(bf0) == 0  # bear destroyed
        # 5 toughness creature takes 4 damage but survives
        big_on_bf = [c for c in game.get_battlefield(game.players[1]).get_all()
                     if isinstance(c, Creature) and c.name == "Hill Giant"]
        assert len(big_on_bf) == 1
        assert big_on_bf[0].damage_taken >= 4

    def test_does_not_damage_players(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SplatterTechnique(owner=p1, controller=p1)
        card.mode = 1
        card.on_resolve(game)
        assert p1.life == 20
        assert p2.life == 20
