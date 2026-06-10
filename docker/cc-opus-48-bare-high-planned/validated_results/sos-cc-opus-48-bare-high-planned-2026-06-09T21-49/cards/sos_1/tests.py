"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from engine.state_based_actions import resolve_state_based_actions
from test_utils import create_game, set_board_state, cast_spell, declare_attackers


class _Bolt(Instant):
    """Minimal instant: gains its controller 5 life on resolve."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Test Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 5


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class TestProperties:
    def test_static(self):
        c = TheDawningArchaic(owner=None)
        assert c.name == "The Dawning Archaic"
        assert c.mana_cost == ManaCost.parse("{10}")
        assert Keyword.REACH in c.keywords
        assert Supertype.LEGENDARY in c.supertypes
        assert (c.base_power, c.base_toughness) == (7, 7)


class TestCostReduction:
    def test_reduced_by_graveyard_instants(self):
        game = create_game()
        p0 = game.players[0]
        gy = [Instant(name=f"I{i}", mana_cost=ManaCost.parse("{R}")) for i in range(3)]
        set_board_state(game, 0, graveyard=gy,
                        hand=[TheDawningArchaic(owner=None)],
                        mana={ManaType.COLORLESS: 7})
        cast_spell(game, 0, "The Dawning Archaic")
        # {10} - 3 = {7}; 7 mana suffices, lands on battlefield.
        bf_names = [getattr(c, "name", "") for c in game.get_battlefield(p0).get_all()]
        assert "The Dawning Archaic" in bf_names

    def test_no_reduction_empty_graveyard(self):
        game = create_game()
        p0 = game.players[0]
        set_board_state(game, 0, graveyard=[],
                        hand=[TheDawningArchaic(owner=None)],
                        mana={ManaType.COLORLESS: 7})
        # No reduction → 7 < 10 → cast fails, card stays in hand.
        try:
            cast_spell(game, 0, "The Dawning Archaic")
        except Exception:
            pass
        hand_names = [getattr(c, "name", "") for c in game.get_hand(p0).get_all()]
        assert "The Dawning Archaic" in hand_names


class TestAttackTrigger:
    def test_attack_casts_from_graveyard_and_exiles(self):
        game = create_game()
        p0 = game.players[0]
        archaic = TheDawningArchaic(owner=p0, controller=p0)
        bolt = _Bolt()
        set_board_state(game, 0, battlefield=[archaic], graveyard=[bolt], life=20)
        archaic.summoning_sick = False
        archaic.is_tapped = False
        archaic.register_triggers(game)
        # Script: yes (may), then choose the bolt.
        p0._script.extend([True, bolt])
        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_stack(game)
        # Bolt resolved (life +5) and was exiled instead of graveyard.
        assert p0.life == 25
        assert p0.zones[Zone.EXILE].contains(bolt)
        assert not p0.zones[Zone.GRAVEYARD].contains(bolt)

    def test_attack_may_decline(self):
        game = create_game()
        p0 = game.players[0]
        archaic = TheDawningArchaic(owner=p0, controller=p0)
        bolt = _Bolt()
        set_board_state(game, 0, battlefield=[archaic], graveyard=[bolt], life=20)
        archaic.summoning_sick = False
        archaic.register_triggers(game)
        p0._script.extend([False])  # decline
        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_stack(game)
        assert p0.life == 20
        assert p0.zones[Zone.GRAVEYARD].contains(bolt)

    def test_attack_empty_graveyard_noop(self):
        game = create_game()
        p0 = game.players[0]
        archaic = TheDawningArchaic(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[], life=20)
        archaic.summoning_sick = False
        archaic.register_triggers(game)
        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_stack(game)
        assert p0.life == 20
