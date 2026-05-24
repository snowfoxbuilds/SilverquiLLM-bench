"""Audited tests for Potioner's Trove (collector key 251).

Verifies the Potioner's Trove card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import PotionersTrove

from benchmarks.sos.workspace.engine.card import Artifact
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestPotionersTroveBasicProperties:
    """Basic property tests for Potioner's Trove."""

    def test_is_artifact(self) -> None:
        """Potioner's Trove must be a Artifact subclass."""
        card = PotionersTrove(name="Potioner's Trove", owner=None)
        assert isinstance(card, Artifact)

    def test_name(self) -> None:
        """PotionersTrove.name must be 'Potioner's Trove'."""
        card = PotionersTrove(name="Potioner's Trove", owner=None)
        assert card.name == "Potioner's Trove"

    def test_card_types(self) -> None:
        """Potioner's Trove must have correct card types."""
        card = PotionersTrove(name="Potioner's Trove", owner=None)
        assert CardType.ARTIFACT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Potioner's Trove must have converted mana cost 3."""
        card = PotionersTrove(name="Potioner's Trove", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Potioner's Trove must have correct colors."""
        card = PotionersTrove(name="Potioner's Trove", owner=None)
        assert len(card.colors) == 0


@pytest.mark.ability
class TestPotionersTroveAbilities:
    """Ability tests for Potioner's Trove — expected to fail against stubs."""

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = PotionersTrove(name="Potioner's Trove", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = PotionersTrove(name="Potioner's Trove", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"


@pytest.mark.edge
class TestPotionersTroveEdgeCases:
    """Edge case tests for Potioner's Trove."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = PotionersTrove(name="Potioner's Trove", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestPotionersTroveInteractions:
    """Interaction tests for Potioner's Trove."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = PotionersTrove(name="Potioner's Trove", owner=player)
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
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = PotionersTrove(name="Potioner's Trove", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
