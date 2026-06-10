"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, declare_attackers, set_board_state


def _instant(name: str = "Spark") -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{R}"))


class TestProperties:
    def test_static_data(self) -> None:
        card = TheDawningArchaic()
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")
        assert card.base_power == 7 and card.base_toughness == 7
        assert Keyword.REACH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes


class TestCostReduction:
    def test_one_less_per_instant_sorcery_in_graveyard(self) -> None:
        """4 instants in graveyard (creature ignored) → pay {6}."""
        game = create_game()
        archaic = TheDawningArchaic()
        yard = [_instant(f"I{i}") for i in range(4)]
        yard.append(Creature(name="Dead Bear", base_power=2, base_toughness=2))
        set_board_state(
            game, 0, hand=[archaic], graveyard=yard,
            mana={ManaType.COLORLESS: 6},
        )
        from test_utils import cast_spell

        cast_spell(game, 0, "The Dawning Archaic")
        assert game.players[0].zones[Zone.BATTLEFIELD].contains(archaic)
        assert game.players[0].mana_pool.total() == 0

    def test_reduction_clamps_at_zero(self) -> None:
        """12 instants in graveyard → cast for free (clamped, not negative)."""
        game = create_game()
        archaic = TheDawningArchaic()
        set_board_state(
            game, 0, hand=[archaic],
            graveyard=[_instant(f"I{i}") for i in range(12)],
        )
        from test_utils import cast_spell

        cast_spell(game, 0, "The Dawning Archaic")
        assert game.players[0].zones[Zone.BATTLEFIELD].contains(archaic)


class TestAttackTrigger:
    def _setup(self, graveyard, p1_script, p2_script):
        game = create_game(scripts=(p1_script, p2_script))
        archaic = TheDawningArchaic()
        set_board_state(game, 0, battlefield=[archaic], graveyard=graveyard)
        archaic.summoning_sick = False
        archaic.register_triggers(game)
        return game, archaic

    def test_attack_casts_single_spell_and_exiles_it(self) -> None:
        """Lone instant in graveyard is auto-selected, cast free, then exiled."""
        spark = _instant()
        game, _ = self._setup([spark], ["pass", "pass"], ["pass", "pass"])
        p1 = game.players[0]

        declare_attackers(game, ["The Dawning Archaic"])
        assert len(game.stack) == 1  # the attack trigger
        priority_loop(game)

        assert p1.zones[Zone.EXILE].contains(spark)
        assert not p1.zones[Zone.GRAVEYARD].contains(spark)

    def test_attack_with_empty_graveyard_is_noop(self) -> None:
        game, _ = self._setup([], ["pass"], ["pass"])

        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)

        assert game.stack.is_empty()
        assert len(game.players[0].zones[Zone.GRAVEYARD]) == 0

    def test_may_decline_with_multiple_candidates(self) -> None:
        """choose_card → None declines; both spells stay in the graveyard."""
        s1, s2 = _instant("A"), _instant("B")
        game, _ = self._setup([s1, s2], ["pass", None], ["pass"])
        p1 = game.players[0]

        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)

        assert p1.zones[Zone.GRAVEYARD].contains(s1)
        assert p1.zones[Zone.GRAVEYARD].contains(s2)
        assert len(p1.zones[Zone.EXILE]) == 0

    def test_chosen_of_multiple_is_cast_other_stays(self) -> None:
        s1, s2 = _instant("A"), _instant("B")
        # p1 script: pass, choose s2 from graveyard, pass again to resolve it.
        game, _ = self._setup([s1, s2], ["pass", s2, "pass"], ["pass", "pass"])
        p1 = game.players[0]

        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)

        assert p1.zones[Zone.EXILE].contains(s2)
        assert p1.zones[Zone.GRAVEYARD].contains(s1)
