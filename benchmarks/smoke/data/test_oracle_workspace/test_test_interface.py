"""How the Test Interface is meant to be used (see test_interface.md).

They show a game built, played from the players' scripts and checked through
the Player View, and they fail when an engine change breaks what the interface
relies on.
"""

from dataclasses import replace

import pytest
from cards.fdn.fdn_134.card_impl import (
    AjaniCallerOfThePride,
    AjaniCallerOfThePrideAbility1,
    AjaniCallerOfThePrideAbility3,
)
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain, MountainAbility1

from test_interface import (
    Phase,
    PlayDiverged,
    Seen,
    Side,
    Step,
    Zone,
    act,
    act_illegal,
    card,
    create_game,
    pass_priority,
    player,
    run,
    view,
)


def test_a_constructed_position_is_what_the_view_shows():
    bolt = card(BurstLightning)
    game = create_game(Side(hand=[bolt], battlefield=[Mountain]), Side(life=15), start=(Step.UPKEEP, 1))
    v = view(game)
    assert (v.step, v.active, v.asked) == (Step.UPKEEP, 1, 1)
    assert v.where(bolt) is Zone.HAND and v.players[1].life == 15
    assert [seen.card for seen in v.players[0].battlefield] == [Mountain]


def test_a_spell_is_cast_and_resolves_as_expected():
    bolt, mountain = card(BurstLightning), card(Mountain)
    game = create_game(Side(hand=[bolt], battlefield=[mountain]), start=(Phase.PRECOMBAT_MAIN, 0))
    start = view(game)
    me, them = start.players

    tapped = replace(start, players=(replace(me, battlefield=(Seen(Mountain, 0, True, mountain),)), them))
    cast = replace(tapped, players=(replace(tapped.players[0], hand=()), them), stack=(Seen(BurstLightning, 0, False, bolt),))
    their_turn_to_answer = replace(cast, asked=1)
    resolved = replace(
        tapped,
        players=(replace(tapped.players[0], hand=(), graveyard=(Seen(BurstLightning, 0, False, bolt),)), replace(them, life=18)),
    )
    final = run(
        game,
        [
            act(MountainAbility1, view=tapped, note="tap the Mountain for R"),
            act(bolt, choices=[player(1)], view=cast, note="Burst Lightning targets player 1"),
            pass_priority(view=their_turn_to_answer),
        ],
        [pass_priority(view=resolved)],
    )
    assert final.players[1].life == 18 and final.where(bolt) is Zone.GRAVEYARD


def test_an_illegal_activation_is_refused_and_the_planeswalker_can_still_act():
    game = create_game(Side(battlefield=[AjaniCallerOfThePride]), start=(Phase.PRECOMBAT_MAIN, 0))
    start = view(game)
    activated = replace(start, stack=(Seen(AjaniCallerOfThePrideAbility1, 0),))
    final = run(
        game,
        [
            act_illegal(AjaniCallerOfThePrideAbility3, note="-8 needs more than Ajani's 4 loyalty"),
            act(AjaniCallerOfThePrideAbility1, view=activated),
            pass_priority(view=replace(activated, asked=1)),
        ],
        [pass_priority(view=start)],
    )
    assert not final.stack


def test_play_that_leaves_the_script_fails():
    game = create_game(Side(hand=[Plains]), start=(Phase.PRECOMBAT_MAIN, 0))
    with pytest.raises(PlayDiverged):
        run(game, [act(BurstLightning)], [])
