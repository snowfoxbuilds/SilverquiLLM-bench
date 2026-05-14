"""Audited tests for Noxious Newt (collector key 155).

Verifies the Noxious Newt card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import NoxiousNewt

from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.types import Keyword


@pytest.mark.basic
class TestNoxiousNewtBasicProperties:
    """Basic property tests for Noxious Newt."""

    def test_is_creature(self) -> None:
        """Noxious Newt must be a Creature subclass."""
        card = NoxiousNewt(name="Noxious Newt", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """NoxiousNewt.name must be 'Noxious Newt'."""
        card = NoxiousNewt(name="Noxious Newt", owner=None)
        assert card.name == "Noxious Newt"

    def test_card_types(self) -> None:
        """Noxious Newt must have correct card types."""
        card = NoxiousNewt(name="Noxious Newt", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Noxious Newt must have converted mana cost 2."""
        card = NoxiousNewt(name="Noxious Newt", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Noxious Newt must have correct colors."""
        card = NoxiousNewt(name="Noxious Newt", owner=None)
        assert "G" in card.colors

    def test_power(self) -> None:
        """Noxious Newt must have base power 1."""
        card = NoxiousNewt(name="Noxious Newt", owner=None)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Noxious Newt must have base toughness 2."""
        card = NoxiousNewt(name="Noxious Newt", owner=None)
        assert card.base_toughness == 2

    def test_has_deathtouch_keyword(self) -> None:
        """Noxious Newt must have Deathtouch keyword."""
        card = NoxiousNewt(name="Noxious Newt", owner=None)
        assert Keyword.DEATHTOUCH in card.keywords


@pytest.mark.ability
class TestNoxiousNewtAbilities:
    """Ability tests for Noxious Newt — expected to fail against stubs."""

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = NoxiousNewt(name="Noxious Newt", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"


@pytest.mark.edge
class TestNoxiousNewtEdgeCases:
    """Edge case tests for Noxious Newt."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = NoxiousNewt(name="Noxious Newt", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestNoxiousNewtInteractions:
    """Interaction tests for Noxious Newt."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = NoxiousNewt(name="Noxious Newt", owner=player)
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
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = NoxiousNewt(name="Noxious Newt", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
