"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Instant, Sorcery
from engine.state_based_actions import resolve_state_based_actions
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    TargetRequirement,
    Zone,
)
from test_utils import cast_spell, create_game, declare_attackers, set_board_state


class _Zap(Instant):
    """Test instant: deal 3 damage to target player."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game):
        players = set(game.players)
        return [
            TargetRequirement(
                filter_fn=lambda o: o in players,
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game):
        from engine.game import deal_damage

        t = (getattr(self, "chosen_targets", []) or [None])[0]
        if t is not None:
            deal_damage(game, self, t, 3)


def _resolve_all(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class TestProperties:
    def test_name_pt_keywords(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.base_power == 7 and card.base_toughness == 7
        assert Keyword.REACH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes


class TestCostReduction:
    def test_reduced_by_graveyard_spells(self) -> None:
        """3 instants/sorceries in graveyard → {10} becomes {7}; 7 mana pays."""
        game = create_game()
        p0 = game.players[0]
        gy = [
            _Zap(owner=None),
            Sorcery(name="S1", mana_cost=ManaCost.parse("{1}"), owner=None),
            Instant(name="I1", mana_cost=ManaCost.parse("{1}"), owner=None),
        ]
        set_board_state(game, 0, hand=[TheDawningArchaic(owner=None)],
                        graveyard=gy, mana={ManaType.COLORLESS: 7})
        cast_spell(game, 0, "The Dawning Archaic")
        assert any(
            getattr(c, "name", None) == "The Dawning Archaic"
            for c in game.get_battlefield(p0).get_all()
        )

    def test_no_reduction_empty_graveyard(self) -> None:
        """Empty graveyard → full {10}; 9 mana is insufficient."""
        from test_utils import TestSetupError

        game = create_game()
        set_board_state(game, 0, hand=[TheDawningArchaic(owner=None)],
                        graveyard=[], mana={ManaType.COLORLESS: 9})
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "The Dawning Archaic")


class TestAttackTrigger:
    def _setup(self):
        game = create_game()
        p0, p1 = game.players
        archaic = TheDawningArchaic(owner=p0, controller=p0)
        archaic.summoning_sick = False
        zap = _Zap(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[zap])
        archaic.register_triggers(game)  # set_board_state does not fire ETB
        return game, p0, p1, archaic, zap

    def test_cast_from_graveyard_and_exile_instead(self) -> None:
        game, p0, p1, archaic, zap = self._setup()
        declare_attackers(game, ["The Dawning Archaic"])
        # Trigger choices: yes-cast, then Zap targets p1.
        p0._script.extend([True, p1])
        _resolve_all(game)

        assert p1.life == 17  # Zap dealt 3
        # "exile it instead" — Zap ends in exile, not graveyard.
        assert game.get_exile(p0).contains(zap)
        assert not game.get_graveyard(p0).contains(zap)

    def test_may_decline(self) -> None:
        game, p0, p1, archaic, zap = self._setup()
        declare_attackers(game, ["The Dawning Archaic"])
        p0._script.extend([False])  # decline
        _resolve_all(game)

        assert p1.life == 20
        assert game.get_graveyard(p0).contains(zap)  # untouched
        assert not game.get_exile(p0).contains(zap)

    def test_empty_graveyard_no_effect(self) -> None:
        game = create_game()
        p0, p1 = game.players
        archaic = TheDawningArchaic(owner=p0, controller=p0)
        archaic.summoning_sick = False
        set_board_state(game, 0, battlefield=[archaic], graveyard=[])
        archaic.register_triggers(game)
        declare_attackers(game, ["The Dawning Archaic"])
        # No candidates → no choices consumed.
        _resolve_all(game)
        assert p1.life == 20
