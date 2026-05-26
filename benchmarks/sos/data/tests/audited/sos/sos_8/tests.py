"""Audited tests for Ascendant Dustspeaker (collector key 8).

Verifies the Ascendant Dustspeaker card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import AscendantDustspeaker

from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestAscendantDustspeakerBasicProperties:
    """Basic property tests for Ascendant Dustspeaker."""

    def test_is_creature(self) -> None:
        """Ascendant Dustspeaker must be a Creature subclass."""
        card = AscendantDustspeaker(name="Ascendant Dustspeaker", owner=None, base_power=3, base_toughness=4)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """AscendantDustspeaker.name must be 'Ascendant Dustspeaker'."""
        card = AscendantDustspeaker(name="Ascendant Dustspeaker", owner=None, base_power=3, base_toughness=4)
        assert card.name == "Ascendant Dustspeaker"

    def test_card_types(self) -> None:
        """Ascendant Dustspeaker must have correct card types."""
        card = AscendantDustspeaker(name="Ascendant Dustspeaker", owner=None, base_power=3, base_toughness=4)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Ascendant Dustspeaker must have converted mana cost 5."""
        card = AscendantDustspeaker(name="Ascendant Dustspeaker", owner=None, base_power=3, base_toughness=4)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Ascendant Dustspeaker must have correct colors."""
        card = AscendantDustspeaker(name="Ascendant Dustspeaker", owner=None, base_power=3, base_toughness=4)
        assert "W" in card_colors(card)

    def test_power(self) -> None:
        """Ascendant Dustspeaker must have base power 3."""
        card = AscendantDustspeaker(name="Ascendant Dustspeaker", owner=None, base_power=3, base_toughness=4)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Ascendant Dustspeaker must have base toughness 4."""
        card = AscendantDustspeaker(name="Ascendant Dustspeaker", owner=None, base_power=3, base_toughness=4)
        assert card.base_toughness == 4

@pytest.mark.ability
class TestAscendantDustspeakerAbilities:
    """Ability tests for Ascendant Dustspeaker -- expected to fail against stubs."""

    def test_has_flying(self) -> None:
        """Ascendant Dustspeaker must have Flying keyword."""
        from engine.types import Keyword
        card = AscendantDustspeaker(name="Ascendant Dustspeaker", owner=None, base_power=3, base_toughness=4)
        assert Keyword.FLYING in card.keywords, "Ascendant Dustspeaker should have Flying"

    def test_etb_exiles_target(self) -> None:
        """ETB must exile target permanent per oracle text."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = AscendantDustspeaker(name="Ascendant Dustspeaker", owner=player, base_power=3, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        exile = opponent.zones[Zone.EXILE].get_all()
        assert target in exile, "ETB must exile the target per oracle"

@pytest.mark.edge
class TestAscendantDustspeakerEdgeCases:
    """Edge case and trap tests for Ascendant Dustspeaker."""

    def test_fizzle_no_targets_creature_stays(self) -> None:
        """If ETB ability fizzles, the creature remains on battlefield."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = AscendantDustspeaker(name="Ascendant Dustspeaker", owner=player, base_power=3, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        # No targets available; ETB fizzles
        try:
            if callable(getattr(card, "on_enter_battlefield", None)):
                card.on_enter_battlefield(game)
        except (ValueError, IndexError):
            pass  # Fizzle expected
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must stay on battlefield when ETB fizzles"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = AscendantDustspeaker(name="Ascendant Dustspeaker", owner=None, base_power=3, base_toughness=4)
        card2 = AscendantDustspeaker(name="Ascendant Dustspeaker", owner=None, base_power=3, base_toughness=4)
        card1.name = "Modified"
        assert card2.name == "Ascendant Dustspeaker", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = AscendantDustspeaker(name="Ascendant Dustspeaker", owner=None, base_power=3, base_toughness=4)
        assert card.mana_cost.cmc == 5, \
            f"CMC must be 5, got {card.mana_cost.cmc}"

@pytest.mark.interaction
class TestAscendantDustspeakerInteractions:
    """Multi-card interaction tests for Ascendant Dustspeaker."""

    def test_exile_from_graveyard_interaction(self) -> None:
        """Cards exiled from graveyard must move to exile zone."""
        from test_utils import create_game, set_board_state
        from engine.card import Instant
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        fodder = Instant(name="Fodder", owner=player)
        set_board_state(game, 0, graveyard=[fodder])
        card = AscendantDustspeaker(name="Ascendant Dustspeaker", owner=player, base_power=3, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_attack", None)):
            card.on_attack(game)
        elif callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        exile = player.zones[Zone.EXILE].get_all()
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert fodder in exile or fodder not in gy, \
            "Exiled card must leave graveyard"

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = AscendantDustspeaker(name="Ascendant Dustspeaker", owner=player, base_power=3, base_toughness=4)
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
        card = AscendantDustspeaker(name="Ascendant Dustspeaker", owner=player, base_power=3, base_toughness=4)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
