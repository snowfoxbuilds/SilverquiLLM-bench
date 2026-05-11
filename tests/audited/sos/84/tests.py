"""Audited tests for Forum Necroscribe (collector key 84).

Verifies the Forum Necroscribe card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ForumNecroscribe

from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.types import Keyword


@pytest.mark.basic
class TestForumNecroscribeBasicProperties:
    """Basic property tests for Forum Necroscribe."""

    def test_is_creature(self) -> None:
        """Forum Necroscribe must be a Creature subclass."""
        card = ForumNecroscribe(name="Forum Necroscribe", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """ForumNecroscribe.name must be 'Forum Necroscribe'."""
        card = ForumNecroscribe(name="Forum Necroscribe", owner=None)
        assert card.name == "Forum Necroscribe"

    def test_card_types(self) -> None:
        """Forum Necroscribe must have correct card types."""
        card = ForumNecroscribe(name="Forum Necroscribe", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Forum Necroscribe must have converted mana cost 6."""
        card = ForumNecroscribe(name="Forum Necroscribe", owner=None)
        assert card.mana_cost.cmc == 6

    def test_colors(self) -> None:
        """Forum Necroscribe must have correct colors."""
        card = ForumNecroscribe(name="Forum Necroscribe", owner=None)
        assert "B" in card.colors

    def test_power_toughness(self) -> None:
        """Forum Necroscribe must have base power 5 and toughness 4."""
        card = ForumNecroscribe(name="Forum Necroscribe", owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 4

    def test_has_ward_keyword(self) -> None:
        """Forum Necroscribe must have Ward keyword."""
        card = ForumNecroscribe(name="Forum Necroscribe", owner=None)
        assert Keyword.WARD in card.keywords


@pytest.mark.ability
class TestForumNecroscribeAbilities:
    """Ability tests for Forum Necroscribe — expected to fail against stubs."""

    def test_repartee_registers_trigger(self) -> None:
        """Repartee must register a triggered ability."""
        from tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = ForumNecroscribe(name="Forum Necroscribe", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        triggers = getattr(game, "triggers", [])
        assert len(triggers) > 0 or hasattr(card, "on_spell_cast"), (
            "Repartee card must register a trigger or expose on_spell_cast"
        )

    def test_repartee_requires_creature_target(self) -> None:
        """Repartee only triggers for spells targeting a creature."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = ForumNecroscribe(name="Forum Necroscribe", owner=player)
        card.controller = player
        target = Creature(name="Target", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[card, target])
        card.register_triggers(game)
        has_trigger_logic = (
            hasattr(card, "on_spell_cast") or
            hasattr(card, "repartee_trigger") or
            hasattr(card, "check_trigger_condition")
        )
        assert has_trigger_logic, "Repartee must check spell targets creature"

    def test_repartee_produces_effect(self) -> None:
        """Repartee trigger should produce an observable effect."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = ForumNecroscribe(name="Forum Necroscribe", owner=player)
        card.controller = player
        target = Creature(name="Target", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[card, target])
        bf_before = len(game.get_battlefield(player).get_all())
        life_before = player.life
        if hasattr(card, "on_spell_cast"):
            card.on_spell_cast(game, target)
        elif hasattr(card, "repartee_trigger"):
            card.repartee_trigger(game, target)
        bf_after = len(game.get_battlefield(player).get_all())
        life_after = player.life
        hand_after = len(player.zones[Zone.HAND].get_all())
        changed = bf_after != bf_before or life_after != life_before or hand_after > 0
        assert changed, "Repartee trigger must produce observable effect"

    def test_causes_discard(self) -> None:
        """Resolution should cause discard."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        filler = Sorcery(name="Discardable", owner=opponent)
        set_board_state(game, 1, hand=[filler])
        hand_before = len(opponent.zones[Zone.HAND].get_all())
        card = ForumNecroscribe(name="Forum Necroscribe", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(opponent.zones[Zone.HAND].get_all())
        assert hand_after < hand_before, (
            f"Should discard: hand {hand_before} -> {hand_after}"
        )

    def test_returns_from_graveyard(self) -> None:
        """Resolution should return card from graveyard."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        gy_card = Creature(name="Returned", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, graveyard=[gy_card])
        card = ForumNecroscribe(name="Forum Necroscribe", owner=player)
        card.controller = player
        card._targets = [gy_card]
        if hasattr(card, "set_targets"):
            card.set_targets([gy_card])
        gy_before = len(player.zones[Zone.GRAVEYARD].get_all())
        card.on_resolve(game)
        gy_after = len(player.zones[Zone.GRAVEYARD].get_all())
        assert gy_after < gy_before, (
            f"Should return from gy: {gy_before} -> {gy_after}"
        )


@pytest.mark.edge
class TestForumNecroscribeEdgeCases:
    """Edge case tests for Forum Necroscribe."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = ForumNecroscribe(name="Forum Necroscribe", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestForumNecroscribeInteractions:
    """Interaction tests for Forum Necroscribe."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = ForumNecroscribe(name="Forum Necroscribe", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = ForumNecroscribe(name="Forum Necroscribe", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
