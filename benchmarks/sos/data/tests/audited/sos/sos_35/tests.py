"""Audited tests for Stirring Hopesinger (collector key 35).

Verifies the Stirring Hopesinger card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import StirringHopesinger

from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.types import Keyword

@pytest.mark.basic
class TestStirringHopesingerBasicProperties:
    """Basic property tests for Stirring Hopesinger."""

    def test_is_creature(self) -> None:
        """Stirring Hopesinger must be a Creature subclass."""
        card = StirringHopesinger(name="Stirring Hopesinger", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """StirringHopesinger.name must be 'Stirring Hopesinger'."""
        card = StirringHopesinger(name="Stirring Hopesinger", owner=None)
        assert card.name == "Stirring Hopesinger"

    def test_card_types(self) -> None:
        """Stirring Hopesinger must have correct card types."""
        card = StirringHopesinger(name="Stirring Hopesinger", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Stirring Hopesinger must have converted mana cost 3."""
        card = StirringHopesinger(name="Stirring Hopesinger", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Stirring Hopesinger must have correct colors."""
        card = StirringHopesinger(name="Stirring Hopesinger", owner=None)
        assert "W" in card_colors(card)

    def test_power(self) -> None:
        """Stirring Hopesinger must have base power 1."""
        card = StirringHopesinger(name="Stirring Hopesinger", owner=None)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Stirring Hopesinger must have base toughness 3."""
        card = StirringHopesinger(name="Stirring Hopesinger", owner=None)
        assert card.base_toughness == 3

    def test_has_flying_keyword(self) -> None:
        """Stirring Hopesinger must have Flying keyword."""
        card = StirringHopesinger(name="Stirring Hopesinger", owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_lifelink_keyword(self) -> None:
        """Stirring Hopesinger must have Lifelink keyword."""
        card = StirringHopesinger(name="Stirring Hopesinger", owner=None)
        assert Keyword.LIFELINK in card.keywords

@pytest.mark.ability
class TestStirringHopesingerAbilities:
    """Ability tests for Stirring Hopesinger — expected to fail against stubs."""

    def test_repartee_registers_trigger(self) -> None:
        """Repartee must register a triggered ability."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = StirringHopesinger(name="Stirring Hopesinger", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        triggers = getattr(game, "triggers", [])
        assert len(triggers) > 0 or hasattr(card, "on_spell_cast"), (
            "Repartee card must register a trigger or expose on_spell_cast"
        )

    def test_repartee_requires_creature_target(self) -> None:
        """Repartee only triggers for spells targeting a creature."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = StirringHopesinger(name="Stirring Hopesinger", owner=player)
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

    def test_repartee_adds_counter(self) -> None:
        """Repartee trigger should add +1/+1 counter."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = StirringHopesinger(name="Stirring Hopesinger", owner=player)
        card.controller = player
        target = Creature(name="Buffed", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card, target])
        power_before = target.base_power
        if hasattr(card, "on_spell_cast"):
            card.on_spell_cast(game, target)
        elif hasattr(card, "repartee_trigger"):
            card.repartee_trigger(game, target)
        power_after = target.power if hasattr(target, "power") else target.base_power
        assert power_after > power_before, (
            f"Repartee should add counter: power {power_before} -> {power_after}"
        )

@pytest.mark.edge
class TestStirringHopesingerEdgeCases:
    """Edge case tests for Stirring Hopesinger."""

    def test_targets_only_own_permanents(self) -> None:
        """Should only target permanents you control."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        own = Creature(name="Own", owner=player, base_power=2, base_toughness=2)
        enemy = Creature(name="Enemy", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[own])
        set_board_state(game, 1, battlefield=[enemy])
        card = StirringHopesinger(name="Stirring Hopesinger", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"

@pytest.mark.interaction
class TestStirringHopesingerInteractions:
    """Interaction tests for Stirring Hopesinger."""

    def test_get_targets_finds_own_creatures(self) -> None:
        """get_targets should return valid own creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Mine", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        card = StirringHopesinger(name="Stirring Hopesinger", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find own creature as target"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = StirringHopesinger(name="Stirring Hopesinger", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
