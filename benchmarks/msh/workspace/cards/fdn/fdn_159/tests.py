"""Regression test for FDN 159 — Mocking Sprite.

The crash surface is ``apply_continuous_effect``: it built a
``ContinuousEffect`` at ``Layer.ABILITIES`` / ``SubLayer.ADD_ABILITY``,
neither of which is a real enum member, so the call raised ``AttributeError``.
This test drives ``apply_continuous_effect`` and asserts the effect
constructs at ``Layer.ABILITY``.

Documented limitation (unchanged): the "Instant and sorcery spells you cast
cost {1} less" reduction is structurally unimplementable until the
cost-reduction sweep lands — the effect body is a marker only.
"""

from __future__ import annotations

from cards.fdn.fdn_159.card_impl import MockingSprite
from engine.card import Creature
from engine.continuous_effects import Layer
from engine.types import Keyword, ManaCost
from test_utils import create_game, set_board_state


class TestMockingSpriteProperties:
    def test_name_and_cost(self) -> None:
        card = MockingSprite(owner=None)
        assert card.name == "Mocking Sprite"
        assert card.mana_cost == ManaCost.parse("{2}{U}")
        assert (card.base_power, card.base_toughness) == (2, 1)

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in MockingSprite(owner=None).keywords


class TestMockingSpriteContinuousEffect:
    """The previously-crashing apply_continuous_effect path."""

    def test_apply_continuous_effect_registers_ability_layer_effect(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sprite = MockingSprite(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[sprite])

        before = len(game.effect_manager)
        sprite.apply_continuous_effect(game)  # must not raise AttributeError
        added = game.effect_manager.get_effects_by_source(sprite)

        assert len(game.effect_manager) == before + 1
        assert len(added) == 1
        assert added[0].layer is Layer.ABILITY

    def test_register_triggers_sets_cost_reduction_marker(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sprite = MockingSprite(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[sprite])
        sprite.register_triggers(game)  # must not raise
        assert sprite._provides_cost_reduction is True
