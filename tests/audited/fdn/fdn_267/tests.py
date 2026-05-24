"""Audited tests for FDN 267 — Secluded Courtyard."""

from __future__ import annotations

from card_impl import SecludedCourtyard
from benchmarks.sos.workspace.engine.card import Land, ManaAbility
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestSecludedCourtyardBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = SecludedCourtyard(owner=None)
        assert card.name == "Secluded Courtyard"

    def test_is_land(self) -> None:
        card = SecludedCourtyard(owner=None)
        assert isinstance(card, Land)

    def test_chosen_creature_type_starts_none(self) -> None:
        card = SecludedCourtyard(owner=None)
        assert card.chosen_creature_type is None


class TestSecludedCourtyardCreatureTypeChoice:
    """As this land enters, choose a creature type."""

    def test_on_resolve_sets_chosen_type(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p1._script.appendleft("Elf")
        courtyard = SecludedCourtyard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(courtyard)
        courtyard.on_resolve(game)
        assert courtyard.chosen_creature_type == "Elf"

    def test_on_resolve_with_different_creature_type(self) -> None:
        """Verify the choice mechanism works for different creature types."""
        game = create_game()
        p1 = game.players[0]
        p1._script.appendleft("Dragon")
        courtyard = SecludedCourtyard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(courtyard)
        courtyard.on_resolve(game)
        assert courtyard.chosen_creature_type == "Dragon"


class TestSecludedCourtyardManaAbilities:
    """{T}: Add {C} and {T}: Add one mana of any color (restricted)."""

    def test_has_two_mana_abilities(self) -> None:
        card = SecludedCourtyard(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) == 2

    def test_colorless_ability_produces_colorless_mana(self) -> None:
        """First ability should produce specifically COLORLESS mana."""
        game = create_game()
        p1 = game.players[0]
        courtyard = SecludedCourtyard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(courtyard)

        abilities = courtyard.get_mana_abilities()
        colorless_before = p1.mana_pool.get(ManaType.COLORLESS)
        assert abilities[0].cost(game, courtyard)
        abilities[0].mana_produced(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == colorless_before + 1

    def test_cannot_tap_twice(self) -> None:
        """Once tapped for one ability, the other should fail."""
        game = create_game()
        p1 = game.players[0]
        courtyard = SecludedCourtyard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(courtyard)

        abilities = courtyard.get_mana_abilities()
        abilities[0].cost(game, courtyard)
        assert not abilities[1].cost(game, courtyard)

    def test_colored_mana_ability_produces_chosen_color(self) -> None:
        """Second ability should produce one mana of any color (player chooses)."""
        game = create_game()
        p1 = game.players[0]
        # Script color choice for the mana ability
        p1._script.appendleft(ManaType.GREEN)
        courtyard = SecludedCourtyard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(courtyard)

        abilities = courtyard.get_mana_abilities()
        green_before = p1.mana_pool.get(ManaType.GREEN)
        assert abilities[1].cost(game, courtyard)
        abilities[1].mana_produced(game)
        assert p1.mana_pool.get(ManaType.GREEN) == green_before + 1

    def test_colored_mana_ability_can_produce_blue(self) -> None:
        """Second ability should work for any color, not just one."""
        game = create_game()
        p1 = game.players[0]
        p1._script.appendleft(ManaType.BLUE)
        courtyard = SecludedCourtyard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(courtyard)

        abilities = courtyard.get_mana_abilities()
        blue_before = p1.mana_pool.get(ManaType.BLUE)
        assert abilities[1].cost(game, courtyard)
        abilities[1].mana_produced(game)
        assert p1.mana_pool.get(ManaType.BLUE) == blue_before + 1

    def test_colorless_ability_description(self) -> None:
        """First ability description should mention colorless / {C}."""
        card = SecludedCourtyard(owner=None)
        abilities = card.get_mana_abilities()
        assert "{C}" in abilities[0].description or "colorless" in abilities[0].description.lower()

    def test_colored_ability_description(self) -> None:
        """Second ability description should mention any color."""
        card = SecludedCourtyard(owner=None)
        abilities = card.get_mana_abilities()
        assert "any color" in abilities[1].description.lower()

