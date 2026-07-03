"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Instant, Sorcery
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, declare_attackers, set_board_state


class TestStaticProperties:
    def test_stats_and_reach(self) -> None:
        card = TheDawningArchaic()
        assert card.base_power == 7
        assert card.base_toughness == 7
        assert Keyword.REACH in card.keywords
        assert card.mana_cost == ManaCost.parse("{10}")


class TestCostReduction:
    def test_costs_one_less_per_instant_or_sorcery_in_graveyard(self) -> None:
        game = create_game()
        graveyard = [
            Instant(name=f"I{i}", mana_cost=ManaCost.parse("{1}")) for i in range(3)
        ]
        set_board_state(
            game,
            0,
            hand=[TheDawningArchaic()],
            graveyard=graveyard,
            mana={ManaType.COLORLESS: 7},
        )
        cast_spell(game, 0, "The Dawning Archaic")
        p1 = game.players[0]
        assert any(
            c.name == "The Dawning Archaic"
            for c in game.get_battlefield(p1).get_all()
        )
        assert p1.mana_pool.total() == 0

    def test_creatures_in_graveyard_do_not_reduce(self) -> None:
        from engine.card import Creature

        game = create_game()
        set_board_state(
            game,
            0,
            hand=[TheDawningArchaic()],
            graveyard=[Creature(name="Bear", base_power=2, base_toughness=2)],
            mana={ManaType.COLORLESS: 9},
        )
        try:
            cast_spell(game, 0, "The Dawning Archaic")
            raised = False
        except Exception:
            raised = True
        assert raised, "9 mana must not pay a {10} cost with no instants/sorceries"


class TestAttackTrigger:
    def test_attack_casts_sole_graveyard_spell_and_exiles_it(self) -> None:
        """One legal candidate: auto-selected, cast for free, exiled after resolving."""
        game = create_game()
        p1, p2 = game.players
        archaic = TheDawningArchaic()
        bolt = BurstLightning()
        set_board_state(game, 0, battlefield=[archaic], graveyard=[bolt])
        archaic.summoning_sick = False

        declare_attackers(game, ["The Dawning Archaic"])
        # Resolve the attack trigger (p1 chooses bolt's target mid-resolution),
        # then the free-cast Burst Lightning.
        p1._script.extend(["pass", p2, "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)

        assert p2.life == 18  # Burst Lightning dealt its 2 damage
        assert game.get_exile(p1).contains(bolt)
        assert not game.get_graveyard(p1).contains(bolt)

    def test_attack_with_empty_graveyard_does_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        set_board_state(game, 0, battlefield=[archaic])
        archaic.summoning_sick = False

        declare_attackers(game, ["The Dawning Archaic"])
        p1._script.extend(["pass"])
        game.players[1]._script.extend(["pass"])
        priority_loop(game)
        assert game.stack.is_empty()

    def test_decline_with_multiple_candidates(self) -> None:
        """Two candidates: player is prompted and may decline with None."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        s1 = Sorcery(name="S1", mana_cost=ManaCost.parse("{1}"))
        s2 = Sorcery(name="S2", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, battlefield=[archaic], graveyard=[s1, s2])
        archaic.summoning_sick = False

        declare_attackers(game, ["The Dawning Archaic"])
        p1._script.extend(["pass", None, "pass"])
        game.players[1]._script.extend(["pass", "pass"])
        priority_loop(game)

        gy = game.get_graveyard(p1)
        assert gy.contains(s1) and gy.contains(s2)
        assert len(game.get_exile(p1).get_all()) == 0

    def test_chosen_spell_cast_from_two_candidates_is_exiled(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        s1 = Sorcery(name="S1", mana_cost=ManaCost.parse("{1}"))
        s2 = Sorcery(name="S2", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, battlefield=[archaic], graveyard=[s1, s2])
        archaic.summoning_sick = False

        declare_attackers(game, ["The Dawning Archaic"])
        p1._script.extend(["pass", s2, "pass"])
        game.players[1]._script.extend(["pass", "pass"])
        priority_loop(game)

        assert game.get_exile(p1).contains(s2)
        assert game.get_graveyard(p1).contains(s1)
