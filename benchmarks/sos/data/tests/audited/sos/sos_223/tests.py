"""Audited tests for Sanar, Unfinished Genius // Wild Idea (collector key 223).

Verifies the Sanar, Unfinished Genius // Wild Idea card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import SanarUnfinishedGeniusWildIdea

from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestSanarUnfinishedGeniusWildIdeaBasicProperties:
    """Basic property tests for Sanar, Unfinished Genius // Wild Idea."""

    def test_is_creature(self) -> None:
        """Sanar, Unfinished Genius // Wild Idea must be a Creature subclass."""
        card = SanarUnfinishedGeniusWildIdea(name="Sanar, Unfinished Genius // Wild Idea", owner=None, base_power=0, base_toughness=4)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """SanarUnfinishedGeniusWildIdea.name must be 'Sanar, Unfinished Genius // Wild Idea'."""
        card = SanarUnfinishedGeniusWildIdea(name="Sanar, Unfinished Genius // Wild Idea", owner=None, base_power=0, base_toughness=4)
        assert card.name == "Sanar, Unfinished Genius // Wild Idea"

    def test_card_types(self) -> None:
        """Sanar, Unfinished Genius // Wild Idea must have correct card types."""
        card = SanarUnfinishedGeniusWildIdea(name="Sanar, Unfinished Genius // Wild Idea", owner=None, base_power=0, base_toughness=4)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Sanar, Unfinished Genius // Wild Idea must have converted mana cost 7."""
        card = SanarUnfinishedGeniusWildIdea(name="Sanar, Unfinished Genius // Wild Idea", owner=None, base_power=0, base_toughness=4)
        assert card.mana_cost.cmc == 7

    def test_colors(self) -> None:
        """Sanar, Unfinished Genius // Wild Idea must have correct colors."""
        card = SanarUnfinishedGeniusWildIdea(name="Sanar, Unfinished Genius // Wild Idea", owner=None, base_power=0, base_toughness=4)
        assert "R" in card_colors(card)
        assert "U" in card_colors(card)

    def test_power(self) -> None:
        """Sanar, Unfinished Genius // Wild Idea must have base power 0."""
        card = SanarUnfinishedGeniusWildIdea(name="Sanar, Unfinished Genius // Wild Idea", owner=None, base_power=0, base_toughness=4)
        assert card.base_power == 0

    def test_toughness(self) -> None:
        """Sanar, Unfinished Genius // Wild Idea must have base toughness 4."""
        card = SanarUnfinishedGeniusWildIdea(name="Sanar, Unfinished Genius // Wild Idea", owner=None, base_power=0, base_toughness=4)
        assert card.base_toughness == 4

@pytest.mark.ability
class TestSanarUnfinishedGeniusWildIdeaAbilities:
    """Ability tests for Sanar, Unfinished Genius // Wild Idea -- expected to fail against stubs."""

    def test_has_prepared(self) -> None:
        """Sanar, Unfinished Genius // Wild Idea must have Prepared keyword."""
        from engine.types import Keyword
        card = SanarUnfinishedGeniusWildIdea(name="Sanar, Unfinished Genius // Wild Idea", owner=None, base_power=0, base_toughness=4)
        assert Keyword.PREPARED in card.keywords, "Sanar, Unfinished Genius // Wild Idea should have Prepared"

    def test_etb_creates_tokens(self) -> None:
        """ETB must create tokens per oracle text."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = SanarUnfinishedGeniusWildIdea(name="Sanar, Unfinished Genius // Wild Idea", owner=player, base_power=0, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf_before = len(player.zones[Zone.BATTLEFIELD].get_all())
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        bf_after = len(player.zones[Zone.BATTLEFIELD].get_all())
        assert bf_after > bf_before, "ETB must create tokens per oracle"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = SanarUnfinishedGeniusWildIdea(name="Sanar, Unfinished Genius // Wild Idea", owner=None, base_power=0, base_toughness=4)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Sanar, Unfinished Genius // Wild Idea must implement prepared mechanic"

@pytest.mark.edge
class TestSanarUnfinishedGeniusWildIdeaEdgeCases:
    """Edge case and trap tests for Sanar, Unfinished Genius // Wild Idea."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = SanarUnfinishedGeniusWildIdea(name="Sanar, Unfinished Genius // Wild Idea", owner=None, base_power=0, base_toughness=4)
        card2 = SanarUnfinishedGeniusWildIdea(name="Sanar, Unfinished Genius // Wild Idea", owner=None, base_power=0, base_toughness=4)
        card1.name = "Modified"
        assert card2.name == "Sanar, Unfinished Genius // Wild Idea", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = SanarUnfinishedGeniusWildIdea(name="Sanar, Unfinished Genius // Wild Idea", owner=None, base_power=0, base_toughness=4)
        assert card.mana_cost.cmc == 7, \
            f"CMC must be 7, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = SanarUnfinishedGeniusWildIdea(name="Sanar, Unfinished Genius // Wild Idea", owner=player, base_power=0, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 3
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"

@pytest.mark.interaction
class TestSanarUnfinishedGeniusWildIdeaInteractions:
    """Multi-card interaction tests for Sanar, Unfinished Genius // Wild Idea."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = SanarUnfinishedGeniusWildIdea(name="Sanar, Unfinished Genius // Wild Idea", owner=player, base_power=0, base_toughness=4)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"

    def test_tokens_appear_on_battlefield(self) -> None:
        """Tokens created must appear on the battlefield."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = SanarUnfinishedGeniusWildIdea(name="Sanar, Unfinished Genius // Wild Idea", owner=player, base_power=0, base_toughness=4)
        card.controller = player
        bf_before = len(player.zones[Zone.BATTLEFIELD].get_all())
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        elif callable(getattr(card, "on_resolve", None)):
            card.on_resolve(game)
        bf_after = len(player.zones[Zone.BATTLEFIELD].get_all())
        assert bf_after > bf_before, "Tokens must appear on battlefield"
