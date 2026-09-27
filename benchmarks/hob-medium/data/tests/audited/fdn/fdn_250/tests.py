"""Reference test for FDN 250 — Burnished Hart.

"Search your library for UP TO TWO basic land cards" is a declinable resolution
choice (`choose_object(min=0, max=2)`), not an automatic grab. Basic lands are
detected by the Basic supertype (there is no `is_basic_land` flag).
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_250.card_impl import BurnishedHart
from engine.basic_lands import Forest
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import activate_card_ability, create_game, resolve_stack, set_board_state


def _put_in_library(game, player, card):
    lib = player.zones[Zone.LIBRARY]
    card.owner = player
    card.controller = player
    lib.add(card)
    card.instance_id = game.refs.instance_id(card, Zone.LIBRARY.value)
    return card


class TestBurnishedHartProperties:
    def test_static_data(self):
        h = BurnishedHart(owner=None)
        assert h.name == "Burnished Hart"
        assert h.mana_cost == ManaCost.parse("{3}")


class TestBurnishedHartSearch:
    def test_fetches_two_chosen_basics_tapped(self):
        game = create_game()
        p1 = game.players[0]
        hart = BurnishedHart(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hart], mana={ManaType.COLORLESS: 3})
        a = _put_in_library(game, p1, Forest())
        b = _put_in_library(game, p1, Forest())
        game.phase = Phase.PRECOMBAT_MAIN

        p1.start_intent("hart", Intent(
            pattern=GameRef(card=frozenset({("name", "Burnished Hart")})),
            preferences=(
                Decision.obj(instance=a.instance_id),
                Decision.obj(instance=b.instance_id),
            ),
        ))
        try:
            activate_card_ability(game, p1, hart)   # pays {3}, sacrifices itself
            resolve_stack(game)
        finally:
            p1.end_intent("hart")

        bf = game.get_battlefield(p1)
        assert bf.contains(a) and bf.contains(b)     # both fetched
        assert a.is_tapped and b.is_tapped           # entered tapped
        assert not game.get_battlefield(p1).contains(hart)   # sacrificed

    def test_declinable_search_no_basics(self):
        """With no basic land in the library the ability still resolves (the
        min=0 search finds nothing) — no crash, Hart sacrificed."""
        game = create_game()
        p1 = game.players[0]
        hart = BurnishedHart(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hart], mana={ManaType.COLORLESS: 3})
        game.phase = Phase.PRECOMBAT_MAIN
        p1.set_baseline(Intent(pattern=GameRef(), preferences=()))
        activate_card_ability(game, p1, hart)
        resolve_stack(game)
        assert not game.get_battlefield(p1).contains(hart)   # sacrificed, no error
