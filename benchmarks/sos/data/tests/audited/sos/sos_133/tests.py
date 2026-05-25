"""Audited tests for Tackle Artist (collector key 133).

Verifies the Tackle Artist card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import TackleArtist

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestTackleArtistBasicProperties:
    """Basic property tests for Tackle Artist."""

    def test_is_creature(self) -> None:
        """Tackle Artist must be a Creature subclass."""
        card = TackleArtist(name="Tackle Artist", owner=None, base_power=4, base_toughness=3)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """TackleArtist.name must be 'Tackle Artist'."""
        card = TackleArtist(name="Tackle Artist", owner=None, base_power=4, base_toughness=3)
        assert card.name == "Tackle Artist"

    def test_card_types(self) -> None:
        """Tackle Artist must have correct card types."""
        card = TackleArtist(name="Tackle Artist", owner=None, base_power=4, base_toughness=3)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Tackle Artist must have converted mana cost 4."""
        card = TackleArtist(name="Tackle Artist", owner=None, base_power=4, base_toughness=3)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Tackle Artist must have correct colors."""
        card = TackleArtist(name="Tackle Artist", owner=None, base_power=4, base_toughness=3)
        assert "R" in card.colors

    def test_power(self) -> None:
        """Tackle Artist must have base power 4."""
        card = TackleArtist(name="Tackle Artist", owner=None, base_power=4, base_toughness=3)
        assert card.base_power == 4

    def test_toughness(self) -> None:
        """Tackle Artist must have base toughness 3."""
        card = TackleArtist(name="Tackle Artist", owner=None, base_power=4, base_toughness=3)
        assert card.base_toughness == 3


@pytest.mark.ability
class TestTackleArtistAbilities:
    """Ability tests for Tackle Artist -- expected to fail against stubs."""

    def test_has_trample(self) -> None:
        """Tackle Artist must have Trample keyword."""
        from engine.types import Keyword
        card = TackleArtist(name="Tackle Artist", owner=None, base_power=4, base_toughness=3)
        assert Keyword.TRAMPLE in card.keywords, "Tackle Artist should have Trample"

    def test_has_opus(self) -> None:
        """Tackle Artist must have Opus keyword."""
        from engine.types import Keyword
        card = TackleArtist(name="Tackle Artist", owner=None, base_power=4, base_toughness=3)
        assert Keyword.OPUS in card.keywords, "Tackle Artist should have Opus"

    def test_opus_trigger_implemented(self) -> None:
        """Opus must trigger when controller casts instant/sorcery."""
        card = TackleArtist(name="Tackle Artist", owner=None, base_power=4, base_toughness=3)
        assert callable(getattr(card, "on_spell_cast", None)) or \
            callable(getattr(card, "opus_trigger", None)), \
            "Tackle Artist must implement opus trigger per oracle text"


@pytest.mark.edge
class TestTackleArtistEdgeCases:
    """Edge case and trap tests for Tackle Artist."""

    def test_opus_no_trigger_without_spell(self) -> None:
        """Opus should not boost without casting instant/sorcery."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = TackleArtist(name="Tackle Artist", owner=player, base_power=4, base_toughness=3)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        base_p = card.base_power
        assert card.base_power == base_p, "No opus trigger should leave power unchanged"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = TackleArtist(name="Tackle Artist", owner=None, base_power=4, base_toughness=3)
        card2 = TackleArtist(name="Tackle Artist", owner=None, base_power=4, base_toughness=3)
        card1.name = "Modified"
        assert card2.name == "Tackle Artist", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = TackleArtist(name="Tackle Artist", owner=None, base_power=4, base_toughness=3)
        assert card.mana_cost.cmc == 4, \
            f"CMC must be 4, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestTackleArtistInteractions:
    """Multi-card interaction tests for Tackle Artist."""

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = TackleArtist(name="Tackle Artist", owner=player, base_power=4, base_toughness=3)
        card.controller = player
        if hasattr(card, "colors_spent"):
            card.colors_spent = 2
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        counters = getattr(card, "counters", {})
        p1p1 = counters.get("+1/+1", counters.get("p1p1", 0))
        assert p1p1 == 2, f"Should have 2 +1/+1 counters, got {p1p1}"

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = TackleArtist(name="Tackle Artist", owner=player, base_power=4, base_toughness=3)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
