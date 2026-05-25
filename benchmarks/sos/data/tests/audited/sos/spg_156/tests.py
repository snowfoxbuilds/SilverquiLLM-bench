"""Audited tests for Adrix and Nev, Twincasters (collector key spg_156).

Verifies the Adrix and Nev, Twincasters card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import AdrixAndNevTwincasters

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestAdrixAndNevTwincastersBasicProperties:
    """Basic property tests for Adrix and Nev, Twincasters."""

    def test_is_creature(self) -> None:
        """Adrix and Nev, Twincasters must be a Creature subclass."""
        card = AdrixAndNevTwincasters(name="Adrix and Nev, Twincasters", owner=None, base_power=2, base_toughness=2)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """AdrixAndNevTwincasters.name must be 'Adrix and Nev, Twincasters'."""
        card = AdrixAndNevTwincasters(name="Adrix and Nev, Twincasters", owner=None, base_power=2, base_toughness=2)
        assert card.name == "Adrix and Nev, Twincasters"

    def test_card_types(self) -> None:
        """Adrix and Nev, Twincasters must have correct card types."""
        card = AdrixAndNevTwincasters(name="Adrix and Nev, Twincasters", owner=None, base_power=2, base_toughness=2)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Adrix and Nev, Twincasters must have converted mana cost 4."""
        card = AdrixAndNevTwincasters(name="Adrix and Nev, Twincasters", owner=None, base_power=2, base_toughness=2)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Adrix and Nev, Twincasters must have correct colors."""
        card = AdrixAndNevTwincasters(name="Adrix and Nev, Twincasters", owner=None, base_power=2, base_toughness=2)
        assert "G" in card.colors
        assert "U" in card.colors

    def test_power(self) -> None:
        """Adrix and Nev, Twincasters must have base power 2."""
        card = AdrixAndNevTwincasters(name="Adrix and Nev, Twincasters", owner=None, base_power=2, base_toughness=2)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Adrix and Nev, Twincasters must have base toughness 2."""
        card = AdrixAndNevTwincasters(name="Adrix and Nev, Twincasters", owner=None, base_power=2, base_toughness=2)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestAdrixAndNevTwincastersAbilities:
    """Ability tests for Adrix and Nev, Twincasters -- expected to fail against stubs."""

    def test_has_ward(self) -> None:
        """Adrix and Nev, Twincasters must have Ward keyword."""
        from engine.types import Keyword
        card = AdrixAndNevTwincasters(name="Adrix and Nev, Twincasters", owner=None, base_power=2, base_toughness=2)
        assert Keyword.WARD in card.keywords, "Adrix and Nev, Twincasters should have Ward"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = AdrixAndNevTwincasters(name="Adrix and Nev, Twincasters", owner=None, base_power=2, base_toughness=2)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Adrix and Nev, Twincasters must implement behavioral method"


@pytest.mark.edge
class TestAdrixAndNevTwincastersEdgeCases:
    """Edge case and trap tests for Adrix and Nev, Twincasters."""

    def test_fizzle_no_targets_creature_stays(self) -> None:
        """If ETB ability fizzles, the creature remains on battlefield."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = AdrixAndNevTwincasters(name="Adrix and Nev, Twincasters", owner=player, base_power=2, base_toughness=2)
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
        card1 = AdrixAndNevTwincasters(name="Adrix and Nev, Twincasters", owner=None, base_power=2, base_toughness=2)
        card2 = AdrixAndNevTwincasters(name="Adrix and Nev, Twincasters", owner=None, base_power=2, base_toughness=2)
        card1.name = "Modified"
        assert card2.name == "Adrix and Nev, Twincasters", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = AdrixAndNevTwincasters(name="Adrix and Nev, Twincasters", owner=None, base_power=2, base_toughness=2)
        assert card.mana_cost.cmc == 4, \
            f"CMC must be 4, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestAdrixAndNevTwincastersInteractions:
    """Multi-card interaction tests for Adrix and Nev, Twincasters."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = AdrixAndNevTwincasters(name="Adrix and Nev, Twincasters", owner=player, base_power=2, base_toughness=2)
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
        card = AdrixAndNevTwincasters(name="Adrix and Nev, Twincasters", owner=player, base_power=2, base_toughness=2)
        card.controller = player
        bf_before = len(player.zones[Zone.BATTLEFIELD].get_all())
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        elif callable(getattr(card, "on_resolve", None)):
            card.on_resolve(game)
        bf_after = len(player.zones[Zone.BATTLEFIELD].get_all())
        assert bf_after > bf_before, "Tokens must appear on battlefield"
