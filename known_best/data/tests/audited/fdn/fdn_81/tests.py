"""Chandra's +2 and −4 through canonical loyalty activation."""

import pytest
from engine.game import destroy
from cards.fdn.fdn_81.card_impl import ChandraFlameshaper
from engine.abilities import AbilityError
from engine.card import Creature, Planeswalker
from engine.decisions import Decision, DecisionKind, GameRef
from test_utils import Intent
from engine.types import ManaCost, ManaType, Phase
from test_utils import (
    activate_loyalty_ability,
    behavioral_game,
    create_game,
    enter_permanent,
    object_preference,
    prefer,
    put_on_battlefield,
    resolve_stack,
)


def test_is_planeswalker():
    assert isinstance(ChandraFlameshaper(), Planeswalker)


def test_name():
    assert ChandraFlameshaper().name == "Chandra, Flameshaper"


def test_mana_cost():
    assert ChandraFlameshaper().mana_cost == ManaCost.parse("{5}{R}{R}")


def test_plus_two_adds_mana_and_exiles_three_cards():
    game = behavioral_game()
    player = game.players[0]
    card = enter_permanent(game, player, ChandraFlameshaper())
    before = len(game.get_library(player).get_all())
    activate_loyalty_ability(game, player, card, 0)
    assert card.loyalty == 8 and player.mana_pool.total() == 0
    resolve_stack(game)
    assert player.mana_pool.get(ManaType.RED) == 3
    assert len(game.get_exile(player).get_all()) == 3
    assert len(game.get_library(player).get_all()) == before - 3
    assert not game.get_hand(player).get_all()


def test_plus_two_handles_fewer_than_three_library_cards():
    game = create_game()
    player = game.players[0]
    game.phase, game.step = Phase.PRECOMBAT_MAIN, None
    player.set_baseline(Intent(pattern=GameRef()))
    top = Creature(name="Only card", base_power=1, base_toughness=1, owner=player)
    game.get_library(player).add(top)
    card = enter_permanent(game, player, ChandraFlameshaper())
    activate_loyalty_ability(game, player, card, 0)
    resolve_stack(game)
    assert game.get_exile(player).get_all() == [top]
    assert not game.get_library(player).get_all()
    assert player.mana_pool.get(ManaType.RED) == 3


def test_plus_two_cannot_be_repeated_in_the_same_turn():
    game = behavioral_game()
    player = game.players[0]
    card = enter_permanent(game, player, ChandraFlameshaper())
    activate_loyalty_ability(game, player, card, 0)
    resolve_stack(game)
    with pytest.raises(AbilityError):
        activate_loyalty_ability(game, player, card, 0)
    assert card.loyalty == 8 and player.mana_pool.get(ManaType.RED) == 3
    assert len(game.get_exile(player).get_all()) == 3


def _minus4_setup(n_targets):
    """Chandra (loyalty 6) on p1's battlefield and ``n_targets`` 4/9 creatures
    on p2's, so no target dies to the damage."""
    game = behavioral_game()
    p1, p2 = game.players
    chandra = enter_permanent(game, p1, ChandraFlameshaper())
    targets = [
        put_on_battlefield(game, p2, Creature(name=f"Target{i}", base_power=4, base_toughness=9))
        for i in range(n_targets)
    ]
    return game, p1, chandra, targets


def _activate_minus4(game, player, chandra):
    activate_loyalty_ability(game, player, chandra, 2)
    resolve_stack(game)


class TestChandraFlameshaperMinus4Split:
    """−4: 8 damage divided as the controller chooses among any number of
    target creatures and/or planeswalkers (rules 601.2c-d via 602.2b)."""

    def test_intent_chooses_the_split(self) -> None:
        game, p1, chandra, (a, b) = _minus4_setup(2)
        prefer(p1, object_preference(game, a), object_preference(game, b), Decision.number(5))
        _activate_minus4(game, p1, chandra)
        assert (a.damage_marked, b.damage_marked) == (5, 3)
        assert chandra.loyalty == 2

    def test_baseline_takes_first_offered_lowest(self) -> None:
        # NUMBER options are offered ascending, so with no number preference
        # each queried target gets 1 and the last takes the remainder.
        game, p1, chandra, targets = _minus4_setup(3)
        prefer(p1, *(object_preference(game, t) for t in targets))
        _activate_minus4(game, p1, chandra)
        assert [t.damage_marked for t in targets] == [1, 1, 6]
        assert chandra.loyalty == 2

    def test_each_queried_target_must_get_at_least_one(self) -> None:
        # Asking for a zero share must not work: each of three targets gets at
        # least 1 of the 8 (rule 601.2d), however the division is queried.
        game, p1, chandra, targets = _minus4_setup(3)
        prefer(p1, *(object_preference(game, t) for t in targets), Decision.number(0))
        _activate_minus4(game, p1, chandra)
        damage = [t.damage_marked for t in targets]
        assert min(damage) >= 1 and sum(damage) == 8
        offered = [
            dict(option.attrs)["value"]
            for query in p1.transcript.queries(DecisionKind.NUMBER)
            for option in query.options
        ]
        assert all(1 <= value <= 6 for value in offered)
        assert chandra.loyalty == 2

    def test_single_target_takes_all_8_without_a_query(self) -> None:
        # A single target can only be dealt all 8; any amount offered is 8.
        game, p1, chandra, (only,) = _minus4_setup(1)
        prefer(p1, object_preference(game, only))
        _activate_minus4(game, p1, chandra)
        assert only.damage_marked == 8
        offered = [
            dict(option.attrs)["value"]
            for query in p1.transcript.queries(DecisionKind.NUMBER)
            for option in query.options
        ]
        assert all(value == 8 for value in offered)
        assert chandra.loyalty == 2

    def test_division_is_locked_in_at_activation(self) -> None:
        """The division is announced while activating (rule 601.2d via
        602.2b); a target that becomes illegal is dealt nothing and the other
        keeps exactly its share (608.2b)."""
        game, p1, chandra, (a, b) = _minus4_setup(2)
        prefer(p1, object_preference(game, a), object_preference(game, b), Decision.number(5))
        activate_loyalty_ability(game, p1, chandra, 2)
        destroy(game, a)
        resolve_stack(game)
        assert b.damage_marked == 3
        assert chandra.loyalty == 2
