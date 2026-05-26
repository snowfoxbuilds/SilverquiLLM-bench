"""Audited tests for Snarl Song (collector key 161).

Verifies the Snarl Song card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import SnarlSong

from engine.card import Sorcery
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestSnarlSongBasicProperties:
    """Basic property tests for Snarl Song."""

    def test_is_sorcery(self) -> None:
        """Snarl Song must be a Sorcery subclass."""
        card = SnarlSong(name="Snarl Song", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """SnarlSong.name must be 'Snarl Song'."""
        card = SnarlSong(name="Snarl Song", owner=None)
        assert card.name == "Snarl Song"

    def test_card_types(self) -> None:
        """Snarl Song must have correct card types."""
        card = SnarlSong(name="Snarl Song", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Snarl Song must have converted mana cost 6."""
        card = SnarlSong(name="Snarl Song", owner=None)
        assert card.mana_cost.cmc == 6

    def test_colors(self) -> None:
        """Snarl Song must have correct colors."""
        card = SnarlSong(name="Snarl Song", owner=None)
        assert "G" in card_colors(card)

@pytest.mark.ability
class TestSnarlSongAbilities:
    """Ability tests for Snarl Song -- expected to fail against stubs."""

    def test_has_converge(self) -> None:
        """Snarl Song must have Converge keyword."""
        from engine.types import Keyword
        card = SnarlSong(name="Snarl Song", owner=None)
        assert Keyword.CONVERGE in card.keywords, "Snarl Song should have Converge"

    def test_converge_adds_counters(self) -> None:
        """Converge must add +1/+1 counters per color of mana spent."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = SnarlSong(name="Snarl Song", owner=player)
        card.controller = player
        if hasattr(card, "colors_spent"):
            card.colors_spent = 3
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        counters = getattr(card, "counters", {})
        p1p1 = counters.get("+1/+1", counters.get("p1p1", 0))
        assert p1p1 == 3, f"Converge with 3 colors should add 3 counters, got {p1p1}"

@pytest.mark.edge
class TestSnarlSongEdgeCases:
    """Edge case and trap tests for Snarl Song."""

    def test_converge_zero_colors_no_bonus(self) -> None:
        """With 0 colors, converge should produce no bonus."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = SnarlSong(name="Snarl Song", owner=player)
        card.controller = player
        if hasattr(card, "colors_spent"):
            card.colors_spent = 0
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        counters = getattr(card, "counters", {})
        p1p1 = counters.get("+1/+1", counters.get("p1p1", 0))
        assert p1p1 == 0, f"Converge with 0 colors should add 0 counters, got {p1p1}"

    def test_converge_five_colors_maximum(self) -> None:
        """With 5 colors, converge should produce maximum bonus."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = SnarlSong(name="Snarl Song", owner=player)
        card.controller = player
        if hasattr(card, "colors_spent"):
            card.colors_spent = 5
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        elif callable(getattr(card, "on_resolve", None)):
            card.on_resolve(game)
        counters = getattr(card, "counters", {})
        p1p1 = counters.get("+1/+1", counters.get("p1p1", 0))
        assert p1p1 == 5, f"Converge with 5 colors should add 5 counters, got {p1p1}"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = SnarlSong(name="Snarl Song", owner=None)
        card2 = SnarlSong(name="Snarl Song", owner=None)
        card1.name = "Modified"
        assert card2.name == "Snarl Song", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = SnarlSong(name="Snarl Song", owner=None)
        assert card.mana_cost.cmc == 6, \
            f"CMC must be 6, got {card.mana_cost.cmc}"

@pytest.mark.interaction
class TestSnarlSongInteractions:
    """Multi-card interaction tests for Snarl Song."""

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = SnarlSong(name="Snarl Song", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"

    def test_tokens_appear_on_battlefield(self) -> None:
        """Tokens created must appear on the battlefield."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = SnarlSong(name="Snarl Song", owner=player)
        card.controller = player
        bf_before = len(player.zones[Zone.BATTLEFIELD].get_all())
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        elif callable(getattr(card, "on_resolve", None)):
            card.on_resolve(game)
        bf_after = len(player.zones[Zone.BATTLEFIELD].get_all())
        assert bf_after > bf_before, "Tokens must appear on battlefield"
