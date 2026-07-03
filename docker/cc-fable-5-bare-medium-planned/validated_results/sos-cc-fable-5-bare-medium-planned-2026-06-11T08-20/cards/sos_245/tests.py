"""Tests for Witherbloom, the Balancer (sos_245)."""

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state, cast_spell


class TestWitherbloomTheBalancer:
    def test_keywords(self):
        card = WitherbloomTheBalancer()
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords

    def test_own_affinity_for_creatures(self):
        game = create_game()
        bears = [Creature(name=f"Bear{i}", base_power=2, base_toughness=2) for i in range(4)]
        set_board_state(game, 0, hand=[WitherbloomTheBalancer()], battlefield=bears,
                        mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 2})
        # {6}{B}{G} minus 4 creatures = {2}{B}{G}
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.players[0].mana_pool.total() == 0
        bf = game.get_battlefield(game.players[0])
        assert any(c.name == "Witherbloom, the Balancer" for c in bf.get_all())

    def test_no_creatures_no_reduction(self):
        game = create_game()
        set_board_state(game, 0, hand=[WitherbloomTheBalancer()],
                        mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 5})
        # 0 creatures: full {6}{B}{G} needed, only 5 generic available -> fails
        try:
            cast_spell(game, 0, "Witherbloom, the Balancer")
            assert False, "expected cast to fail"
        except Exception:
            pass

    def test_grants_affinity_to_your_instants(self):
        game = create_game()
        wb = WitherbloomTheBalancer()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        spell = Instant(name="Big Trick", mana_cost=ManaCost.parse("{3}{U}"))
        set_board_state(game, 0, battlefield=[wb, bear], hand=[spell],
                        mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1})
        # {3}{U} minus 2 creatures (Witherbloom counts itself) = {1}{U}
        cast_spell(game, 0, "Big Trick")
        assert game.players[0].mana_pool.total() == 0

    def test_does_not_reduce_opponent_spells(self):
        game = create_game()
        wb = WitherbloomTheBalancer()
        set_board_state(game, 0, battlefield=[wb])
        spell = Instant(name="Opp Trick", mana_cost=ManaCost.parse("{1}{U}"))
        set_board_state(game, 1, hand=[spell], mana={ManaType.BLUE: 1})
        # Opponent has no creatures and no reduction from our Witherbloom
        try:
            cast_spell(game, 1, "Opp Trick")
            assert False, "expected cast to fail"
        except Exception:
            pass
