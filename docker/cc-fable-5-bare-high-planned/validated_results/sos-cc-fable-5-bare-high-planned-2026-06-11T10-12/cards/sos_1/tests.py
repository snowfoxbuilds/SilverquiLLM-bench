"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Instant, Sorcery
from engine.casting import resolve_top
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import (
    TestSetupError,
    create_game,
    cast_spell,
    declare_attackers,
    set_board_state,
)


class ProbeSorcery(Sorcery):
    """Test-local sorcery: controller gains 3 life."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Probe Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 3


class TestCostReduction:
    def test_reduced_by_instants_and_sorceries_in_graveyard(self):
        """4 instant/sorcery cards in graveyard: {10} becomes {6}."""
        game = create_game()
        p1 = game.players[0]
        bones = [Instant(name=f"I{i}", mana_cost=ManaCost.parse("{1}")) for i in range(3)]
        bones.append(Sorcery(name="S0", mana_cost=ManaCost.parse("{1}")))
        archaic = TheDawningArchaic(owner=p1)
        set_board_state(game, 0, hand=[archaic], graveyard=bones,
                        mana={ManaType.COLORLESS: 6})
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(p1).contains(archaic)
        assert p1.mana_pool.total() == 0

    def test_non_spell_cards_do_not_reduce(self):
        """A creature card in the graveyard gives no reduction."""
        from engine.card import Creature

        game = create_game()
        p1 = game.players[0]
        dead_bear = Creature(name="Dead Bear", base_power=2, base_toughness=2)
        archaic = TheDawningArchaic(owner=p1)
        set_board_state(game, 0, hand=[archaic], graveyard=[dead_bear],
                        mana={ManaType.COLORLESS: 9})
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "The Dawning Archaic")

    def test_has_reach(self):
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords


class TestAttackTrigger:
    def _setup_attacker(self, game, graveyard_cards):
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1)
        set_board_state(game, 0, battlefield=[archaic], graveyard=graveyard_cards)
        archaic.register_triggers(game)
        archaic.summoning_sick = False
        return archaic

    def test_free_cast_then_exile_instead_of_graveyard(self):
        """Attacking lets you cast the lone sorcery in graveyard for free;
        after it resolves it is exiled, not put back into the graveyard."""
        game = create_game()
        p1 = game.players[0]
        probe = ProbeSorcery(owner=p1)
        self._setup_attacker(game, [probe])
        declare_attackers(game, ["The Dawning Archaic"])

        # Resolve the attack trigger (auto-selects the only candidate and
        # free-casts it), then resolve the spell itself.
        assert len(game.stack) == 1
        resolve_top(game)
        assert len(game.stack) == 1
        resolve_top(game)

        assert p1.life == 23
        assert p1.zones[Zone.EXILE].contains(probe)
        assert not p1.zones[Zone.GRAVEYARD].contains(probe)

    def test_empty_graveyard_trigger_no_ops(self):
        game = create_game()
        self._setup_attacker(game, [])
        declare_attackers(game, ["The Dawning Archaic"])
        assert len(game.stack) == 1
        resolve_top(game)
        assert game.stack.is_empty()

    def test_may_decline_with_multiple_candidates(self):
        """With two candidates the controller is prompted; None declines."""
        game = create_game()
        p1 = game.players[0]
        a = ProbeSorcery(owner=p1)
        b = Instant(name="Other", mana_cost=ManaCost.parse("{1}"))
        self._setup_attacker(game, [a, b])
        declare_attackers(game, ["The Dawning Archaic"])
        p1._script.append(None)  # decline the may-cast
        resolve_top(game)

        assert game.stack.is_empty()
        assert p1.zones[Zone.GRAVEYARD].contains(a)
        assert p1.zones[Zone.GRAVEYARD].contains(b)
        assert len(p1.zones[Zone.EXILE]) == 0

    def test_normally_cast_spells_still_go_to_graveyard(self):
        """The exile-instead replacement only applies to the trigger's cast."""
        game = create_game()
        p1 = game.players[0]
        probe = ProbeSorcery(owner=p1)
        self._setup_attacker(game, [probe])
        declare_attackers(game, ["The Dawning Archaic"])
        resolve_top(game)  # trigger → free-cast probe
        resolve_top(game)  # probe resolves → exiled

        # A different spell cast the normal way still hits the graveyard.
        other = ProbeSorcery(owner=p1)
        set_board_state(game, 0, hand=[other], mana={ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Probe Sorcery")
        assert p1.zones[Zone.GRAVEYARD].contains(other)
