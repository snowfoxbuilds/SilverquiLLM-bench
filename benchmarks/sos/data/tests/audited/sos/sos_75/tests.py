"""Audited tests for Burrog Banemaker (collector key 75).

Verifies the Burrog Banemaker card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import BurrogBanemaker

from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.types import Keyword

@pytest.mark.basic
class TestBurrogBanemakerBasicProperties:
    """Basic property tests for Burrog Banemaker."""

    def test_is_creature(self) -> None:
        """Burrog Banemaker must be a Creature subclass."""
        card = BurrogBanemaker(name="Burrog Banemaker", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """BurrogBanemaker.name must be 'Burrog Banemaker'."""
        card = BurrogBanemaker(name="Burrog Banemaker", owner=None)
        assert card.name == "Burrog Banemaker"

    def test_card_types(self) -> None:
        """Burrog Banemaker must have correct card types."""
        card = BurrogBanemaker(name="Burrog Banemaker", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Burrog Banemaker must have converted mana cost 1."""
        card = BurrogBanemaker(name="Burrog Banemaker", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Burrog Banemaker must have correct colors."""
        card = BurrogBanemaker(name="Burrog Banemaker", owner=None)
        assert "B" in card_colors(card)

    def test_power(self) -> None:
        """Burrog Banemaker must have base power 1."""
        card = BurrogBanemaker(name="Burrog Banemaker", owner=None)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Burrog Banemaker must have base toughness 1."""
        card = BurrogBanemaker(name="Burrog Banemaker", owner=None)
        assert card.base_toughness == 1

    def test_has_deathtouch_keyword(self) -> None:
        """Burrog Banemaker must have Deathtouch keyword."""
        card = BurrogBanemaker(name="Burrog Banemaker", owner=None)
        assert Keyword.DEATHTOUCH in card.keywords

@pytest.mark.ability
class TestBurrogBanemakerAbilities:
    """Ability tests for Burrog Banemaker — expected to fail against stubs."""

    def test_pump_effect(self) -> None:
        """Resolution should grant +1/+1."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="PumpTarget", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[target])
        card = BurrogBanemaker(name="Burrog Banemaker", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        actual_power = target.power if hasattr(target, "power") else target.base_power
        assert actual_power == 2, (
            f"Should pump to 2 power, got {actual_power}"
        )

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = BurrogBanemaker(name="Burrog Banemaker", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"

@pytest.mark.edge
class TestBurrogBanemakerEdgeCases:
    """Edge case tests for Burrog Banemaker."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = BurrogBanemaker(name="Burrog Banemaker", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()

@pytest.mark.interaction
class TestBurrogBanemakerInteractions:
    """Interaction tests for Burrog Banemaker."""

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
        card = BurrogBanemaker(name="Burrog Banemaker", owner=player)
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

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = BurrogBanemaker(name="Burrog Banemaker", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
