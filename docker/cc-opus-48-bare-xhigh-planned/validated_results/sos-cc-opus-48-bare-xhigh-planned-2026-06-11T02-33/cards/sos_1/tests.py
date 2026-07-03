"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant
from engine.casting import resolve_top
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, cast_spell, set_board_state


class ZapInstant(Instant):
    """Helper instant: deal 2 damage to the opponent on resolve."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        from engine.game import deal_damage
        opp = [p for p in game.players if p is not self.controller][0]
        deal_damage(game, self, opp, 2)


def _drain(game):
    while not game.stack.is_empty():
        resolve_top(game)


class TestProperties:
    def test_basic(self):
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")
        assert card.base_power == 7 and card.base_toughness == 7
        assert Keyword.REACH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes


class TestCostReduction:
    def test_reduced_by_graveyard_spells(self):
        game = create_game()
        p0 = game.players[0]
        gy = [Instant(name=f"S{i}", mana_cost=ManaCost.parse("{R}")) for i in range(3)]
        set_board_state(game, 0, hand=[TheDawningArchaic(owner=None)],
                        graveyard=gy, mana={ManaType.COLORLESS: 7})
        # {10} - 3 instants = {7}; exactly 7 mana casts it.
        cast_spell(game, 0, "The Dawning Archaic")
        names = [getattr(c, "name", "") for c in game.get_battlefield(p0).get_all()]
        assert "The Dawning Archaic" in names

    def test_insufficient_when_not_enough_reduction(self):
        game = create_game()
        gy = [Instant(name="S0", mana_cost=ManaCost.parse("{R}"))]  # only 1 → {9}
        set_board_state(game, 0, hand=[TheDawningArchaic(owner=None)],
                        graveyard=gy, mana={ManaType.COLORLESS: 7})
        with pytest.raises(Exception):
            cast_spell(game, 0, "The Dawning Archaic")

    def test_reduction_clamps_generic_only(self):
        # Reduction never drops below 0 cost; with a huge graveyard the cost
        # floors at {0} and the creature still casts with no mana.
        game = create_game()
        p0 = game.players[0]
        gy = [Instant(name=f"S{i}", mana_cost=ManaCost.parse("{R}")) for i in range(15)]
        set_board_state(game, 0, hand=[TheDawningArchaic(owner=None)],
                        graveyard=gy, mana={ManaType.COLORLESS: 0})
        cast_spell(game, 0, "The Dawning Archaic")
        assert any(getattr(c, "name", "") == "The Dawning Archaic"
                   for c in game.get_battlefield(p0).get_all())


class TestAttackTrigger:
    def _setup(self, graveyard):
        game = create_game()
        p0 = game.players[0]
        archaic = TheDawningArchaic(owner=None)
        set_board_state(game, 0, battlefield=[archaic], graveyard=graveyard)
        archaic.summoning_sick = False
        archaic.register_triggers(game)  # simulate ETB registration
        return game, p0, archaic

    def test_single_target_autocast_and_exile(self):
        zap = ZapInstant()
        game, p0, archaic = self._setup([zap])
        from test_utils import declare_attackers
        declare_attackers(game, ["The Dawning Archaic"])
        _drain(game)
        assert game.players[1].life == 18          # Zap resolved (2 dmg)
        assert game.get_exile(p0).contains(zap)    # exiled instead of GY
        assert not game.get_graveyard(p0).contains(zap)

    def test_no_legal_target_is_noop(self):
        # Only a creature card in the graveyard — not a legal target.
        creature = Creature(name="Corpse", base_power=1, base_toughness=1)
        game, p0, archaic = self._setup([creature])
        from test_utils import declare_attackers
        declare_attackers(game, ["The Dawning Archaic"])
        _drain(game)
        assert game.players[1].life == 20
        assert game.get_graveyard(p0).contains(creature)

    def test_multiple_targets_player_chooses(self):
        zap_a = ZapInstant(name="ZapA")
        zap_b = ZapInstant(name="ZapB")
        game, p0, archaic = self._setup([zap_a, zap_b])
        # Pre-load the choose_card answer (declare_attackers prepends the
        # attacker choice, so this is popped afterward at resolution).
        p0._script.append(zap_b)
        from test_utils import declare_attackers
        declare_attackers(game, ["The Dawning Archaic"])
        _drain(game)
        assert game.get_exile(p0).contains(zap_b)         # chosen one exiled
        assert game.get_graveyard(p0).contains(zap_a)     # other untouched
        assert game.players[1].life == 18
