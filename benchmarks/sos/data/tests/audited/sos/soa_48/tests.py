"""Audited tests for Subterranean Tremors (SOA collector number 48).

Verifies the Subterranean Tremors card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import SubterraneanTremors

from engine.card import Sorcery
from engine.types import CardType


@pytest.mark.basic
class TestSubterraneanTremorsBasicProperties:
    """Subterranean Tremors basic property tests."""

    def test_is_sorcery(self) -> None:
        """Subterranean Tremors must be a Sorcery subclass."""
        card = SubterraneanTremors(name="Subterranean Tremors", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """SubterraneanTremors.name must be 'Subterranean Tremors'."""
        card = SubterraneanTremors(name="Subterranean Tremors", owner=None)
        assert card.name == "Subterranean Tremors"

    def test_card_type(self) -> None:
        """Subterranean Tremors must have CardType.SORCERY."""
        card = SubterraneanTremors(name="Subterranean Tremors", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_has_x(self) -> None:
        """Subterranean Tremors must have X in its mana cost."""
        card = SubterraneanTremors(name="Subterranean Tremors", owner=None)
        assert card.mana_cost.x_count >= 1

    def test_colors(self) -> None:
        """Subterranean Tremors must have colors ['R']."""
        card = SubterraneanTremors(name="Subterranean Tremors", owner=None)
        for c in ["R"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestSubterraneanTremorsAbilities:
    """Subterranean Tremors ability tests — expected to fail against stubs."""

    def test_on_resolve_creates_token_when_x_ge_8(self) -> None:
        """Subterranean Tremors should create an 8/8 Lizard token when X >= 8.

        Oracle: Subterranean Tremors deals X damage to each creature without flying. If X is 4 or more, destroy all artifacts. If X is 8 or more, create an 8/8 red Lizard creature token.
        This test will fail against stubs (expected).
        """
        from test_utils import create_game
        from engine.types import Zone

        game = create_game()
        player = game.players[0]
        card = SubterraneanTremors(name="Subterranean Tremors", owner=player)
        card.controller = player
        card.x_value = 8  # Set X=8 for token creation
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Expected 8/8 Lizard token on battlefield when X=8. "
            f"Before: {bf_before}, After: {bf_after}"
        )

    def test_on_resolve_destroys_artifacts_when_x_ge_4(self) -> None:
        """Subterranean Tremors should destroy all artifacts when X >= 4.

        Oracle: If X is 4 or more, destroy all artifacts.
        This test will fail against stubs (expected).
        """
        from test_utils import create_game, set_board_state
        from engine.card import Artifact

        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        artifact = Artifact(name="TargetArtifact", owner=opponent)
        set_board_state(game, 1, battlefield=[artifact])
        card = SubterraneanTremors(name="Subterranean Tremors", owner=player)
        card.controller = player
        card.x_value = 4  # Set X=4 for artifact destruction
        card.on_resolve(game)
        bf = game.get_battlefield(opponent).get_all()
        assert artifact not in bf, (
            f"Expected artifact destroyed when X=4. BF: {[c.name for c in bf]}"
        )

    def test_on_resolve_deals_damage(self) -> None:
        """Subterranean Tremors should deal damage on resolution.

        Oracle: Subterranean Tremors deals X damage to each creature without flying. If X is 4 or more, destroy all 
        This test will fail against stubs (expected).
        """
        from test_utils import create_game, set_board_state
        from engine.card import Creature as CreatureBase

        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = CreatureBase(name="Target", owner=opponent, base_power=1, base_toughness=5)
        set_board_state(game, 1, battlefield=[target])
        card = SubterraneanTremors(name="Subterranean Tremors", owner=player)
        card.controller = player
        card.x_value = 3  # Set X=3 for testing
        card.on_resolve(game)
        assert target.damage_marked > 0, (
            f"Expected damage on target creature. Damage: {target.damage_marked}"
        )
