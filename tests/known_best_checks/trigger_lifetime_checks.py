"""An enters trigger keeps what was fixed as it went on the stack — its
controller, its targets' legality, its mode — and acts on its source only
while the source is still there (rules 603.3a, 608.2b, 701.14b).

Run inside ``known_best/workspace`` by
``tests/test_known_best_gameplay_regressions.py``: the module imports the
workspace's own ``engine``, ``cards`` and ``test_interface``.
"""

from __future__ import annotations

from cards.fdn.fdn_31.card_impl import BigfinBouncer, BigfinBouncerAbility1
from cards.fdn.fdn_40.card_impl import HighFaeTrickster
from cards.fdn.fdn_99.card_impl import (
    ApothecaryStomper,
    ApothecaryStomperAbility2,
    ApothecaryStomperAbility4,
)
from cards.fdn.fdn_138.card_impl import BanishingLight, BanishingLightAbility1
from cards.fdn.fdn_144.card_impl import MischievousPup, MischievousPupAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_203.card_impl import InvoluntaryEmployment
from cards.fdn.fdn_211.card_impl import AffectionateIndrik, AffectionateIndrikAbility1
from cards.fdn.fdn_214.card_impl import BrokenWings
from cards.fdn.fdn_272.card_impl import Plains
from engine.types import ManaType, Phase, Zone
from test_interface import Side, card, create_game

from silverquillm.table import Table, appears, gains_control, life, moves, off_stack, on_stack, taps

MAIN = (Phase.PRECOMBAT_MAIN, 0)


def _plains():
    return [card(Plains) for _ in range(3)]


def _tap(t, lands):
    """Player 0 taps ``lands`` for mana, so a pool of one colour pays the
    other spell (Known-Best's auto-payment can spend the wrong colour, #169)."""
    for land in lands:
        t.act(0, land, then=[taps(land)])


def _cast(t, seat, spell, *, choices=(), then=()):
    """``seat`` casts ``spell`` and both pass, so it resolves, causing ``then``;
    ``choices`` answer ``seat``'s questions until it next acts."""
    t.act(seat, spell, then=[moves(spell, Zone.STACK)])
    t.pass_(seat, choices=list(choices))
    t.pass_(1 - seat, then=list(then))


def test_banishing_light_gone_before_its_trigger_exiles_nothing():
    light, wings, lions = card(BanishingLight), card(BrokenWings), card(SavannahLions)
    t = Table(create_game(
        Side(hand=[light], mana={ManaType.WHITE: 3}),
        Side(hand=[wings], battlefield=[lions], mana={ManaType.GREEN: 3}),
        start=MAIN,
    ))
    _cast(t, 0, light, choices=[lions], then=[moves(light, Zone.BATTLEFIELD), on_stack(BanishingLightAbility1, 0)])
    t.pass_(0)
    t.act(1, wings, choices=[light], then=[moves(wings, Zone.STACK)])
    t.pass_(1)
    # Known-Best models the exile's end as a leaves-the-battlefield trigger
    # (#169); with nothing exiled it does nothing.
    t.pass_(0, then=[moves(wings, Zone.GRAVEYARD), moves(light, Zone.GRAVEYARD), on_stack(BanishingLightAbility1, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(BanishingLightAbility1)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(BanishingLightAbility1)])
    final = t.run()
    assert final.where(lions) is Zone.BATTLEFIELD


def test_bigfin_bouncers_trigger_keeps_its_controller_when_the_bouncer_is_stolen():
    bigfin, employment, lions = card(BigfinBouncer), card(InvoluntaryEmployment), card(SavannahLions)
    t = Table(create_game(
        Side(hand=[bigfin], mana={ManaType.BLUE: 4}),
        Side(hand=[employment], battlefield=[lions, HighFaeTrickster], mana={ManaType.RED: 4}),
        start=MAIN,
    ))
    _cast(t, 0, bigfin, choices=[lions], then=[moves(bigfin, Zone.BATTLEFIELD), on_stack(BigfinBouncerAbility1, 0)])
    t.pass_(0)
    t.act(1, employment, choices=[bigfin], then=[moves(employment, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(employment, Zone.GRAVEYARD), gains_control(bigfin, 1), appears(1)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(BigfinBouncerAbility1), moves(lions, Zone.HAND)], note="still player 0's opponent's creature")
    t.run()


def test_affectionate_indrik_back_in_hand_fights_nothing():
    indrik, pup, lions, plains = card(AffectionateIndrik), card(MischievousPup), card(SavannahLions), _plains()
    t = Table(create_game(
        Side(hand=[indrik, pup], battlefield=plains, mana={ManaType.GREEN: 6}),
        Side(battlefield=[lions]),
        start=MAIN,
    ))
    _cast(t, 0, indrik, choices=[lions], then=[moves(indrik, Zone.BATTLEFIELD), on_stack(AffectionateIndrikAbility1, 0)])
    _tap(t, plains)
    _cast(t, 0, pup, choices=[indrik], then=[moves(pup, Zone.BATTLEFIELD), on_stack(MischievousPupAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(MischievousPupAbility2), moves(indrik, Zone.HAND)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(AffectionateIndrikAbility1)])
    final = t.run()
    assert final.where(lions) is Zone.BATTLEFIELD


def test_an_untargeted_mode_still_resolves_after_its_source_leaves():
    stomper, pup, plains = card(ApothecaryStomper), card(MischievousPup), _plains()
    t = Table(create_game(Side(hand=[stomper, pup], battlefield=plains, mana={ManaType.GREEN: 6}), Side(), start=MAIN))
    _cast(t, 0, stomper, choices=[ApothecaryStomperAbility4],
          then=[moves(stomper, Zone.BATTLEFIELD), on_stack(ApothecaryStomperAbility2, 0)])
    _tap(t, plains)
    _cast(t, 0, pup, choices=[stomper], then=[moves(pup, Zone.BATTLEFIELD), on_stack(MischievousPupAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(MischievousPupAbility2), moves(stomper, Zone.HAND)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(ApothecaryStomperAbility2), life(0, 24)])
    t.run()
