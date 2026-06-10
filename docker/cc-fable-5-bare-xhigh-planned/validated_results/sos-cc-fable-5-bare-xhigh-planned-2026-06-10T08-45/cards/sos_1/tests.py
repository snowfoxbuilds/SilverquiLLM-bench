"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.casting import resolve_top
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import (
    TestSetupError,
    cast_spell,
    create_game,
    declare_attackers,
    set_board_state,
)


class TestDawningArchaicCostReduction:
    def test_one_less_per_instant_or_sorcery_in_graveyard(self):
        game = create_game()
        archaic = TheDawningArchaic(owner=None)
        graveyard = [
            Instant(name=f"Spent Instant {i}", mana_cost=ManaCost.parse("{1}"))
            for i in range(3)
        ] + [Creature(name="Dead Bear", base_power=2, base_toughness=2)]
        set_board_state(
            game, 0, hand=[archaic], graveyard=graveyard,
            mana={ManaType.COLORLESS: 7},
        )
        # {10} - 3 = {7}; the dead creature does not count.
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(game.players[0]).contains(archaic)

    def test_no_reduction_with_empty_graveyard(self):
        game = create_game()
        archaic = TheDawningArchaic(owner=None)
        set_board_state(game, 0, hand=[archaic], mana={ManaType.COLORLESS: 9})
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "The Dawning Archaic")

    def test_has_reach(self):
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords


class TestDawningArchaicAttackTrigger:
    def _setup_attack(self, graveyard_cards):
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1)
        set_board_state(game, 0, battlefield=[archaic], graveyard=graveyard_cards)
        # set_board_state places cards directly; register triggers as the
        # engine would on entering the battlefield.
        archaic.register_triggers(game)
        archaic.summoning_sick = False
        declare_attackers(game, ["The Dawning Archaic"])
        return game, p1, archaic

    def test_attack_casts_sole_spell_free_then_exiles_it(self):
        spell = Sorcery(name="Dusty Ritual", mana_cost=ManaCost.parse("{4}"))
        game, p1, _ = self._setup_attack([spell])
        # Attack trigger is on the stack; resolving it free-casts the only
        # legal card (auto-selected), then the spell itself resolves.
        resolve_top(game)
        resolve_top(game)
        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)

    def test_attack_with_choice_prompts_and_can_decline(self):
        spell_a = Instant(name="Option A", mana_cost=ManaCost.parse("{1}"))
        spell_b = Instant(name="Option B", mana_cost=ManaCost.parse("{2}"))
        game, p1, _ = self._setup_attack([spell_a, spell_b])
        p1._script.append(None)  # decline the "may" choice
        resolve_top(game)
        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(spell_a)
        assert game.get_graveyard(p1).contains(spell_b)

    def test_attack_with_choice_casts_chosen_spell(self):
        spell_a = Instant(name="Option A", mana_cost=ManaCost.parse("{1}"))
        spell_b = Instant(name="Option B", mana_cost=ManaCost.parse("{2}"))
        game, p1, _ = self._setup_attack([spell_a, spell_b])
        p1._script.append(spell_b)
        resolve_top(game)
        resolve_top(game)
        assert game.get_exile(p1).contains(spell_b)
        assert game.get_graveyard(p1).contains(spell_a)

    def test_attack_with_no_instant_or_sorcery_does_nothing(self):
        bear = Creature(name="Dead Bear", base_power=2, base_toughness=2)
        game, p1, _ = self._setup_attack([bear])
        resolve_top(game)
        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(bear)
