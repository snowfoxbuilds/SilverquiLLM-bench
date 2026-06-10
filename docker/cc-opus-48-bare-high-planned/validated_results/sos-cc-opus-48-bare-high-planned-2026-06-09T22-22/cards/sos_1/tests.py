"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from engine.state_based_actions import resolve_state_based_actions
from test_utils import create_game, set_board_state, cast_spell, declare_attackers


class MarkerSpell(Instant):
    """Test instant: gains its controller 5 life on resolve (no targets)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Marker Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 5


def _drain_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class TestProperties:
    def test_basics(self):
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")
        assert card.base_power == 7 and card.base_toughness == 7
        assert Keyword.REACH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes


class TestCostReduction:
    def test_reduced_by_graveyard_instants(self):
        game = create_game()
        p0 = game.players[0]
        gy = [MarkerSpell(owner=None) for _ in range(3)]
        set_board_state(game, 0, hand=[TheDawningArchaic(owner=None)],
                        graveyard=gy, mana={ManaType.COLORLESS: 7})
        # 10 - 3 instants = 7; exactly affordable.
        cast_spell(game, 0, "The Dawning Archaic")
        bf_names = [c.name for c in game.get_battlefield(p0).get_all()]
        assert "The Dawning Archaic" in bf_names

    def test_no_reduction_empty_graveyard(self):
        game = create_game()
        p0 = game.players[0]
        set_board_state(game, 0, hand=[TheDawningArchaic(owner=None)],
                        mana={ManaType.COLORLESS: 7})
        # Only 7 mana, no reduction → cannot cast.
        try:
            cast_spell(game, 0, "The Dawning Archaic")
        except Exception:
            pass
        bf_names = [c.name for c in game.get_battlefield(p0).get_all()]
        assert "The Dawning Archaic" not in bf_names


class TestAttackTrigger:
    def test_free_cast_then_exile(self):
        spell = MarkerSpell(owner=None)
        # Script: choose to cast (yes), then which spell (the marker).
        game = create_game(scripts=([True, spell], []))
        p0 = game.players[0]
        dawning = TheDawningArchaic(owner=None)
        set_board_state(game, 0, battlefield=[dawning], graveyard=[spell])
        dawning.summoning_sick = False
        dawning.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])
        _drain_stack(game)

        # The marker resolved (life +5) and was exiled instead of graveyard.
        assert p0.life == 25
        assert game.get_exile(p0).contains(spell)
        assert not game.get_graveyard(p0).contains(spell)

    def test_may_decline(self):
        spell = MarkerSpell(owner=None)
        game = create_game(scripts=([False], []))
        p0 = game.players[0]
        dawning = TheDawningArchaic(owner=None)
        set_board_state(game, 0, battlefield=[dawning], graveyard=[spell])
        dawning.summoning_sick = False
        dawning.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])
        _drain_stack(game)

        # Declined: spell stays in graveyard, no life change.
        assert p0.life == 20
        assert game.get_graveyard(p0).contains(spell)

    def test_no_legal_target_noop(self):
        # Empty graveyard → trigger does nothing (no yes/no even asked).
        game = create_game(scripts=([], []))
        p0 = game.players[0]
        dawning = TheDawningArchaic(owner=None)
        set_board_state(game, 0, battlefield=[dawning])
        dawning.summoning_sick = False
        dawning.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])
        _drain_stack(game)
        assert p0.life == 20
