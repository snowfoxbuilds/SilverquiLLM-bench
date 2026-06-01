"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.combat import declare_attackers_step
from engine.types import Keyword, ManaCost, Phase, Step, Supertype
from test_utils import create_game, set_board_state


class _DamageInstant(Instant):
    """Test instant that deals 2 damage to its controller's opponent."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        controller = self.controller
        opp = game.players[1] if controller is game.players[0] else game.players[0]
        deal_damage(game, self, opp, 2)


def _resolve_all(game) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _isorc(n: int) -> list:
    return [Instant(name=f"i{i}", mana_cost=ManaCost.parse("{1}")) for i in range(n)]


class TestDawningArchaicProperties:
    def test_name_and_stats(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_keywords_and_types(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Keyword.REACH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes


class TestDawningArchaicCostReduction:
    def test_reduction_counts_instants_and_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        gy = [
            Instant(name="i1", mana_cost=ManaCost.parse("{1}")),
            Sorcery(name="s1", mana_cost=ManaCost.parse("{2}")),
            Creature(name="bear", base_power=2, base_toughness=2),
        ]
        set_board_state(game, 0, hand=[archaic], graveyard=gy)
        # Only the instant + sorcery count; the creature does not.
        assert get_cost_reduction(game, archaic, p1) == 2

    def test_reduction_clamped_to_generic(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[archaic], graveyard=_isorc(13))
        # Generic portion is {10}; reduction cannot exceed it.
        assert get_cost_reduction(game, archaic, p1) == 10


class TestDawningArchaicAttackCast:
    def test_attack_casts_from_graveyard_and_exiles(self) -> None:
        game = create_game()
        p1, p2 = game.players
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        zap = _DamageInstant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[zap])
        archaic.summoning_sick = False
        archaic.register_triggers(game)

        # When the attack trigger resolves: yes, then choose the instant.
        p1._script.append(True)
        p1._script.append(zap)

        game.active_player_index = 0
        game.phase = Phase.COMBAT
        game.step = Step.DECLARE_ATTACKERS
        game.combat_state.in_combat = True
        p1._script.appendleft([archaic])  # attacker declaration (consumed first)
        declare_attackers_step(game)

        # Resolve the attack trigger and the free spell it casts.
        _resolve_all(game)

        assert p2.life == 20 - 2
        assert zap in game.get_exile(p1).get_all()
        assert zap not in game.get_graveyard(p1).get_all()

    def test_decline_does_not_cast(self) -> None:
        game = create_game()
        p1, p2 = game.players
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        zap = _DamageInstant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[zap])

        p1._script.append(False)  # decline the optional cast
        archaic._attack_cast(game)
        _resolve_all(game)

        assert p2.life == 20
        assert zap in game.get_graveyard(p1).get_all()
        assert zap not in game.get_exile(p1).get_all()

    def test_no_castable_cards_asks_nothing(self) -> None:
        game = create_game()
        p1, p2 = game.players
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        bear = Creature(name="bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[bear])

        # No instants/sorceries: must return without consuming any choice
        # (an empty script would raise if it tried to ask).
        archaic._attack_cast(game)
        assert game.stack.is_empty()
        assert p2.life == 20
