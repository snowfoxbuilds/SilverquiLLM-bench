"""Tests for SOS 13 — Emeritus of Truce."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


def _inklings(game, player):
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if isinstance(obj, Creature) and "Inkling" in getattr(obj, "subtypes", set())
    ]


def _trigger_requirements(trigger, game, event):
    requirements = trigger.target_requirements
    if callable(requirements):
        requirements = requirements(game, event)
    return list(requirements or [])


class TestEmeritusOfTruceProperties:
    """Front-face characteristics should match the creature half of the spec."""

    def test_front_face_is_a_three_three_cat_cleric_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Emeritus of Truce"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert CardType.CREATURE in card.card_types
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestEmeritusOfTruceTriggeredAbility:
    """Its ETB ability should target a player and resolve from the stack."""

    def test_registers_a_self_enters_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent
        assert triggers[0].controller is p1

    def test_enters_trigger_targets_a_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        requirements = _trigger_requirements(
            trigger,
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )

        assert len(requirements) == 1
        requirement = requirements[0]
        assert isinstance(requirement, TargetRequirement)
        assert requirement.zone == Zone.BATTLEFIELD
        assert "target player" in requirement.description.lower()
        assert requirement.filter_fn(p1) is True
        assert requirement.filter_fn(p2) is True
        assert requirement.filter_fn(
            Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        ) is False


class TestEmeritusOfTruceResolution:
    """Casting the creature should create the token, then check preparation."""

    def test_casting_it_makes_the_target_player_create_an_inkling(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2},
        )

        cast_spell(game, 0, "Emeritus of Truce", targets=[p2])

        assert game.get_battlefield(p1).contains(card)
        assert len(_inklings(game, p1)) == 0
        assert len(_inklings(game, p2)) == 1

        token = _inklings(game, p2)[0]
        assert token.is_token is True
        assert token.controller is p2
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert "Inkling" in token.subtypes
        assert Keyword.FLYING in token.keywords

    def test_targeting_an_opponent_can_prepare_it_after_the_token_is_created(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        opposing_bear = Creature(
            name="Grizzly Bears",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2},
        )
        set_board_state(game, 1, battlefield=[opposing_bear])

        cast_spell(game, 0, "Emeritus of Truce", targets=[p2])

        exile_cards = game.get_exile(p1).get_all()
        assert len(exile_cards) == 1
        prepared_copy = exile_cards[0]
        assert prepared_copy.name == "Swords to Plowshares"
        assert prepared_copy.mana_cost == ManaCost.parse("{W}")
        assert CardType.INSTANT in prepared_copy.card_types
        assert len(game.get_exile(p2).get_all()) == 0

    def test_targeting_yourself_can_keep_it_unprepared_when_creature_counts_flip(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        opposing_bear = Creature(
            name="Grizzly Bears",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2},
        )
        set_board_state(game, 1, battlefield=[opposing_bear])

        cast_spell(game, 0, "Emeritus of Truce", targets=[p1])

        assert len(_inklings(game, p1)) == 1
        assert len(game.get_exile(p1).get_all()) == 0
