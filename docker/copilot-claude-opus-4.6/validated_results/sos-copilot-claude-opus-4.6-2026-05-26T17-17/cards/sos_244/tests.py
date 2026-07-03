"""Tests for SOS 244 — Witherbloom Charm.

Instant {B}{G}
Choose one —
• You may sacrifice a permanent. If you do, draw two cards.
• You gain 5 life.
• Destroy target nonland permanent with mana value 2 or less.
"""

from __future__ import annotations

from cards.sos.sos_244.card_impl import WitherbloomCharm
from engine.card import Creature, Instant, Artifact
from engine.types import ManaCost, Zone
from test_utils import create_game, set_board_state


class TestWitherbloomCharmProperties:
    """Static card data should match the SOS 244 spec."""

    def test_name(self) -> None:
        card = WitherbloomCharm(owner=None)
        assert card.name == "Witherbloom Charm"

    def test_mana_cost(self) -> None:
        card = WitherbloomCharm(owner=None)
        assert card.mana_cost == ManaCost.parse("{B}{G}")

    def test_is_instant(self) -> None:
        card = WitherbloomCharm(owner=None)
        assert isinstance(card, Instant)


class TestWitherbloomCharmMode1:
    """Mode 1: You may sacrifice a permanent. If you do, draw two cards."""

    def test_sacrifice_and_draw_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomCharm(owner=p1, controller=p1)
        sac_target = Creature(name="Elf", base_power=1, base_toughness=1)
        sac_target.owner = p1
        sac_target.controller = p1
        # Put some cards in library to draw
        lib1 = Creature(name="Card1", base_power=1, base_toughness=1)
        lib2 = Creature(name="Card2", base_power=2, base_toughness=2)
        lib1.owner = p1
        lib2.owner = p1
        set_board_state(game, 0, battlefield=[sac_target])
        p1.zones[Zone.LIBRARY].add(lib1)
        p1.zones[Zone.LIBRARY].add(lib2)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        card.on_resolve(game, mode=1, sacrifice_target=sac_target)
        hand_after = len(p1.zones[Zone.HAND].get_all())
        # Should draw 2 cards
        assert hand_after - hand_before == 2
        # Sacrificed permanent should leave the battlefield
        bf = game.get_battlefield(p1).get_all()
        assert sac_target not in bf

    def test_may_choose_not_to_sacrifice(self) -> None:
        """'You may sacrifice' — if you don't, you don't draw."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomCharm(owner=p1, controller=p1)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        card.on_resolve(game, mode=1, sacrifice_target=None)
        hand_after = len(p1.zones[Zone.HAND].get_all())
        assert hand_after == hand_before


class TestWitherbloomCharmMode2:
    """Mode 2: You gain 5 life."""

    def test_gain_5_life(self) -> None:
        game = create_game(player1_life=20)
        p1 = game.players[0]
        card = WitherbloomCharm(owner=p1, controller=p1)
        card.on_resolve(game, mode=2)
        assert p1.life == 25


class TestWitherbloomCharmMode3:
    """Mode 3: Destroy target nonland permanent with mana value 2 or less."""

    def test_destroys_creature_with_mv_2(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = WitherbloomCharm(owner=p1, controller=p1)
        target = Creature(name="Bear", base_power=2, base_toughness=2)
        target.mana_cost = ManaCost.parse("{1}{G}")
        target.owner = p2
        target.controller = p2
        set_board_state(game, 1, battlefield=[target])
        card.on_resolve(game, mode=3, targets=[target])
        bf = game.get_battlefield(p2).get_all()
        assert target not in bf

    def test_destroys_artifact_with_mv_1(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = WitherbloomCharm(owner=p1, controller=p1)
        target = Artifact(name="Relic")
        target.mana_cost = ManaCost.parse("{1}")
        target.owner = p2
        target.controller = p2
        set_board_state(game, 1, battlefield=[target])
        card.on_resolve(game, mode=3, targets=[target])
        bf = game.get_battlefield(p2).get_all()
        assert target not in bf

    def test_does_not_destroy_permanent_with_mv_above_2(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = WitherbloomCharm(owner=p1, controller=p1)
        target = Creature(name="Angel", base_power=4, base_toughness=4)
        target.mana_cost = ManaCost.parse("{3}{W}")
        target.owner = p2
        target.controller = p2
        set_board_state(game, 1, battlefield=[target])
        # This should be an illegal target; implementation should not destroy it
        card.on_resolve(game, mode=3, targets=[target])
        bf = game.get_battlefield(p2).get_all()
        assert target in bf
