"""Audited tests for Ark of Hunger (collector key 173).

Verifies the Ark of Hunger card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import ArkOfHunger

from engine.card import Artifact
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestArkOfHungerBasicProperties:
    """Basic property tests for Ark of Hunger."""

    def test_is_artifact(self) -> None:
        """Ark of Hunger must be a Artifact subclass."""
        card = ArkOfHunger(name="Ark of Hunger", owner=None)
        assert isinstance(card, Artifact)

    def test_name(self) -> None:
        """ArkOfHunger.name must be 'Ark of Hunger'."""
        card = ArkOfHunger(name="Ark of Hunger", owner=None)
        assert card.name == "Ark of Hunger"

    def test_card_types(self) -> None:
        """Ark of Hunger must have correct card types."""
        card = ArkOfHunger(name="Ark of Hunger", owner=None)
        assert CardType.ARTIFACT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Ark of Hunger must have converted mana cost 4."""
        card = ArkOfHunger(name="Ark of Hunger", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Ark of Hunger must have correct colors."""
        card = ArkOfHunger(name="Ark of Hunger", owner=None)
        assert "R" in card_colors(card)
        assert "W" in card_colors(card)

@pytest.mark.ability
class TestArkOfHungerAbilities:
    """Ability tests for Ark of Hunger — expected to fail against stubs."""

    def test_deals_damage(self) -> None:
        """Resolution should deal 1 damage."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        life_before = opponent.life
        card = ArkOfHunger(name="Ark of Hunger", owner=player)
        card.controller = player
        card._targets = [opponent]
        if hasattr(card, "set_targets"):
            card.set_targets([opponent])
        card.on_resolve(game)
        life_after = opponent.life
        assert life_after < life_before, (
            f"Should deal damage: life {life_before} -> {life_after}"
        )

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = ArkOfHunger(name="Ark of Hunger", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )

    def test_mill_effect(self) -> None:
        """Resolution should mill 2 cards."""
        from test_utils import create_game
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        for i in range(4):
            opponent.zones[Zone.LIBRARY].add(Sorcery(name=f"Mill{i}", owner=opponent))
        gy_before = len(opponent.zones[Zone.GRAVEYARD].get_all())
        card = ArkOfHunger(name="Ark of Hunger", owner=player)
        card.controller = player
        card.on_resolve(game)
        gy_after = len(opponent.zones[Zone.GRAVEYARD].get_all())
        assert gy_after > gy_before, (
            f"Should mill: gy {gy_before} -> {gy_after}"
        )

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = ArkOfHunger(name="Ark of Hunger", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"

@pytest.mark.edge
class TestArkOfHungerEdgeCases:
    """Edge case tests for Ark of Hunger."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = ArkOfHunger(name="Ark of Hunger", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True

@pytest.mark.interaction
class TestArkOfHungerInteractions:
    """Interaction tests for Ark of Hunger."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = ArkOfHunger(name="Ark of Hunger", owner=player)
        card.controller = player
        card._targets = [t1]
        if hasattr(card, "set_targets"):
            card.set_targets([t1])
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Non-targeted creature should remain
        bf = game.get_battlefield(opponent).get_all()
        assert t2 in bf, "Non-targeted creature should remain"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = ArkOfHunger(name="Ark of Hunger", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
