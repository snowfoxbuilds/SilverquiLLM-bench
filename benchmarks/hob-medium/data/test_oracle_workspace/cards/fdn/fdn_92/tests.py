"""Reference test for FDN 92 — Rite of the Dragoncaller.

"Whenever you cast an instant or sorcery spell, create a 5/5 red Dragon
creature token with flying." The mint routes through ``make_creature_token``,
so this test drives the cast trigger and proves the produced token carries the
exact spec characteristics — a token has no mana cost, so its red colour must
be represented explicitly for ``get_colors`` (and the replay executor's colour
correlation) to see it.
"""

from __future__ import annotations

from cards.fdn.fdn_92.card_impl import RiteOfTheDragoncaller
from engine.card import Instant
from engine.events import SpellCastTriggeredEvent
from engine.protection import get_colors
from engine.types import Color, Keyword, ManaCost
from test_utils import create_game, set_board_state


def _dragons(game, player):
    bf = game.get_battlefield(player)
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False) and getattr(o, "name", None) == "Dragon"
    ]


def _cast_instant(game, p1) -> None:
    """Fire the cast event for an instant spell and resolve the trigger."""
    from engine.stack import priority_loop

    spell = Instant(name="Some Instant", owner=p1, controller=p1)
    game.trigger_manager.fire_event(
        game, SpellCastTriggeredEvent(spell=spell, player=p1)
    )
    priority_loop(game)


class TestRiteOfTheDragoncallerProperties:
    def test_static_data(self) -> None:
        c = RiteOfTheDragoncaller(owner=None)
        assert c.name == "Rite of the Dragoncaller"
        assert c.mana_cost == ManaCost.parse("{4}{R}{R}")


class TestRiteOfTheDragoncallerToken:
    def test_casting_instant_mints_flying_red_dragon(self) -> None:
        game = create_game()
        p1 = game.players[0]
        rite = RiteOfTheDragoncaller()
        set_board_state(game, 0, battlefield=[rite])
        rite.register_triggers(game)

        _cast_instant(game, p1)

        dragons = _dragons(game, p1)
        assert len(dragons) == 1
        dragon = dragons[0]
        assert dragon.subtypes == {"Dragon"}
        assert (dragon.base_power, dragon.base_toughness) == (5, 5)
        assert dragon.is_token is True
        assert get_colors(dragon) == {Color.RED}
        assert Keyword.FLYING in dragon.keywords
