"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, set_board_state, cast_spell
from test_utils import TestSetupError as _CastError


def _resolve_stack(game) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _activate_mana(game, player, land, index: int) -> None:
    ma = land.get_mana_abilities()[index]
    inst = ActivatedAbilityInstance(
        source=land, controller=player, cost=ma.cost,
        effect=ma.mana_produced, is_mana_ability=True,
    )
    activate_ability(game, player, inst)


def _activate_five(game, player, land) -> None:
    aa = land.get_activated_abilities()[0]
    inst = ActivatedAbilityInstance(
        source=land, controller=player, cost=aa.cost,
        effect=aa.effect, is_mana_ability=False,
    )
    activate_ability(game, player, inst)
    _resolve_stack(game)


class TestProperties:
    def test_is_land_no_pt_initially(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)
        assert card.name == "Great Hall of the Biblioplex"
        assert CardType.LAND in card.card_types
        assert CardType.CREATURE not in card.card_types
        # No P/T until animated — guards on hasattr must see nothing.
        assert not hasattr(card, "toughness")
        assert not hasattr(card, "base_power")


class TestManaAbilities:
    def test_colorless_mana_ability(self) -> None:
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land], mana={})
        _activate_mana(game, p0, land, 0)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 1
        assert land.is_tapped

    def test_any_color_costs_life_and_is_restricted(self) -> None:
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land], mana={}, life=20)
        p0._script.append(ManaType.BLUE)  # color choice
        _activate_mana(game, p0, land, 1)
        assert land.is_tapped
        assert p0.life == 19  # paid 1 life
        assert p0.mana_pool.get(ManaType.BLUE) == 1
        assert p0.mana_pool._restricted[ManaType.BLUE] == 1

    def test_restricted_mana_pays_instant(self) -> None:
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        instant = Instant(name="Bolt", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, battlefield=[land], hand=[instant], mana={})
        p0._script.append(ManaType.BLUE)
        _activate_mana(game, p0, land, 1)
        cast_spell(game, 0, "Bolt")
        assert game.get_graveyard(p0).contains(instant)

    def test_restricted_mana_cannot_pay_creature(self) -> None:
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        critter = Creature(name="Critter", mana_cost=ManaCost.parse("{U}"),
                           base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[land], hand=[critter], mana={})
        p0._script.append(ManaType.BLUE)
        _activate_mana(game, p0, land, 1)
        try:
            cast_spell(game, 0, "Critter")
            assert False, "restricted mana should not pay for a creature"
        except _CastError:
            pass
        assert game.get_hand(p0).contains(critter)


class TestAnimation:
    def test_becomes_creature_still_land(self) -> None:
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 5})
        _activate_five(game, p0, land)
        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types  # still a land
        assert "Wizard" in land.subtypes
        assert land.power == 2 and land.toughness == 4

    def test_pump_on_instant_sorcery_cast(self) -> None:
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 5})
        _activate_five(game, p0, land)
        assert land.power == 2

        i1 = Instant(name="I1", mana_cost=ManaCost())
        i2 = Instant(name="I2", mana_cost=ManaCost())
        set_board_state(game, 0, hand=[i1, i2])
        cast_spell(game, 0, "I1")
        assert land.power == 3  # +1/+0
        cast_spell(game, 0, "I2")
        assert land.power == 4  # stacks

    def test_gate_no_double_animation(self) -> None:
        """Activating {5} twice does not register the pump trigger twice."""
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 10})
        _activate_five(game, p0, land)
        _activate_five(game, p0, land)  # already a creature → no-op
        instant = Instant(name="I", mana_cost=ManaCost())
        set_board_state(game, 0, hand=[instant])
        cast_spell(game, 0, "I")
        assert land.power == 3  # only +1, not +2

    def test_pump_resets_at_upkeep(self) -> None:
        from engine.events import BeginningOfUpkeepTriggeredEvent

        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 5})
        _activate_five(game, p0, land)
        instant = Instant(name="I", mana_cost=ManaCost())
        set_board_state(game, 0, hand=[instant])
        cast_spell(game, 0, "I")
        assert land.power == 3
        # New turn's upkeep resets the until-end-of-turn pump.
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)
        assert land.power == 2
