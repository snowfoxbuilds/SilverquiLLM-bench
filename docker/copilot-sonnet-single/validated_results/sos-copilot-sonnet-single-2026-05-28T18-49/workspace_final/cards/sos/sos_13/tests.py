"""Tests for Emeritus of Truce // Swords to Plowshares (sos_13)."""

from __future__ import annotations

import pytest
from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class TestEmeritusProperties:
    """Static card properties."""

    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce"

    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types
        assert isinstance(card, Creature)

    def test_power_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_is_legendary(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_not_prepared_initially(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.is_prepared is False


class TestEmeritusETBTrigger:
    """ETB trigger: target player creates a 1/1 Inkling with flying."""

    def _get_etb_trigger(self, game, card):
        from engine.events import EntersBattlefieldTriggeredEvent
        for t in game.trigger_manager.get_triggers_for_source(card):
            from engine.events import EntersBattlefieldTriggeredEvent
            if t.event_type is EntersBattlefieldTriggeredEvent:
                return t
        return None

    def test_creates_inkling_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        # Script: choose p1 as target
        p1._script.append(p1)

        trigger = self._get_etb_trigger(game, card)
        assert trigger is not None
        trigger.effect(game)

        bf = game.get_battlefield(p1).get_all()
        inklings = [c for c in bf if "Inkling" in getattr(c, "subtypes", set())]
        assert len(inklings) == 1

    def test_inkling_has_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        p1._script.append(p1)
        trigger = self._get_etb_trigger(game, card)
        trigger.effect(game)
        bf = game.get_battlefield(p1).get_all()
        inkling = next(c for c in bf if "Inkling" in getattr(c, "subtypes", set()))
        assert Keyword.FLYING & inkling.keywords

    def test_inkling_stats(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        p1._script.append(p1)
        trigger = self._get_etb_trigger(game, card)
        trigger.effect(game)
        bf = game.get_battlefield(p1).get_all()
        inkling = next(c for c in bf if "Inkling" in getattr(c, "subtypes", set()))
        assert inkling.base_power == 1
        assert inkling.base_toughness == 1

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # Give opponent more creatures
        opp_creature1 = Creature(name="Orc1", base_power=2, base_toughness=2,
                                  owner=p2, controller=p2)
        opp_creature2 = Creature(name="Orc2", base_power=2, base_toughness=2,
                                  owner=p2, controller=p2)
        opp_creature3 = Creature(name="Orc3", base_power=2, base_toughness=2,
                                  owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[opp_creature1, opp_creature2, opp_creature3])

        card.register_triggers(game)
        p1._script.append(p1)  # target player for inkling

        trigger = self._get_etb_trigger(game, card)
        trigger.effect(game)

        # Opponent has 3 creatures; controller now has 1 (the inkling) → prepared
        assert card.is_prepared is True

    def test_does_not_become_prepared_when_even_or_ahead(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        # Give controller a creature (after inkling creation p1 will have 2, p2 has 1)
        my_creature = Creature(name="Bear", base_power=2, base_toughness=2,
                               owner=p1, controller=p1)
        opp_creature = Creature(name="Goblin", base_power=1, base_toughness=1,
                                owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[my_creature])
        set_board_state(game, 1, battlefield=[opp_creature])

        card.register_triggers(game)
        p1._script.append(p1)

        trigger = self._get_etb_trigger(game, card)
        trigger.effect(game)

        # p1 has 2 creatures (my_creature + inkling), p2 has 1 → not prepared
        assert card.is_prepared is False


class TestEmeritusPreparation:
    """Prepared: cast a copy of Swords to Plowshares."""

    def test_cast_prepared_spell_exiles_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = True

        target = Creature(name="Dragon", base_power=5, base_toughness=5,
                          owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])

        card.cast_prepared_spell(game, target)

        # Target is exiled
        assert target in p2.zones[Zone.EXILE].get_all()
        assert not game.get_battlefield(p2).contains(target)

    def test_cast_prepared_spell_grants_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = True

        target = Creature(name="Dragon", base_power=5, base_toughness=5,
                          owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])

        card.cast_prepared_spell(game, target)
        # p2 (target's controller) gains life equal to power (5)
        assert p2.life == 25

    def test_cast_prepared_spell_unprepares(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = True

        target = Creature(name="Bear", base_power=2, base_toughness=2,
                          owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])
        card.cast_prepared_spell(game, target)

        assert card.is_prepared is False

    def test_cannot_use_prepared_when_not_prepared(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = False

        target = Creature(name="Bear", base_power=2, base_toughness=2,
                          owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])

        # Should be a no-op
        card.cast_prepared_spell(game, target)
        assert game.get_battlefield(p2).contains(target)

    def test_cannot_target_creature_not_on_battlefield(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = True

        # Target is in hand, not battlefield
        target = Creature(name="Bear", base_power=2, base_toughness=2,
                          owner=p2, controller=p2)
        set_board_state(game, 1, hand=[target])

        card.cast_prepared_spell(game, target)
        # No exile should occur since it's not on battlefield
        assert target in p2.zones[Zone.HAND].get_all()
