"""Audited tests for FDN 267 — Secluded Courtyard."""

from __future__ import annotations

from card_impl import SecludedCourtyard
from engine.card import Land, ManaAbility
from engine.types import ManaCost, ManaType
from tests.test_utils import create_game


class TestSecludedCourtyardBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = SecludedCourtyard(owner=None)
        assert card.name == "Secluded Courtyard"

    def test_is_land(self) -> None:
        card = SecludedCourtyard(owner=None)
        assert isinstance(card, Land)

    def test_has_chosen_creature_type_attribute(self) -> None:
        card = SecludedCourtyard(owner=None)
        assert hasattr(card, "chosen_creature_type")
        assert card.chosen_creature_type is None


class TestSecludedCourtyardManaAbilities:
    """{T}: Add {C} and {T}: Add one mana of any color (restricted)."""

    def test_has_two_mana_abilities(self) -> None:
        card = SecludedCourtyard(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) == 2

    def test_colorless_mana_ability(self) -> None:
        game = create_game()
        p1 = game.players[0]
        courtyard = SecludedCourtyard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(courtyard)

        abilities = courtyard.get_mana_abilities()
        mana_before = p1.mana_pool.total()
        assert abilities[0].cost(game, courtyard)
        abilities[0].mana_produced(game)
        assert p1.mana_pool.total() == mana_before + 1

    def test_cannot_tap_twice(self) -> None:
        game = create_game()
        p1 = game.players[0]
        courtyard = SecludedCourtyard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(courtyard)

        abilities = courtyard.get_mana_abilities()
        abilities[0].cost(game, courtyard)
        # Already tapped, second ability should fail
        assert not abilities[1].cost(game, courtyard)

    def test_on_resolve_sets_chosen_type(self) -> None:
        game = create_game()
        p1 = game.players[0]
        from engine.player import DeterministicPlayer
        # Script the choice
        p1._script.appendleft("Elf")
        courtyard = SecludedCourtyard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(courtyard)
        courtyard.on_resolve(game)
        assert courtyard.chosen_creature_type == "Elf"

