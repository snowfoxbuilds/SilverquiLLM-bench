"""Tests for SOS 157 — Pestbrood Sloth."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_157.card_impl import PestbroodSloth
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent, CreatureDiesTriggeredEvent
from benchmarks.sos.workspace.engine.game import destroy
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestPestbroodSlothProperties:
    """Static card data should match the SOS 157 spec."""

    def test_is_plant_sloth_creature_with_reach(self) -> None:
        card = PestbroodSloth(owner=None)

        assert isinstance(card, Creature)
        assert "Plant" in card.subtypes
        assert "Sloth" in card.subtypes
        assert Keyword.REACH in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = PestbroodSloth(owner=None)

        assert card.name == "Pestbrood Sloth"
        assert card.mana_cost == ManaCost.parse("{3}{G}")
        assert card.base_power == 4
        assert card.base_toughness == 4


class TestPestbroodSlothDiesTrigger:
    """Pestbrood Sloth should make two life-gaining Pest tokens when it dies."""

    def test_registers_a_creature_dies_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PestbroodSloth(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is CreatureDiesTriggeredEvent

    def test_when_it_dies_it_creates_two_black_and_green_pest_tokens(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PestbroodSloth(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        destroy(game, card)

        assert len(game.stack) == 1
        resolve_top(game)

        tokens = [
            permanent
            for permanent in game.get_battlefield(p1).get_all()
            if getattr(permanent, "is_token", False)
        ]
        assert len(tokens) == 2
        for token in tokens:
            assert isinstance(token, Creature)
            assert token.power == 1
            assert token.toughness == 1
            assert "Pest" in token.subtypes
            assert get_colors(token) == {Color.BLACK, Color.GREEN}

    def test_created_pest_tokens_each_gain_you_one_life_when_they_attack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PestbroodSloth(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        destroy(game, card)
        resolve_top(game)

        tokens = [
            permanent
            for permanent in game.get_battlefield(p1).get_all()
            if getattr(permanent, "is_token", False)
        ]

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=tokens[0], attacker=tokens[0]),
        )
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=tokens[1], attacker=tokens[1]),
        )

        assert len(game.stack) == 2
        resolve_top(game)
        resolve_top(game)

        assert p1.life == 22

    def test_another_creature_dying_does_not_trigger_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sloth = PestbroodSloth(owner=p1, controller=p1)
        other = Creature(
            name="Other Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[sloth, other])
        sloth.register_triggers(game)

        destroy(game, other)

        assert game.stack.is_empty()
        assert game.get_battlefield(p1).contains(sloth)
        assert len(game.get_battlefield(p1).get_all()) == 1
