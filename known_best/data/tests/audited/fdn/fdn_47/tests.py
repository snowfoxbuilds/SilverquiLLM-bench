"""Mischievous Mystic observes actual draws, including the first-draw negative.

Its controller's draw step is their first draw of the turn and makes nothing;
Think Twice then draws their second, which makes one Faerie token.
"""

from cards.fdn.fdn_47.card_impl import MischievousMystic, MischievousMysticAbility2
from cards.fdn.fdn_165.card_impl import ThinkTwice
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from test_interface import Phase, Side, Step, Zone, card, create_game

from table import Table, appears, moves, off_stack, on_stack, taps


def test_second_draw_mints_blue_flying_faerie():
    think, islands, second = card(ThinkTwice), [card(Island), card(Island)], card(Plains)
    game = create_game(
        Side(),
        Side(
            battlefield=[MischievousMystic, *islands], hand=[think], library=[card(Plains), second]
        ),
        start=(Step.UPKEEP, 1),
    )
    t = Table(game)
    t.pass_to(Phase.PRECOMBAT_MAIN, 1)
    for island in islands:
        t.act(1, island, then=[taps(island)])
    t.act(
        1,
        think,
        then=[moves(think, Zone.STACK)],
        note="the draw step's draw was the first; nothing triggered",
    )
    t.pass_(1)
    t.pass_(
        0,
        then=[
            moves(think, Zone.GRAVEYARD),
            moves(second, Zone.HAND),
            on_stack(MischievousMysticAbility2, 1),
        ],
    )
    t.pass_(1)
    t.pass_(0, then=[off_stack(MischievousMysticAbility2), appears(1)])
    t.run()
