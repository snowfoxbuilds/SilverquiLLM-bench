"""Audited tests for Culling Ritual (SOA collector number 62).

Verifies the Culling Ritual card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import CullingRitual

from engine.card import Sorcery
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestCullingRitualBasicProperties:
    """Culling Ritual basic property tests."""

    def test_is_sorcery(self) -> None:
        """Culling Ritual must be a Sorcery subclass."""
        card = CullingRitual(name="Culling Ritual", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """CullingRitual.name must be 'Culling Ritual'."""
        card = CullingRitual(name="Culling Ritual", owner=None)
        assert card.name == "Culling Ritual"

    def test_card_type(self) -> None:
        """Culling Ritual must have CardType.SORCERY."""
        card = CullingRitual(name="Culling Ritual", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Culling Ritual must have converted mana cost 4."""
        card = CullingRitual(name="Culling Ritual", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Culling Ritual must have colors ['B', 'G']."""
        card = CullingRitual(name="Culling Ritual", owner=None)
        for c in ["B", "G"]:
            assert c in card_colors(card), f"Expected color {c} in {card_colors(card)}"

@pytest.mark.ability
class TestCullingRitualAbilities:
    """Culling Ritual ability tests — expected to fail against stubs."""

    def test_on_resolve_destroys_and_adds_mana(self) -> None:
        """Culling Ritual should destroy low-MV nonland permanents and add mana for each.

        Oracle: Destroy each nonland permanent with mana value 2 or less. Add {B} or {G} for each permanent destroyed this way.
        This test will fail against stubs (expected).
        """
        from test_utils import create_game, set_board_state
        from engine.card import Creature as CreatureBase
        from engine.types import ManaCost

        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        # Place low-MV nonland permanents on the battlefield
        cheap1 = CreatureBase(name="CheapGuy1", owner=opponent, base_power=1, base_toughness=1,
                              mana_cost=ManaCost.parse("{1}"))
        cheap2 = CreatureBase(name="CheapGuy2", owner=opponent, base_power=1, base_toughness=1,
                              mana_cost=ManaCost.parse("{W}"))
        set_board_state(game, 1, battlefield=[cheap1, cheap2])

        card = CullingRitual(name="Culling Ritual", owner=player)
        card.controller = player
        pool_before = player.mana_pool.total()
        card.on_resolve(game)
        pool_after = player.mana_pool.total()

        # Both should be destroyed
        bf = game.get_battlefield(opponent).get_all()
        assert cheap1 not in bf, (
            f"Expected CheapGuy1 destroyed. BF: {[c.name for c in bf]}"
        )
        assert cheap2 not in bf, (
            f"Expected CheapGuy2 destroyed. BF: {[c.name for c in bf]}"
        )
        # Should gain mana for each destroyed (2 permanents)
        assert pool_after >= pool_before + 2, (
            f"Expected at least 2 mana added for 2 destroyed permanents. "
            f"Pool before: {pool_before}, after: {pool_after}"
        )

    def test_on_resolve_destroys_low_mv_permanents(self) -> None:
        """Culling Ritual should destroy nonland permanents with low mana value.

        Oracle: Destroy each nonland permanent with mana value 2 or less. Add {B} or {G} for each permanent destroye
        This test will fail against stubs (expected).
        """
        from test_utils import create_game, set_board_state
        from engine.card import Creature as CreatureBase
        from engine.types import ManaCost

        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        cheap = CreatureBase(name="CheapGuy", owner=opponent, base_power=1, base_toughness=1,
                            mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 1, battlefield=[cheap])
        card = CullingRitual(name="Culling Ritual", owner=player)
        card.controller = player
        card.on_resolve(game)
        bf = game.get_battlefield(opponent).get_all()
        assert cheap not in bf, (
            f"Expected cheap creature destroyed. BF: {[c.name for c in bf]}"
        )
