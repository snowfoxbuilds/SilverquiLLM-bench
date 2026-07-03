"""Tests for Emeritus of Truce // Swords to Plowshares (sos_13)."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares, SwordsToPlowshares
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import (
    advance_to_phase,
    create_game,
    set_board_state,
    _resolve_top_of_stack,
)


class BearCreature(Creature):
    def __init__(self, name="Bear", **kwargs):
        kwargs.setdefault("name", name)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)


def test_card_name():
    """Card name must be the full double-faced name."""
    card = EmeritusOfTruceSwordsToPlowshares()
    assert card.name == "Emeritus of Truce // Swords to Plowshares"


def test_etb_creates_inkling_token():
    """ETB trigger creates a 1/1 Inkling with Flying for target player."""
    game = create_game()
    p1 = game.players[0]
    p2 = game.players[1]

    emeritus = EmeritusOfTruceSwordsToPlowshares()
    set_board_state(game, 0, battlefield=[emeritus])

    from engine.player import DeterministicPlayer
    # Script p1 to choose p1 as target for the token
    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(p1)

    emeritus.register_triggers(game)

    from engine.events import EntersBattlefieldTriggeredEvent
    game.trigger_manager.fire_event(
        game,
        EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p1),
    )
    _resolve_top_of_stack(game)

    # P1 should have an Inkling on battlefield
    bf = game.get_battlefield(p1).get_all()
    inklings = [c for c in bf if "Inkling" in getattr(c, "subtypes", set())]
    assert len(inklings) == 1
    assert Keyword.FLYING in inklings[0].keywords


def test_prepared_when_opponent_has_more_creatures():
    """Becomes prepared if an opponent controls more creatures."""
    game = create_game()
    p1 = game.players[0]
    p2 = game.players[1]

    emeritus = EmeritusOfTruceSwordsToPlowshares()
    bear1 = BearCreature("OppBear1")
    bear2 = BearCreature("OppBear2")

    set_board_state(game, 0, battlefield=[emeritus])
    set_board_state(game, 1, battlefield=[bear1, bear2])

    from engine.player import DeterministicPlayer
    # Give the inkling to p2 so after ETB: p1=1 creature, p2=3 creatures → prepared.
    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(p2)

    emeritus.register_triggers(game)

    from engine.events import EntersBattlefieldTriggeredEvent
    game.trigger_manager.fire_event(
        game,
        EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p1),
    )
    _resolve_top_of_stack(game)

    assert emeritus.is_prepared


def test_not_prepared_when_you_have_more_or_equal_creatures():
    """Not prepared if controller has equal or more creatures than opponents."""
    game = create_game()
    p1 = game.players[0]

    emeritus = EmeritusOfTruceSwordsToPlowshares()
    set_board_state(game, 0, battlefield=[emeritus])

    from engine.player import DeterministicPlayer
    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(p1)

    emeritus.register_triggers(game)

    from engine.events import EntersBattlefieldTriggeredEvent
    game.trigger_manager.fire_event(
        game,
        EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p1),
    )
    _resolve_top_of_stack(game)

    # No opponents have more creatures (we have emeritus + inkling = 2, opponent has 0)
    assert not emeritus.is_prepared


def test_swords_exiles_creature_and_gains_life():
    """Swords to Plowshares exiles target creature; controller gains power in life."""
    game = create_game()
    p1 = game.players[0]
    p2 = game.players[1]

    swords = SwordsToPlowshares()
    target = BearCreature()  # power = 2

    set_board_state(game, 0, hand=[swords])
    set_board_state(game, 1, battlefield=[target])

    from engine.player import DeterministicPlayer
    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(target)

    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0
    p1.mana_pool.add(ManaType.WHITE, 1)

    from engine.casting import cast_spell as _cast
    _cast(game, p1, swords)
    _resolve_top_of_stack(game)

    # Target bear should be exiled, p2 gains 2 life
    assert target in game.get_exile(p2).get_all()
    assert p2.life == 22  # 20 + 2 (power)
