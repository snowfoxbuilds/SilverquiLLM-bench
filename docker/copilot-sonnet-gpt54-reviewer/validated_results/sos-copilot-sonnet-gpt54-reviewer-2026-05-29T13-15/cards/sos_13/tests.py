"""Tests for sos_13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestEmeritusProperties:
    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Emeritus of Truce" in card.name

    def test_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)

    def test_power_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_has_cat_subtype(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cat" in card.subtypes

    def test_has_cleric_subtype(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cleric" in card.subtypes

    def test_has_prepared_attribute(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert hasattr(card, "is_prepared")
        assert card.is_prepared is False


class TestEmeritusETBToken:
    """When creature enters, target player creates a 1/1 Inkling with flying."""

    def test_etb_creates_inkling_token(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # Script: choose p1 as target player for token
        p1._script.appendleft(p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        # Manually fire the ETB
        from engine.events import EntersBattlefieldTriggeredEvent
        game.trigger_manager.fire_event(
            game, EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        )
        # Resolve the trigger
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        # Check that a 1/1 token with flying exists on p1's battlefield
        bf = game.get_battlefield(p1).get_all()
        inklings = [
            c for c in bf
            if isinstance(c, Creature) and "Inkling" in getattr(c, "subtypes", set())
        ]
        assert len(inklings) >= 1
        inkling = inklings[0]
        assert inkling.base_power == 1
        assert inkling.base_toughness == 1
        assert Keyword.FLYING in inkling.keywords

    def test_etb_token_can_go_to_opponent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # Script: choose p2 as target player
        p1._script.appendleft(p2)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        from engine.events import EntersBattlefieldTriggeredEvent
        game.trigger_manager.fire_event(
            game, EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        bf2 = game.get_battlefield(p2).get_all()
        inklings = [c for c in bf2 if "Inkling" in getattr(c, "subtypes", set())]
        assert len(inklings) >= 1


class TestEmeritusPrepared:
    """Creature becomes prepared if opponent controls more creatures."""

    def _fire_etb(self, game, card, p1, target_player):
        p1._script.appendleft(target_player)
        card.register_triggers(game)
        from engine.events import EntersBattlefieldTriggeredEvent
        game.trigger_manager.fire_event(
            game, EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def test_not_prepared_when_opponent_has_fewer_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        # p1 has the Emeritus, p2 has nothing → opponent has fewer
        self._fire_etb(game, card, p1, p1)
        assert card.is_prepared is False

    def test_prepared_when_opponent_has_more_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        # Give p2 two creatures
        for i in range(2):
            c = Creature(name=f"Opp{i}", base_power=1, base_toughness=1)
            game.get_battlefield(p2).add(c)
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        # p1 has 1 creature (Emeritus), p2 has 2 → p2 has more
        self._fire_etb(game, card, p1, p1)
        assert card.is_prepared is True


class TestEmeritusSwordsToPlowshares:
    """Prepared ability: cast Swords to Plowshares copy (exile, gain life)."""

    def test_prepared_ability_exiles_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(bear)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = True
        game.get_battlefield(p1).add(card)

        # Script: choose bear as target
        p1._script.appendleft(bear)
        card.cast_prepared_ability(game)

        exile = p2.zones[Zone.EXILE]
        bf = game.get_battlefield(p2).get_all()
        assert exile.contains(bear)
        assert bear not in bf

    def test_prepared_ability_controller_gains_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=3, base_toughness=3, owner=p2, controller=p2)
        game.get_battlefield(p2).add(bear)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = True
        game.get_battlefield(p1).add(card)
        initial_life = p2.life

        p1._script.appendleft(bear)
        card.cast_prepared_ability(game)

        # The creature's controller (p2) gains life equal to bear's power (3)
        assert p2.life == initial_life + 3

    def test_becomes_unprepared_after_use(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(bear)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = True
        game.get_battlefield(p1).add(card)

        p1._script.appendleft(bear)
        card.cast_prepared_ability(game)

        assert card.is_prepared is False
