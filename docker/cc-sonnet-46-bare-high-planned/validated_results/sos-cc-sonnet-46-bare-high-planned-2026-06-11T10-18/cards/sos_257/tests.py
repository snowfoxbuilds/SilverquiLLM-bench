"""Tests for Great Hall of the Biblioplex (sos_257)."""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state, _resolve_top_of_stack


class SimpleInstant(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "SimpleInstant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{0}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        pass


def _setup_land_on_battlefield():
    land = GreatHallOfTheBiblioplex()
    game = create_game()
    p1 = game.players[0]
    set_board_state(game, 0, battlefield=[land])
    land.controller = p1
    land.owner = p1
    land.register_triggers(game)
    return game, land, p1


def test_colorless_mana_ability():
    """{T}: Add {C}."""
    game, land, p1 = _setup_land_on_battlefield()
    mana_abs = land.get_mana_abilities()
    assert len(mana_abs) >= 1

    mana_abs[0].cost(game)
    mana_abs[0].mana_produced(game)

    assert p1.mana_pool.get(ManaType.COLORLESS) == 1


def test_restricted_mana_from_life_payment():
    """{T}, Pay 1 life: Add one mana of any color (restricted)."""
    game, land, p1 = _setup_land_on_battlefield()

    p1.life = 20
    from engine.player import DeterministicPlayer
    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(ManaType.RED)

    mana_abs = land.get_mana_abilities()
    mana_abs[1].cost(game)
    mana_abs[1].mana_produced(game)

    assert p1.life == 19
    assert p1.mana_pool.restricted_total() == 1


def test_restricted_mana_unusable_for_creature():
    """Restricted mana cannot pay for a non-instant/sorcery spell."""
    from engine.card import Creature
    from engine.types import Keyword
    game = create_game()
    p1 = game.players[0]
    # Add only restricted mana
    p1.mana_pool.add_restricted(ManaType.RED, 3)

    # Restricted mana should NOT be available for can_pay without for_instant_sorcery=True
    from engine.types import ManaCost
    cost = ManaCost.parse("{3}")
    assert not p1.mana_pool.can_pay(cost, for_instant_sorcery=False)
    assert p1.mana_pool.can_pay(cost, for_instant_sorcery=True)


def test_animation_makes_creature():
    """{5} animates the land into a 2/4 Wizard."""
    game, land, p1 = _setup_land_on_battlefield()

    # Pay {5} to animate
    p1.mana_pool.add(ManaType.COLORLESS, 5)
    activated = land.get_activated_abilities()
    assert len(activated) >= 1

    activated[0].cost(game)
    activated[0].effect(game)

    assert CardType.CREATURE in land.card_types
    assert CardType.LAND in land.card_types
    assert "Wizard" in land.subtypes
    assert land.base_power == 2
    assert land.base_toughness == 4


def test_pump_trigger_fires_on_instant_cast():
    """After animation, casting an instant pumps the land +1/+0 until EOT."""
    game, land, p1 = _setup_land_on_battlefield()

    p1.mana_pool.add(ManaType.COLORLESS, 5)
    activated = land.get_activated_abilities()
    activated[0].cost(game)
    activated[0].effect(game)

    assert land.modified_power == 2

    spell = SimpleInstant()
    set_board_state(game, 0, battlefield=[land], hand=[spell])
    land.controller = p1

    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0

    from engine.casting import cast_spell as _cast
    _cast(game, p1, spell)

    _resolve_top_of_stack(game)

    assert land.modified_power == 3  # +1/+0 applied
