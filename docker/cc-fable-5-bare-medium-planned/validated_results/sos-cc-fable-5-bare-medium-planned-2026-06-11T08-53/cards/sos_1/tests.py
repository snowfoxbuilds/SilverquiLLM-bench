"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, cast_spell, declare_attackers, set_board_state


def _instants(n: int) -> list[Instant]:
    return [Instant(name=f"Spark {i}", mana_cost=ManaCost(generic=1)) for i in range(n)]


class TestDawningArchaicCost:
    def test_cost_reduced_by_instants_and_sorceries_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        bear = Creature(name="Dead Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[archaic], graveyard=_instants(3) + [bear])
        # {10} less {3} (the bear doesn't count) = {7}
        set_board_state(game, 0, mana={ManaType.COLORLESS: 7})
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(p1).contains(archaic)
        assert p1.mana_pool.total() == 0

    def test_reduction_clamps_at_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        set_board_state(game, 0, hand=[archaic], graveyard=_instants(12), mana={})
        cast_spell(game, 0, "The Dawning Archaic")  # free — 12 > 10, clamped
        assert game.get_battlefield(p1).contains(archaic)

    def test_has_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic().keywords


class TestDawningArchaicAttackTrigger:
    def _setup_attacker(self, game, graveyard_cards):
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        set_board_state(game, 0, hand=[archaic], mana={ManaType.COLORLESS: 10})
        cast_spell(game, 0, "The Dawning Archaic")
        set_board_state(game, 0, graveyard=graveyard_cards)
        archaic.summoning_sick = False
        return archaic

    def test_attack_casts_sole_instant_then_exiles_it(self) -> None:
        game = create_game(
            scripts=(["pass", "pass", "pass"], ["pass", "pass", "pass"])
        )
        p1 = game.players[0]
        spark = Instant(name="Spark", mana_cost=ManaCost(generic=1))
        self._setup_attacker(game, [spark])

        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)

        # The spell was cast for free and exiled instead of returning
        # to the graveyard.
        assert game.get_exile(p1).contains(spark)
        assert not game.get_graveyard(p1).contains(spark)

    def test_attack_with_empty_graveyard_is_noop(self) -> None:
        game = create_game(scripts=(["pass"], ["pass"]))
        p1 = game.players[0]
        self._setup_attacker(game, [])
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        assert len(game.get_exile(p1)) == 0

    def test_attack_may_decline_with_multiple_candidates(self) -> None:
        # p1's script: pass priority, then decline the choose_card prompt.
        game = create_game(scripts=(["pass", None], ["pass"]))
        p1 = game.players[0]
        sparks = _instants(2)
        self._setup_attacker(game, sparks)
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        # Declined: both stay in the graveyard, nothing exiled.
        assert all(game.get_graveyard(p1).contains(s) for s in sparks)
        assert len(game.get_exile(p1)) == 0

    def test_exile_replacement_is_one_shot(self) -> None:
        # After the trigger's spell is exiled, a different spell resolving
        # later goes to the graveyard normally.
        game = create_game(
            scripts=(["pass", "pass", "pass"], ["pass", "pass", "pass"])
        )
        p1 = game.players[0]
        spark = Instant(name="Spark", mana_cost=ManaCost(generic=1))
        self._setup_attacker(game, [spark])
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        assert game.get_exile(p1).contains(spark)

        other = Instant(name="Other Spell", mana_cost=ManaCost(generic=1))
        set_board_state(game, 0, hand=[other], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Other Spell")
        assert game.get_graveyard(p1).contains(other)
