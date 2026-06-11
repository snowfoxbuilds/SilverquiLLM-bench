"""Tests for Great Hall of the Biblioplex (sos_257)."""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import _resolve_top_of_stack, create_game


def _put_on_battlefield(game, player_index, card):
    p = game.players[player_index]
    card.owner = p
    card.controller = p
    p.zones[Zone.BATTLEFIELD].add(card)


class TestGreatHallProperties:
    def test_name(self) -> None:
        assert GreatHallOfTheBiblioplex().name == "Great Hall of the Biblioplex"

    def test_is_land(self) -> None:
        assert CardType.LAND in GreatHallOfTheBiblioplex().card_types

    def test_not_initially_a_creature(self) -> None:
        assert CardType.CREATURE not in GreatHallOfTheBiblioplex().card_types


class TestManaAbilityColorless:
    def test_tap_adds_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        _put_on_battlefield(game, 0, hall)

        ma = hall.get_mana_abilities()[0]
        # Activate via ActivatedAbilityInstance
        ability = ActivatedAbilityInstance(
            source=hall,
            controller=p1,
            cost=ma.cost,
            effect=ma.mana_produced,
            is_mana_ability=True,
        )
        activate_ability(game, p1, ability)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped

    def test_tapped_land_cannot_tap_again(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        _put_on_battlefield(game, 0, hall)
        hall.is_tapped = True

        from engine.abilities import AbilityError
        ma = hall.get_mana_abilities()[0]
        ability = ActivatedAbilityInstance(
            source=hall,
            controller=p1,
            cost=ma.cost,
            effect=ma.mana_produced,
            is_mana_ability=True,
        )
        import pytest
        with pytest.raises(AbilityError):
            activate_ability(game, p1, ability)


class TestRestrictedManaAbility:
    def test_life_tap_produces_restricted_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        _put_on_battlefield(game, 0, hall)

        # Script: choose RED for the color
        p1._script.appendleft(ManaType.RED)

        ma = hall.get_mana_abilities()[1]
        ability = ActivatedAbilityInstance(
            source=hall,
            controller=p1,
            cost=ma.cost,
            effect=ma.mana_produced,
            is_mana_ability=True,
        )
        activate_ability(game, p1, ability)

        assert p1.life == 19  # 1 life paid
        assert hall.is_tapped
        # Restricted mana is present
        assert p1.mana_pool._restricted_instant_sorcery[ManaType.RED] == 1

    def test_restricted_mana_usable_for_instant(self) -> None:
        """Restricted mana can pay for an instant spell."""
        from engine.casting import cast_spell as engine_cast_spell

        game = create_game()
        p1 = game.players[0]

        # Add restricted red mana directly
        p1.mana_pool.add_restricted(ManaType.RED, 1)

        spell = Instant(name="TestInstant", mana_cost=ManaCost.parse("{R}"))
        spell.owner = p1
        spell.controller = p1
        p1.zones[Zone.HAND].add(spell)

        from engine.types import Phase
        game.phase = Phase.PRECOMBAT_MAIN
        game.active_player_index = 0

        # Should not raise — restricted mana pays for instants
        engine_cast_spell(game, p1, spell)
        _resolve_top_of_stack(game)

        # Restricted mana consumed
        assert p1.mana_pool._restricted_instant_sorcery[ManaType.RED] == 0

    def test_restricted_mana_cannot_pay_for_creature(self) -> None:
        """Restricted mana cannot pay for a creature spell."""
        from engine.casting import cast_spell as engine_cast_spell
        from engine.card import Creature

        game = create_game()
        p1 = game.players[0]

        # Only restricted mana available
        p1.mana_pool.add_restricted(ManaType.RED, 2)

        creature_spell = Creature(
            name="TestCreature", base_power=1, base_toughness=1,
            mana_cost=ManaCost.parse("{R}")
        )
        creature_spell.owner = p1
        creature_spell.controller = p1
        p1.zones[Zone.HAND].add(creature_spell)

        from engine.types import Phase
        game.phase = Phase.PRECOMBAT_MAIN
        game.active_player_index = 0

        # Should raise — no unrestricted mana
        import pytest
        from engine.casting import CastingError
        with pytest.raises((CastingError, Exception)):
            engine_cast_spell(game, p1, creature_spell)


class TestAnimation:
    def test_five_mana_animates_to_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        _put_on_battlefield(game, 0, hall)

        p1.mana_pool.add(ManaType.COLORLESS, 5)

        aa = hall.get_activated_abilities()[0]
        ability = ActivatedAbilityInstance(
            source=hall,
            controller=p1,
            cost=aa.cost,
            effect=aa.effect,
            is_mana_ability=False,
        )
        activate_ability(game, p1, ability)
        _resolve_top_of_stack(game)

        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types
        assert "Wizard" in getattr(hall, "subtypes", set())
        assert getattr(hall, "modified_power", None) == 2
        assert getattr(hall, "modified_toughness", None) == 4

    def test_animation_requires_five_mana(self) -> None:
        """Cannot animate with only 4 mana."""
        from engine.abilities import AbilityError

        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        _put_on_battlefield(game, 0, hall)

        p1.mana_pool.add(ManaType.COLORLESS, 4)

        aa = hall.get_activated_abilities()[0]
        ability = ActivatedAbilityInstance(
            source=hall,
            controller=p1,
            cost=aa.cost,
            effect=aa.effect,
            is_mana_ability=False,
        )
        import pytest
        with pytest.raises(AbilityError):
            activate_ability(game, p1, ability)

        assert CardType.CREATURE not in hall.card_types
