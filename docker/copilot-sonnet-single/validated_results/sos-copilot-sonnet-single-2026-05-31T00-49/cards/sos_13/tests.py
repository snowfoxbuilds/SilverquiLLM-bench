"""Tests for sos_13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class TestEmeritusProperties:
    def test_name(self) -> None:
        assert EmeritusOfTruceSwordsToPlowshares(owner=None).name == "Emeritus of Truce"

    def test_mana_cost(self) -> None:
        assert EmeritusOfTruceSwordsToPlowshares(owner=None).mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_subtypes(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_power_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_starts_unprepared(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.is_prepared is False


class TestEmeritusETBToken:
    """ETB creates a 1/1 Inkling token with flying for the target player."""

    def test_etb_creates_inkling_on_target_player_battlefield(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        from engine.events import EntersBattlefieldTriggeredEvent
        # Fire ETB manually to simulate entering.
        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        trigger.effect(game)
        bf = game.get_battlefield(p1)
        inklings = [c for c in bf.get_all() if getattr(c, "name", "") == "Inkling"]
        assert len(inklings) == 1

    def test_inkling_has_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        trigger.effect(game)
        bf = game.get_battlefield(p1)
        inklings = [c for c in bf.get_all() if getattr(c, "name", "") == "Inkling"]
        assert Keyword.FLYING in inklings[0].keywords

    def test_inkling_is_1_1(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        trigger.effect(game)
        bf = game.get_battlefield(p1)
        inklings = [c for c in bf.get_all() if getattr(c, "name", "") == "Inkling"]
        assert inklings[0].base_power == 1
        assert inklings[0].base_toughness == 1


class TestEmeritusPreparation:
    """Becomes prepared if opponent has more creatures."""

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # p1 controls: just the Emeritus (1 creature, but not counted yet in ETB).
        # p2 controls: 2 creatures.
        opp_creature1 = Creature(name="Opp1", base_power=2, base_toughness=2)
        opp_creature2 = Creature(name="Opp2", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[opp_creature1, opp_creature2])
        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        trigger.effect(game)
        assert card.is_prepared is True

    def test_not_prepared_when_equal_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        p1_creature = Creature(name="Bear", base_power=2, base_toughness=2)
        p2_creature = Creature(name="Opp Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card, p1_creature])
        set_board_state(game, 1, battlefield=[p2_creature])
        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        trigger.effect(game)
        assert card.is_prepared is False

    def test_not_prepared_when_controller_has_more_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        p1_extra = Creature(name="Extra", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card, p1_extra])
        set_board_state(game, 1, battlefield=[])
        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        trigger.effect(game)
        assert card.is_prepared is False


class TestSwordsToPlowshares:
    """cast_swords_to_plowshares exiles the target and gives life."""

    def test_exile_creature_when_prepared(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = True
        target = Creature(name="Grizzly Bears", base_power=2, base_toughness=2,
                          owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])
        result = card.cast_swords_to_plowshares(game, target)
        assert result is True
        # Target should be in exile, not on battlefield.
        assert game.get_exile(p2).contains(target)
        assert not game.get_battlefield(p2).contains(target)

    def test_life_gain_equals_power(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = True
        target = Creature(name="Big Bear", base_power=4, base_toughness=4,
                          owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])
        card.cast_swords_to_plowshares(game, target)
        assert p2.life == 24  # gained 4 (power of target)

    def test_cannot_cast_when_not_prepared(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = False
        target = Creature(name="Bear", base_power=2, base_toughness=2,
                          owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])
        result = card.cast_swords_to_plowshares(game, target)
        assert result is False
        assert game.get_battlefield(p2).contains(target)  # unchanged

    def test_unprepares_after_casting(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = True
        target = Creature(name="Bear", base_power=2, base_toughness=2,
                          owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])
        card.cast_swords_to_plowshares(game, target)
        assert card.is_prepared is False
