"""Known-Best checks of which activations summoning sickness forbids (rule
302.6), with costs no FDN card has: a {T} cost that also sacrifices its source,
a {Q} cost, a cost that taps in words, and a granted quoted ability. They drive
``activate_ability`` directly, so they guard the engine without being graded
against candidates (ADR-018)."""

from __future__ import annotations

import pytest
from cards.fdn.fdn_146.card_impl import SavannahLions
from engine.abilities import (
    AbilityError,
    ActivatedAbilityInstance,
    activate_ability,
    has_tap_symbol_cost,
)
from engine.game import move_to_zone
from engine.types import Keyword, Zone
from test_utils import create_game, set_board_state


class TapSacrifice:
    text = "{T}, Sacrifice this creature: You gain 1 life."


class Untap:
    text = "{Q}: You gain 1 life."


class TapInWords:
    text = "Tap an untapped creature you control: You gain 1 life."


class Granted:
    text = 'Enchanted creature has "{1}, {T}: You gain 1 life."'


class GrantFromHand:
    text = '{3}, Exile this card from your hand: Target land gains "{T}: Add {C}{C}".'


class NoTap:
    text = "{1}, Sacrifice this creature: You gain 1 life."


@pytest.mark.parametrize("printed, expected", [
    (TapSacrifice, True), (Untap, True), (Granted, True), (TapInWords, False), (NoTap, False),
    (GrantFromHand, False), (None, False),
])
def test_tap_symbol_costs_are_read_from_the_printed_cost(printed, expected):
    assert has_tap_symbol_cost(printed) is expected


def _sick_lions():
    game = create_game()
    player = game.players[0]
    lions = SavannahLions(owner=player, controller=player)
    set_board_state(game, 0, battlefield=[lions])
    assert lions.summoning_sick
    return game, player, lions


def _ability(game, player, lions, printed, cost, gained):
    return ActivatedAbilityInstance(
        source=lions, controller=player, cost=cost,
        effect=lambda _game: gained.append(1), printed=printed,
    )


def _tap_and_sacrifice(game, source):
    source.is_tapped = True
    move_to_zone(game, source, Zone.BATTLEFIELD, Zone.GRAVEYARD)
    return True


def _untap(game, source):
    source.is_tapped = False
    return True


@pytest.mark.parametrize("printed, cost", [(TapSacrifice, _tap_and_sacrifice), (Untap, _untap), (Granted, _untap)])
def test_a_sick_creature_cannot_pay_a_tap_or_untap_symbol_and_nothing_is_paid(printed, cost):
    game, player, lions = _sick_lions()
    lions.is_tapped = printed is Untap
    gained: list[int] = []
    with pytest.raises(AbilityError, match="302.6|most recent turn"):
        activate_ability(game, player, _ability(game, player, lions, printed, cost, gained))
    assert game.get_battlefield(player).contains(lions)
    assert lions.is_tapped is (printed is Untap)
    assert game.stack.is_empty() and gained == []


def test_haste_lifts_the_restriction():
    game, player, lions = _sick_lions()
    lions.keywords |= Keyword.HASTE
    activate_ability(game, player, _ability(game, player, lions, TapSacrifice, _tap_and_sacrifice, []))
    assert game.get_graveyard(player).contains(lions)
    assert not game.stack.is_empty()


@pytest.mark.parametrize("printed", [TapInWords, NoTap])
def test_a_cost_without_the_symbol_is_not_restricted(printed):
    game, player, lions = _sick_lions()
    lions.is_tapped = True
    activate_ability(game, player, _ability(game, player, lions, printed, _tap_and_sacrifice, []))
    assert game.get_graveyard(player).contains(lions)
