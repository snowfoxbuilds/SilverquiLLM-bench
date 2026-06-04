"""Tests for SOS 257 — Great Hall of the Biblioplex (Land animation)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land
from engine.types import CardType, ManaCost, ManaType
from test_utils import (
    cast_spell,
    create_game,
    set_board_state,
    _resolve_top_of_stack,
)


class _Zap(Instant):
    """No-op instant ({R}) used to fire the cast trigger."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)
        self.resolved = False

    def on_resolve(self, game: Any) -> None:
        self.resolved = True


def _activate_mana(game: Any, player: Any, land: Any, index: int) -> None:
    ma = land.get_mana_abilities()[index]
    inst = ActivatedAbilityInstance(
        source=land,
        controller=player,
        cost=ma.cost,
        effect=ma.mana_produced,
        is_mana_ability=True,
    )
    activate_ability(game, player, inst)


class TestProperties:
    def test_is_land(self) -> None:
        c = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(c, Land)

    def test_name_and_no_mana_cost(self) -> None:
        c = GreatHallOfTheBiblioplex(owner=None)
        assert c.name == "Great Hall of the Biblioplex"
        assert c.mana_cost.cmc == 0

    def test_is_land_type_and_uncastable(self) -> None:
        game = create_game()
        c = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in c.card_types
        assert c.can_cast(game) is False
        assert CardType.CREATURE not in c.card_types


class TestManaAbilities:
    def test_tap_for_colorless(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={})

        _activate_mana(game, p1, hall, 0)  # {T}: Add {C}

        assert hall.is_tapped is True
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_tap_pay_life_for_any_color(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={}, life=20)
        p1._script.append(ManaType.BLUE)  # choose the color to add

        _activate_mana(game, p1, hall, 1)  # {T}, Pay 1 life: Add any color

        assert hall.is_tapped is True
        assert p1.life == 19
        assert p1.mana_pool.get(ManaType.BLUE) == 1

    def test_already_tapped_cannot_pay(self) -> None:
        from engine.abilities import AbilityError

        game = create_game()
        p1, _p2 = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={})
        hall.is_tapped = True

        import pytest

        with pytest.raises(AbilityError):
            _activate_mana(game, p1, hall, 0)


def _activate_five(game: Any, player: Any, hall: Any) -> None:
    ab = hall.get_activated_abilities(game)[0]
    inst = ActivatedAbilityInstance(
        source=hall, controller=player, cost=ab.cost, effect=ab.effect,
    )
    activate_ability(game, player, inst)
    _resolve_top_of_stack(game)


class TestAnimation:
    def test_becomes_2_4_wizard_still_land(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall],
                        mana={ManaType.COLORLESS: 5})

        _activate_five(game, p1, hall)

        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types  # still a land
        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4
        assert p1.mana_pool.total() == 0  # {5} spent

    def test_insufficient_mana_does_not_animate(self) -> None:
        from engine.abilities import AbilityError

        import pytest

        game = create_game()
        p1, _p2 = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall],
                        mana={ManaType.COLORLESS: 4})

        with pytest.raises(AbilityError):
            _activate_five(game, p1, hall)

        assert CardType.CREATURE not in hall.card_types

    def test_animates_only_once(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall],
                        mana={ManaType.COLORLESS: 10})

        _activate_five(game, p1, hall)

        # Already a creature — the {5} ability is no longer offered.
        assert hall.get_activated_abilities(game) == []


class TestCastPump:
    def test_instant_cast_pumps_plus_one_zero(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        zap = _Zap(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], hand=[zap],
                        mana={ManaType.COLORLESS: 5})
        _activate_five(game, p1, hall)  # animate -> 2/4
        p1.mana_pool.add(ManaType.RED, 1)

        cast_spell(game, 0, "Zap")

        assert zap.resolved is True
        assert hall.power == 3  # 2 + 1
        assert hall.toughness == 4  # unchanged

    def test_two_instants_stack_two_pumps(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        zap1 = _Zap(owner=p1, controller=p1)
        zap2 = _Zap(name="Zap2", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], hand=[zap1, zap2],
                        mana={ManaType.COLORLESS: 5})
        _activate_five(game, p1, hall)
        p1.mana_pool.add(ManaType.RED, 2)

        cast_spell(game, 0, "Zap")
        cast_spell(game, 0, "Zap2")

        assert hall.power == 4  # 2 + 1 + 1
        assert hall.toughness == 4

    def test_creature_spell_does_not_pump(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        bear = Creature(name="Bear", owner=p1, controller=p1,
                        base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{1}{G}"))
        set_board_state(game, 0, battlefield=[hall], hand=[bear],
                        mana={ManaType.COLORLESS: 5})
        _activate_five(game, p1, hall)
        p1.mana_pool.add(ManaType.GREEN, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 1)

        cast_spell(game, 0, "Bear")

        assert hall.power == 2  # no pump from a creature spell
        assert hall.toughness == 4
