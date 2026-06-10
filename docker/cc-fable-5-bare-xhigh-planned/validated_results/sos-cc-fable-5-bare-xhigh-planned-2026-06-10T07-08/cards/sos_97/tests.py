"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    AbilityError,
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


@pytest.fixture(autouse=True)
def _reset_loyalty_tracker():
    clear_loyalty_tracking()
    yield
    clear_loyalty_tracking()


def _activate(game, pw, index: int, targets=None) -> None:
    """Activate loyalty ability *index* through the real ability pipeline."""
    player = pw.controller
    game.active_player_index = game.players.index(player)
    game.priority_player_index = game.active_player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    if targets is not None:
        pw.chosen_targets = targets
    ability = pw.get_loyalty_abilities()[index]
    activate_ability(
        game,
        player,
        LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=ability.loyalty_cost,
            effect=ability.effect,
            description=ability.description,
        ),
    )
    # Passes are consumed before the ability's own choices — prepend them.
    for p in game.players:
        p._script.appendleft("pass")
    priority_loop(game)


def _setup():
    game = create_game()
    pw = RalZarekGuestLecturer()
    set_board_state(game, 0, battlefield=[pw])
    return game, pw


def _bear(name: str, mv: int) -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2,
                    mana_cost=ManaCost.parse(f"{{{mv}}}"))


class TestProperties:
    def test_static_data(self) -> None:
        pw = RalZarekGuestLecturer()
        assert pw.name == "Ral Zarek, Guest Lecturer"
        assert pw.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert pw.starting_loyalty == 3 and pw.loyalty == 3
        assert CardType.PLANESWALKER in pw.card_types
        assert Supertype.LEGENDARY in pw.supertypes
        assert "Ral" in pw.subtypes


class TestPlusOneSurveil:
    def test_surveil_bins_chosen_keeps_rest_on_top(self) -> None:
        game, pw = _setup()
        p1 = game.players[0]
        bottom, second, top = _bear("Bottom", 1), _bear("Second", 1), _bear("Top", 1)
        for c in (bottom, second, top):
            c.owner = c.controller = p1
            p1.zones[Zone.LIBRARY].add(c)

        # Bin "Top", keep "Second" on top.
        p1._script.extend([top, None])
        _activate(game, pw, 0)

        assert pw.loyalty == 4
        assert p1.zones[Zone.GRAVEYARD].contains(top)
        assert p1.zones[Zone.LIBRARY].top(1)[0] is second

    def test_surveil_empty_library_noop(self) -> None:
        game, pw = _setup()
        _activate(game, pw, 0)
        assert pw.loyalty == 4


class TestMinusOneDiscard:
    def test_each_target_player_discards(self) -> None:
        game, pw = _setup()
        p1, p2 = game.players
        c1, c2 = _bear("Mine", 1), _bear("Theirs", 1)
        set_board_state(game, 0, battlefield=[pw], hand=[c1])
        set_board_state(game, 1, hand=[c2])

        p1._script.append(c1)
        p2._script.append(c2)
        _activate(game, pw, 1, targets=[p1, p2])

        assert pw.loyalty == 2
        assert p1.zones[Zone.GRAVEYARD].contains(c1)
        assert p2.zones[Zone.GRAVEYARD].contains(c2)

    def test_zero_targets_noop(self) -> None:
        game, pw = _setup()
        _activate(game, pw, 1, targets=[])
        assert pw.loyalty == 2


class TestMinusTwoReanimate:
    def test_returns_cheap_creature_to_battlefield(self) -> None:
        game, pw = _setup()
        p1 = game.players[0]
        cheap = _bear("Cheap", 3)
        set_board_state(game, 0, battlefield=[pw], graveyard=[cheap])

        _activate(game, pw, 2, targets=[cheap])

        assert pw.loyalty == 1
        assert p1.zones[Zone.BATTLEFIELD].contains(cheap)
        assert not p1.zones[Zone.GRAVEYARD].contains(cheap)

    def test_mv_four_is_not_returned(self) -> None:
        game, pw = _setup()
        p1 = game.players[0]
        pricey = _bear("Pricey", 4)
        set_board_state(game, 0, battlefield=[pw], graveyard=[pricey])

        _activate(game, pw, 2, targets=[pricey])

        assert p1.zones[Zone.GRAVEYARD].contains(pricey)
        assert not p1.zones[Zone.BATTLEFIELD].contains(pricey)

    def test_empty_graveyard_noop(self) -> None:
        game, pw = _setup()
        _activate(game, pw, 2)
        assert pw.loyalty == 1


class TestMinusSevenCoinFlips:
    def test_requires_loyalty_seven(self) -> None:
        game, pw = _setup()  # loyalty 3
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        ability = pw.get_loyalty_abilities()[3]
        with pytest.raises(AbilityError):
            activate_ability(
                game,
                pw.controller,
                LoyaltyAbilityInstance(
                    source=pw,
                    controller=pw.controller,
                    loyalty_cost=ability.loyalty_cost,
                    effect=ability.effect,
                ),
            )

    def test_opponent_skips_heads_turns(self) -> None:
        game, pw = _setup()
        p1, p2 = game.players
        pw.loyalty = 7
        game.rng = random.Random(7)
        reference = random.Random(7)
        expected_heads = sum(reference.randint(0, 1) for _ in range(5))
        assert expected_heads > 0  # seed chosen to produce at least one head

        _activate(game, pw, 3, targets=[p2])

        assert pw.loyalty == 0
        assert p2.skip_turns == expected_heads

        # The skipped turns actually pass p2 over in the turn rotation.
        for skipped in range(expected_heads):
            while not (game.phase is Phase.BEGINNING and game.step is Step.UNTAP):
                game.advance_phase()
            assert game.active_player is p1  # p2's turn was skipped
            game.advance_phase()  # leave untap so the wrap-search restarts
        assert p2.skip_turns == 0

    def test_zero_heads_skips_nothing(self) -> None:
        game, pw = _setup()
        p2 = game.players[1]
        pw.loyalty = 7

        class AllTails(random.Random):
            def randint(self, a, b):  # noqa: ARG002
                return 0

        game.rng = AllTails()
        _activate(game, pw, 3, targets=[p2])

        assert p2.skip_turns == 0
