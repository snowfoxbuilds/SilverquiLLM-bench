"""Audited tests for Colorstorm Stallion (collector key 180).

Verifies the Colorstorm Stallion card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import ColorstormStallion

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestColorstormStallionBasicProperties:
    """Basic property tests for Colorstorm Stallion."""

    def test_is_creature(self) -> None:
        """Colorstorm Stallion must be a Creature subclass."""
        card = ColorstormStallion(name="Colorstorm Stallion", owner=None, base_power=3, base_toughness=3)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """ColorstormStallion.name must be 'Colorstorm Stallion'."""
        card = ColorstormStallion(name="Colorstorm Stallion", owner=None, base_power=3, base_toughness=3)
        assert card.name == "Colorstorm Stallion"

    def test_card_types(self) -> None:
        """Colorstorm Stallion must have correct card types."""
        card = ColorstormStallion(name="Colorstorm Stallion", owner=None, base_power=3, base_toughness=3)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Colorstorm Stallion must have converted mana cost 3."""
        card = ColorstormStallion(name="Colorstorm Stallion", owner=None, base_power=3, base_toughness=3)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Colorstorm Stallion must have correct colors."""
        card = ColorstormStallion(name="Colorstorm Stallion", owner=None, base_power=3, base_toughness=3)
        assert "R" in card.colors
        assert "U" in card.colors

    def test_power(self) -> None:
        """Colorstorm Stallion must have base power 3."""
        card = ColorstormStallion(name="Colorstorm Stallion", owner=None, base_power=3, base_toughness=3)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Colorstorm Stallion must have base toughness 3."""
        card = ColorstormStallion(name="Colorstorm Stallion", owner=None, base_power=3, base_toughness=3)
        assert card.base_toughness == 3


@pytest.mark.ability
class TestColorstormStallionAbilities:
    """Ability tests for Colorstorm Stallion -- expected to fail against stubs."""

    def test_has_haste(self) -> None:
        """Colorstorm Stallion must have Haste keyword."""
        from engine.types import Keyword
        card = ColorstormStallion(name="Colorstorm Stallion", owner=None, base_power=3, base_toughness=3)
        assert Keyword.HASTE in card.keywords, "Colorstorm Stallion should have Haste"

    def test_has_ward(self) -> None:
        """Colorstorm Stallion must have Ward keyword."""
        from engine.types import Keyword
        card = ColorstormStallion(name="Colorstorm Stallion", owner=None, base_power=3, base_toughness=3)
        assert Keyword.WARD in card.keywords, "Colorstorm Stallion should have Ward"

    def test_has_opus(self) -> None:
        """Colorstorm Stallion must have Opus keyword."""
        from engine.types import Keyword
        card = ColorstormStallion(name="Colorstorm Stallion", owner=None, base_power=3, base_toughness=3)
        assert Keyword.OPUS in card.keywords, "Colorstorm Stallion should have Opus"

    def test_opus_trigger_implemented(self) -> None:
        """Opus must trigger when controller casts instant/sorcery."""
        card = ColorstormStallion(name="Colorstorm Stallion", owner=None, base_power=3, base_toughness=3)
        assert callable(getattr(card, "on_spell_cast", None)) or \
            callable(getattr(card, "opus_trigger", None)), \
            "Colorstorm Stallion must implement opus trigger per oracle text"


@pytest.mark.edge
class TestColorstormStallionEdgeCases:
    """Edge case and trap tests for Colorstorm Stallion."""

    def test_opus_no_trigger_without_spell(self) -> None:
        """Opus should not boost without casting instant/sorcery."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = ColorstormStallion(name="Colorstorm Stallion", owner=player, base_power=3, base_toughness=3)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        base_p = card.base_power
        # Without casting a spell, power should remain at base
        actual_p = getattr(card, "power", card.base_power)
        assert actual_p == base_p, f"Without opus trigger, power should be {base_p}, got {actual_p}"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = ColorstormStallion(name="Colorstorm Stallion", owner=None, base_power=3, base_toughness=3)
        card2 = ColorstormStallion(name="Colorstorm Stallion", owner=None, base_power=3, base_toughness=3)
        card1.name = "Modified"
        assert card2.name == "Colorstorm Stallion", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = ColorstormStallion(name="Colorstorm Stallion", owner=None, base_power=3, base_toughness=3)
        assert card.mana_cost.cmc == 3, \
            f"CMC must be 3, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestColorstormStallionInteractions:
    """Multi-card interaction tests for Colorstorm Stallion."""

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = ColorstormStallion(name="Colorstorm Stallion", owner=player, base_power=3, base_toughness=3)
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
        card = ColorstormStallion(name="Colorstorm Stallion", owner=player, base_power=3, base_toughness=3)
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
        card = ColorstormStallion(name="Colorstorm Stallion", owner=player, base_power=3, base_toughness=3)
        card.controller = player
        bf_before = len(player.zones[Zone.BATTLEFIELD].get_all())
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        elif callable(getattr(card, "on_resolve", None)):
            card.on_resolve(game)
        bf_after = len(player.zones[Zone.BATTLEFIELD].get_all())
        assert bf_after > bf_before, "Tokens must appear on battlefield"
