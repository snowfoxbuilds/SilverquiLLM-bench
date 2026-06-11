"""Tests for Great Hall of the Biblioplex (sos_257)."""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state
from test_utils import _resolve_top_of_stack


def _setup():
    """Set up game with Great Hall on p0's battlefield."""
    hall = GreatHallOfTheBiblioplex()
    game = create_game()
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    p0 = game.players[0]
    set_board_state(game, 0, battlefield=[hall])
    hall.register_triggers(game)
    return game, hall


def test_basic_colorless_mana():
    """{T}: Add {C}."""
    game, hall = _setup()
    p0 = game.players[0]
    hall.is_tapped = False

    ability = hall.get_mana_abilities()[0]
    paid = ability.cost(game)
    assert paid
    ability.mana_produced(game)

    assert p0.mana_pool.get(ManaType.COLORLESS) == 1
    assert hall.is_tapped


def test_restricted_mana():
    """{T}, Pay 1 life: restricted mana stored separately from main pool."""
    game, hall = _setup()
    p0 = game.players[0]
    p0.life = 20
    hall.is_tapped = False

    # Script the color choice: RED
    p0._script.appendleft(ManaType.RED)

    ability = hall.get_mana_abilities()[1]
    paid = ability.cost(game)
    assert paid
    assert hall.is_tapped
    assert p0.life == 19  # paid 1 life

    ability.mana_produced(game)

    # Restricted mana should be in _restricted_is_mana, not in main pool
    assert p0.mana_pool._restricted_is_mana.get(ManaType.RED, 0) == 1
    assert p0.mana_pool.get(ManaType.RED) == 0


def test_restricted_mana_usable_for_instant():
    """Restricted mana can be used to cast an instant."""
    game, hall = _setup()
    p0 = game.players[0]
    p0.life = 20
    hall.is_tapped = False

    # Add restricted RED mana directly
    p0.mana_pool.add_restricted(ManaType.RED, 1)

    # Create a 1-generic instant
    instant = Instant(name="TestInstant", mana_cost=ManaCost(generic=1))
    instant.on_resolve = lambda g: None
    set_board_state(game, 0, hand=[instant], battlefield=[hall])

    from engine.casting import cast_spell
    cast_spell(game, p0, instant)  # should succeed using restricted mana
    _resolve_top_of_stack(game)

    # Spell should be in graveyard (resolved normally)
    assert game.get_graveyard(p0).contains(instant) or game.get_exile(p0).contains(instant)


def test_animation_adds_creature_type():
    """{5}: Hall becomes 2/4 Wizard creature (still a land)."""
    game, hall = _setup()
    p0 = game.players[0]
    p0.mana_pool.add(ManaType.COLORLESS, 5)

    ability = hall.get_activated_abilities()[0]
    paid = ability.cost(game)
    assert paid
    ability.effect(game)

    assert CardType.CREATURE in hall.card_types
    assert CardType.LAND in hall.card_types
    assert "Wizard" in hall.subtypes
    assert hall.power == 2
    assert hall.toughness == 4


def test_pump_trigger_on_instant_cast():
    """While animated, casting an IS spell pumps the hall +1/+0 until EOT."""
    game, hall = _setup()
    p0 = game.players[0]
    p0.mana_pool.add(ManaType.COLORLESS, 5)

    # Animate
    ability = hall.get_activated_abilities()[0]
    ability.cost(game)
    ability.effect(game)
    assert hall.power == 2

    # Cast an instant
    instant = Instant(name="Bolt", mana_cost=ManaCost(generic=3))
    instant.on_resolve = lambda g: None
    set_board_state(game, 0, hand=[instant], battlefield=[hall])
    p0.mana_pool.add(ManaType.COLORLESS, 3)
    hall._animated = True  # ensure animation flag is set

    from engine.casting import cast_spell
    cast_spell(game, p0, instant)
    _resolve_top_of_stack(game)

    # Hall should be 3/4 after casting instant
    assert hall.power == 3

    # Two instants should pump twice
    instant2 = Instant(name="Bolt2", mana_cost=ManaCost(generic=3))
    instant2.on_resolve = lambda g: None
    set_board_state(game, 0, hand=[instant2], battlefield=[hall])
    p0.mana_pool.add(ManaType.COLORLESS, 3)
    cast_spell(game, p0, instant2)
    _resolve_top_of_stack(game)

    assert hall.power == 4
