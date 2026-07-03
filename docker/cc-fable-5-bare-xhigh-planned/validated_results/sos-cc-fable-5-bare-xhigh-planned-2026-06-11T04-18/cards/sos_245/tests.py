"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


def _bears(n: int) -> list[Creature]:
    return [Creature(name=f"Bear {i}", base_power=2, base_toughness=2) for i in range(n)]


class TestStaticProperties:
    def test_keywords_and_stats(self) -> None:
        card = WitherbloomTheBalancer()
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert card.base_power == 5
        assert card.base_toughness == 5
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")


class TestOwnAffinity:
    def test_costs_one_less_per_creature_you_control(self) -> None:
        game = create_game()
        set_board_state(
            game,
            0,
            battlefield=_bears(4),
            hand=[WitherbloomTheBalancer()],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 2},
        )
        cast_spell(game, 0, "Witherbloom, the Balancer")
        p1 = game.players[0]
        assert any(
            c.name == "Witherbloom, the Balancer"
            for c in game.get_battlefield(p1).get_all()
        )
        assert p1.mana_pool.total() == 0

    def test_no_creatures_full_price(self) -> None:
        game = create_game()
        set_board_state(
            game,
            0,
            hand=[WitherbloomTheBalancer()],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 5},
        )
        try:
            cast_spell(game, 0, "Witherbloom, the Balancer")
            raised = False
        except Exception:
            raised = True
        assert raised, "without creatures the full {6}{B}{G} is due"

    def test_colored_pips_never_reduced(self) -> None:
        """Even with 10 creatures, {B}{G} must still be paid."""
        game = create_game()
        set_board_state(
            game,
            0,
            battlefield=_bears(10),
            hand=[WitherbloomTheBalancer()],
            mana={ManaType.COLORLESS: 2},
        )
        try:
            cast_spell(game, 0, "Witherbloom, the Balancer")
            raised = False
        except Exception:
            raised = True
        assert raised


class TestGrantedAffinity:
    def test_your_instants_cost_less(self) -> None:
        """Witherbloom + 2 bears = 3 creatures -> a {3}{R} instant costs {R}."""
        game = create_game()
        spell = Instant(name="Big Bolt", mana_cost=ManaCost.parse("{3}{R}"))
        set_board_state(
            game,
            0,
            battlefield=[WitherbloomTheBalancer()] + _bears(2),
            hand=[spell],
            mana={ManaType.RED: 1},
        )
        cast_spell(game, 0, "Big Bolt")
        assert game.get_graveyard(game.players[0]).contains(spell)

    def test_opponents_spells_unaffected(self) -> None:
        """Witherbloom only grants affinity to its controller's spells."""
        game = create_game()
        set_board_state(game, 0, battlefield=[WitherbloomTheBalancer()] + _bears(2))
        spell = Instant(name="Opposing Bolt", mana_cost=ManaCost.parse("{2}{R}"))
        set_board_state(game, 1, hand=[spell], mana={ManaType.RED: 1})
        game.active_player_index = 1
        game.priority_player_index = 1
        try:
            cast_spell(game, 1, "Opposing Bolt")
            raised = False
        except Exception:
            raised = True
        assert raised, "opponent's spell should not be reduced"

    def test_creature_spells_not_granted_affinity(self) -> None:
        game = create_game()
        bear = Creature(name="Costly Bear", mana_cost=ManaCost.parse("{2}{G}"), base_power=2, base_toughness=2)
        set_board_state(
            game,
            0,
            battlefield=[WitherbloomTheBalancer()] + _bears(2),
            hand=[bear],
            mana={ManaType.GREEN: 1},
        )
        try:
            cast_spell(game, 0, "Costly Bear")
            raised = False
        except Exception:
            raised = True
        assert raised, "only instants/sorceries get granted affinity"
