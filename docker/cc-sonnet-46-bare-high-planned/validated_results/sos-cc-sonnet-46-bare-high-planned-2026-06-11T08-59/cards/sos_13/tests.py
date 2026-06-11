"""Tests for Emeritus of Truce // Swords to Plowshares (sos_13)."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares, SwordsToPlowshares
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state
from test_utils import _resolve_top_of_stack


def _setup():
    game = create_game()
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    return game


def test_etb_creates_inkling_token():
    """ETB trigger creates a 1/1 white-black Inkling with flying for target player."""
    game = _setup()
    p0, p1 = game.players

    emeritus = EmeritusOfTruceSwordsToPlowshares()
    emeritus.owner = p0
    emeritus.controller = p0
    set_board_state(game, 0, battlefield=[emeritus])
    emeritus.register_triggers(game)

    # No opponent advantage — not prepared. Target p0 for the token.
    p0._script.appendleft(p0)  # choose_card: target player = p0

    # Fire the ETB trigger manually
    from engine.events import EntersBattlefieldTriggeredEvent
    game.trigger_manager.fire_event(
        game,
        EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p0),
    )
    _resolve_top_of_stack(game)

    # p0's battlefield should have the Inkling token
    bf = game.get_battlefield(p0)
    inklings = [c for c in bf.get_all() if "Inkling" in getattr(c, "subtypes", set())]
    assert len(inklings) == 1
    assert inklings[0].base_power == 1
    assert inklings[0].base_toughness == 1
    assert Keyword.FLYING in getattr(inklings[0], "keywords", Keyword(0))


def test_becomes_prepared_when_opponent_has_more_creatures():
    """Becomes prepared when an opponent controls more creatures after ETB."""
    game = _setup()
    p0, p1 = game.players

    emeritus = EmeritusOfTruceSwordsToPlowshares()
    emeritus.owner = p0
    emeritus.controller = p0

    # p1 controls 2 creatures; p0 controls only emeritus (1 creature)
    opp_creature1 = Creature(name="Opp1", base_power=2, base_toughness=2)
    opp_creature2 = Creature(name="Opp2", base_power=2, base_toughness=2)
    set_board_state(game, 0, battlefield=[emeritus])
    set_board_state(game, 1, battlefield=[opp_creature1, opp_creature2])
    emeritus.register_triggers(game)

    # Give the Inkling to p1 so p0's creature count stays at 1 (emeritus only),
    # while p1 gets 3 creatures (2 existing + 1 Inkling) → p1 > p0 → prepared.
    p0._script.appendleft(p1)

    from engine.events import EntersBattlefieldTriggeredEvent
    game.trigger_manager.fire_event(
        game,
        EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p0),
    )
    _resolve_top_of_stack(game)

    assert emeritus._prepared, "Should be prepared when opponent has more creatures"


def test_not_prepared_when_equal_creatures():
    """Does not become prepared when opponent does NOT have more creatures."""
    game = _setup()
    p0, p1 = game.players

    emeritus = EmeritusOfTruceSwordsToPlowshares()
    emeritus.owner = p0
    emeritus.controller = p0
    opp_creature = Creature(name="Opp1", base_power=2, base_toughness=2)
    set_board_state(game, 0, battlefield=[emeritus])
    set_board_state(game, 1, battlefield=[opp_creature])
    emeritus.register_triggers(game)

    # p0: 1 creature (emeritus), p1: 1 creature — equal, not more
    p0._script.appendleft(p0)

    from engine.events import EntersBattlefieldTriggeredEvent
    game.trigger_manager.fire_event(
        game,
        EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p0),
    )
    _resolve_top_of_stack(game)

    assert not emeritus._prepared, "Should NOT be prepared when opponent has same number"


def test_swords_exiles_creature_and_gains_life():
    """SwordsToPlowshares exiles target creature; its controller gains life = power."""
    game = _setup()
    p0, p1 = game.players

    target = Creature(name="BigCreature", base_power=5, base_toughness=5)
    set_board_state(game, 1, battlefield=[target])
    p1.life = 20

    swords = SwordsToPlowshares()
    swords.owner = p0
    swords.controller = p0
    swords.chosen_targets = [target]

    swords.on_resolve(game)

    assert game.get_exile(p1).contains(target), "Target should be in exile"
    assert not game.get_battlefield(p1).contains(target)
    assert p1.life == 25, "Creature's controller gains life equal to its power (5)"


def test_prepared_casts_swords_from_exile_and_unprepares():
    """While prepared, casting the Swords copy unprepares the creature."""
    game = _setup()
    p0, p1 = game.players

    emeritus = EmeritusOfTruceSwordsToPlowshares()
    emeritus.owner = p0
    emeritus.controller = p0
    emeritus._prepared = True

    # Opponent has a creature to target
    target = Creature(name="Target", base_power=3, base_toughness=3)
    set_board_state(game, 0, battlefield=[emeritus])
    set_board_state(game, 1, battlefield=[target])
    p0.life = 20

    # Activate the prepared ability
    ability = emeritus.get_activated_abilities()[0]
    assert ability.cost(game)  # should be True when prepared

    # Script: choose target (target creature for Swords)
    p0._script.appendleft(target)

    ability.effect(game)
    _resolve_top_of_stack(game)

    assert not emeritus._prepared, "Should be unprepared after casting Swords"
    assert game.get_exile(p1).contains(target), "Target should be exiled"
