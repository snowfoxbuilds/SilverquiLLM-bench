"""Audited tests for Triumph of the Hordes (SOA collector number 59).

Verifies the Triumph of the Hordes card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import TriumphOfTheHordes

from engine.card import Sorcery
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestTriumphOfTheHordesBasicProperties:
    """Triumph of the Hordes basic property tests."""

    def test_is_sorcery(self) -> None:
        """Triumph of the Hordes must be a Sorcery subclass."""
        card = TriumphOfTheHordes(name="Triumph of the Hordes", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """TriumphOfTheHordes.name must be 'Triumph of the Hordes'."""
        card = TriumphOfTheHordes(name="Triumph of the Hordes", owner=None)
        assert card.name == "Triumph of the Hordes"

    def test_card_type(self) -> None:
        """Triumph of the Hordes must have CardType.SORCERY."""
        card = TriumphOfTheHordes(name="Triumph of the Hordes", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Triumph of the Hordes must have converted mana cost 4."""
        card = TriumphOfTheHordes(name="Triumph of the Hordes", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Triumph of the Hordes must have colors ['G']."""
        card = TriumphOfTheHordes(name="Triumph of the Hordes", owner=None)
        for c in ["G"]:
            assert c in card_colors(card), f"Expected color {c} in {card_colors(card)}"

@pytest.mark.ability
class TestTriumphOfTheHordesAbilities:
    """Triumph of the Hordes ability tests — expected to fail against stubs."""

    def test_on_resolve_grants_buff(self) -> None:
        """Triumph of the Hordes should grant a buff until end of turn.

        Oracle: Until end of turn, creatures you control get +1/+1 and gain trample and infect. (Creatures with infe
        This test will fail against stubs (expected).
        """
        from test_utils import create_game, set_board_state
        from engine.card import Creature as CreatureBase

        game = create_game()
        player = game.players[0]
        target = CreatureBase(name="TestCreature", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        power_before = target.power
        card = TriumphOfTheHordes(name="Triumph of the Hordes", owner=player)
        card.controller = player
        card.on_resolve(game)
        # A correct implementation should modify creature power
        assert target.power > power_before, (
            f"Expected power increase. Before: {power_before}, After: {target.power}"
        )

    def test_on_resolve_grants_infect(self) -> None:
        """Triumph of the Hordes should grant infect to creatures.

        Oracle: Until end of turn, creatures you control get +1/+1 and gain trample and infect.
        This test will fail against stubs (expected).
        """
        from test_utils import create_game, set_board_state
        from engine.card import Creature as CreatureBase
        from engine.types import Keyword

        game = create_game()
        player = game.players[0]
        target = CreatureBase(name="TestCreature", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = TriumphOfTheHordes(name="Triumph of the Hordes", owner=player)
        card.controller = player
        card.on_resolve(game)
        # Infect is granted by the spell; check via keywords or a custom attribute
        has_infect = (
            hasattr(Keyword, 'INFECT') and Keyword.INFECT in target.keywords
        ) or getattr(target, 'has_infect', False)
        assert has_infect, (
            f"Expected creature to gain infect after Triumph of the Hordes resolves"
        )
