"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, ManaType
from test_utils import TestSetupError as _CastError
from test_utils import cast_spell, create_game, set_board_state


class _Cantrip(Instant):
    """Trivial {R} instant, no targets/effect."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Cantrip")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)


def _resolve_all(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _activate_mana(game, player, land, index, *scripted):
    ab = land.get_mana_abilities()[index]
    for s in reversed(scripted):
        player._script.appendleft(s)
    activate_ability(
        game, player,
        ActivatedAbilityInstance(source=land, controller=player,
                                 cost=ab.cost, effect=ab.mana_produced,
                                 is_mana_ability=True),
    )


def _activate_five(game, player, land):
    ab = land.get_activated_abilities()[0]
    activate_ability(
        game, player,
        ActivatedAbilityInstance(source=land, controller=player,
                                 cost=ab.cost, effect=ab.effect,
                                 is_mana_ability=False),
    )
    _resolve_all(game)


class TestProperties:
    def test_static(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.name == "Great Hall of the Biblioplex"
        assert isinstance(card, Land)
        assert CardType.LAND in card.card_types
        assert card.can_cast(create_game()) is False
        assert len(card.get_mana_abilities()) == 2
        assert len(card.get_activated_abilities()) == 1


class TestManaAbilities:
    def test_colorless(self) -> None:
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land])
        _activate_mana(game, p0, land, 0)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 1
        assert land.is_tapped is True

    def test_restricted_any_color_pays_one_life(self) -> None:
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land], life=20)
        _activate_mana(game, p0, land, 1, ManaType.RED)
        assert land.is_tapped is True
        assert p0.life == 19
        assert p0.mana_pool.get(ManaType.RED) == 1

    def test_restricted_mana_pays_instant_only(self) -> None:
        # Restricted red can pay an instant...
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land])
        p0.mana_pool.add_restricted(ManaType.RED, 1)
        set_board_state(game, 0, hand=[_Cantrip(owner=None)])
        cast_spell(game, 0, "Cantrip")
        assert any(getattr(c, "name", None) == "Cantrip"
                   for c in game.get_graveyard(p0).get_all())

    def test_restricted_mana_cannot_pay_creature(self) -> None:
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land])
        p0.mana_pool.add_restricted(ManaType.RED, 1)
        goblin = Creature(name="Goblin", base_power=1, base_toughness=1,
                          mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[goblin])
        with pytest.raises(_CastError):
            cast_spell(game, 0, "Goblin")


class TestAnimation:
    def _animated(self):
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 5})
        _activate_five(game, p0, land)
        return game, p0, land

    def test_becomes_2_4_wizard_still_land(self) -> None:
        game, p0, land = self._animated()
        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types  # still a land
        assert "Wizard" in land.subtypes
        assert land.power == 2 and land.toughness == 4

    def test_animation_costs_five(self) -> None:
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land],
                        mana={ManaType.COLORLESS: 4})
        from engine.abilities import AbilityError

        ab = land.get_activated_abilities()[0]
        with pytest.raises(AbilityError):
            activate_ability(
                game, p0,
                ActivatedAbilityInstance(source=land, controller=p0,
                                         cost=ab.cost, effect=ab.effect),
            )
        assert CardType.CREATURE not in land.card_types

    def test_pump_on_spell_and_eot_reset(self) -> None:
        game, p0, land = self._animated()
        # Cast an instant → +1/+0 (power 2 → 3).
        set_board_state(game, 0, hand=[_Cantrip(owner=None)],
                        mana={ManaType.RED: 1})
        cast_spell(game, 0, "Cantrip")
        assert land.power == 3 and land.toughness == 4
        # A second instant stacks → power 4.
        set_board_state(game, 0, hand=[_Cantrip(name="Cantrip2", owner=None)],
                        mana={ManaType.RED: 1})
        cast_spell(game, 0, "Cantrip2")
        assert land.power == 4
        # End-of-turn cleanup removes the until-EOT pumps → back to 2/4.
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)
        assert land.power == 2 and land.toughness == 4
