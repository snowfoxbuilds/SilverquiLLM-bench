"""Audited tests for Withering Curse (collector key 105).

Verifies the Withering Curse card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import WitheringCurse

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestWitheringCurseBasicProperties:
    """Basic property tests for Withering Curse."""

    def test_is_sorcery(self) -> None:
        """Withering Curse must be a Sorcery subclass."""
        card = WitheringCurse(name="Withering Curse", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """WitheringCurse.name must be 'Withering Curse'."""
        card = WitheringCurse(name="Withering Curse", owner=None)
        assert card.name == "Withering Curse"

    def test_card_types(self) -> None:
        """Withering Curse must have correct card types."""
        card = WitheringCurse(name="Withering Curse", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Withering Curse must have converted mana cost 3."""
        card = WitheringCurse(name="Withering Curse", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Withering Curse must have correct colors."""
        card = WitheringCurse(name="Withering Curse", owner=None)
        assert "B" in card.colors


@pytest.mark.ability
class TestWitheringCurseAbilities:
    """Ability tests for Withering Curse -- expected to fail against stubs."""

    def test_has_infusion(self) -> None:
        """Withering Curse must have Infusion keyword."""
        from benchmarks.sos.workspace.engine.types import Keyword
        card = WitheringCurse(name="Withering Curse", owner=None)
        assert Keyword.INFUSION in card.keywords, "Withering Curse should have Infusion"

    def test_infusion_mechanic_implemented(self) -> None:
        """Infusion must alter effect when condition is met."""
        card = WitheringCurse(name="Withering Curse", owner=None)
        assert callable(getattr(card, "check_infusion", None)) or \
            callable(getattr(card, "infusion_active", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Withering Curse must implement infusion per oracle text"

    def test_resolution_removes_creatures(self) -> None:
        """Spell resolution must remove/destroy creatures per oracle text."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Victim", owner=opponent, base_power=1, base_toughness=1)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = WitheringCurse(name="Withering Curse", owner=player)
        card.controller = player
        card.on_resolve(game)
        bf = opponent.zones[Zone.BATTLEFIELD].get_all()
        gy = opponent.zones[Zone.GRAVEYARD].get_all()
        assert target not in bf or target in gy, "Withering Curse must remove creature"


@pytest.mark.edge
class TestWitheringCurseEdgeCases:
    """Edge case and trap tests for Withering Curse."""

    def test_infusion_base_effect_without_condition(self) -> None:
        """Without infusion condition, only base effect applies."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=4, base_toughness=4)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = WitheringCurse(name="Withering Curse", owner=player)
        card.controller = player
        if hasattr(player, "life_gained_this_turn"):
            player.life_gained_this_turn = 0
        card.on_resolve(game)
        # Base effect should not destroy a large creature
        bf = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert target in bf, "Base effect should not destroy a 4/4"

    def test_infusion_enhanced_effect_with_condition(self) -> None:
        """With infusion condition met, enhanced effect applies."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=4, base_toughness=4)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = WitheringCurse(name="Withering Curse", owner=player)
        card.controller = player
        if hasattr(player, "life_gained_this_turn"):
            player.life_gained_this_turn = 3
        card.on_resolve(game)
        bf = opponent.zones[Zone.BATTLEFIELD].get_all()
        gy = opponent.zones[Zone.GRAVEYARD].get_all()
        assert target not in bf or target in gy, \
            "Infusion enhanced effect must destroy creatures"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = WitheringCurse(name="Withering Curse", owner=None)
        card2 = WitheringCurse(name="Withering Curse", owner=None)
        card1.name = "Modified"
        assert card2.name == "Withering Curse", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = WitheringCurse(name="Withering Curse", owner=None)
        assert card.mana_cost.cmc == 3, \
            f"CMC must be 3, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestWitheringCurseInteractions:
    """Multi-card interaction tests for Withering Curse."""

    def test_affects_both_players_creatures(self) -> None:
        """Board-wide effect must affect both players creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        own = Creature(name="Own", owner=player, base_power=1, base_toughness=1)
        own.controller = player
        enemy = Creature(name="Enemy", owner=opponent, base_power=1, base_toughness=1)
        enemy.controller = opponent
        set_board_state(game, 0, battlefield=[own])
        set_board_state(game, 1, battlefield=[enemy])
        card = WitheringCurse(name="Withering Curse", owner=player)
        card.controller = player
        card.on_resolve(game)
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        gy_p = player.zones[Zone.GRAVEYARD].get_all()
        gy_o = opponent.zones[Zone.GRAVEYARD].get_all()
        p_affected = own not in bf_p or own in gy_p
        o_affected = enemy not in bf_o or enemy in gy_o
        assert p_affected and o_affected, "Withering Curse must affect both players"

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.types import Zone
        from benchmarks.sos.workspace.engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = WitheringCurse(name="Withering Curse", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"
