"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.fdn.fdn_13.card_impl import FleetingFlight
from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import (
    _resolve_top_of_stack,
    cast_spell,
    create_game,
    declare_attackers,
    set_board_state,
)


class TestDawningArchaicStatics:
    def test_card_data(self):
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")
        assert card.base_power == 7 and card.base_toughness == 7
        assert Keyword.REACH in card.keywords


class TestDawningArchaicCostReduction:
    def test_costs_one_less_per_instant_sorcery_in_graveyard(self):
        game = create_game()
        graveyard = [FleetingFlight(owner=None) for _ in range(3)]
        graveyard.append(Creature(name="Dead Bear", base_power=2, base_toughness=2))
        set_board_state(
            game, 0,
            hand=[TheDawningArchaic(owner=None)],
            graveyard=graveyard,
            mana={ManaType.COLORLESS: 7},
        )
        # {10} − 3 (creature card doesn't count) = {7}; exactly 7 in pool.
        cast_spell(game, 0, "The Dawning Archaic")
        bf = game.get_battlefield(game.players[0])
        assert any(c.name == "The Dawning Archaic" for c in bf.get_all())
        assert game.players[0].mana_pool.total() == 0

    def test_reduction_clamps_at_zero(self):
        game = create_game()
        set_board_state(
            game, 0,
            hand=[TheDawningArchaic(owner=None)],
            graveyard=[FleetingFlight(owner=None) for _ in range(12)],
            mana={},
        )
        cast_spell(game, 0, "The Dawning Archaic")
        bf = game.get_battlefield(game.players[0])
        assert any(c.name == "The Dawning Archaic" for c in bf.get_all())

    def test_no_reduction_with_empty_graveyard(self):
        game = create_game()
        set_board_state(
            game, 0,
            hand=[TheDawningArchaic(owner=None)],
            graveyard=[],
            mana={ManaType.COLORLESS: 10},
        )
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.players[0].mana_pool.total() == 0


class TestDawningArchaicAttackTrigger:
    def _setup_attacking_archaic(self, graveyard_spells):
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=None)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(
            game, 0, hand=[archaic], battlefield=[bear],
            mana={ManaType.COLORLESS: 10},
        )
        cast_spell(game, 0, "The Dawning Archaic")
        set_board_state(game, 0, graveyard=graveyard_spells)
        archaic.summoning_sick = False
        return game, p1, archaic, bear

    def test_attack_casts_sole_spell_from_graveyard_then_exiles_it(self):
        flight = FleetingFlight(owner=None)
        game, p1, archaic, bear = self._setup_attacking_archaic([flight])
        declare_attackers(game, ["The Dawning Archaic"])
        # Single candidate is auto-selected; only the spell's target is asked.
        p1._script.append(bear)
        _resolve_top_of_stack(game)
        assert bear.plus_one_counters == 1
        assert game.get_exile(p1).contains(flight)
        assert not game.get_graveyard(p1).contains(flight)

    def test_attack_with_empty_graveyard_does_nothing(self):
        game, p1, archaic, bear = self._setup_attacking_archaic([])
        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_top_of_stack(game)
        assert bear.plus_one_counters == 0
        assert len(game.get_exile(p1)) == 0

    def test_attack_with_multiple_candidates_prompts_choice(self):
        chosen_spell = FleetingFlight(owner=None)
        other_spell = FleetingFlight(owner=None)
        game, p1, archaic, bear = self._setup_attacking_archaic(
            [chosen_spell, other_spell]
        )
        declare_attackers(game, ["The Dawning Archaic"])
        p1._script.append(chosen_spell)  # choose_card answer
        p1._script.append(bear)          # spell target
        _resolve_top_of_stack(game)
        assert game.get_exile(p1).contains(chosen_spell)
        assert game.get_graveyard(p1).contains(other_spell)

    def test_decline_optional_cast(self):
        spell_a = FleetingFlight(owner=None)
        spell_b = FleetingFlight(owner=None)
        game, p1, archaic, bear = self._setup_attacking_archaic([spell_a, spell_b])
        declare_attackers(game, ["The Dawning Archaic"])
        p1._script.append(None)  # decline the "may" cast
        _resolve_top_of_stack(game)
        assert game.get_graveyard(p1).contains(spell_a)
        assert game.get_graveyard(p1).contains(spell_b)
        assert len(game.get_exile(p1)) == 0
