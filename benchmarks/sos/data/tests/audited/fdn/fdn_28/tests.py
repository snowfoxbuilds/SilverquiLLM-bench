"""Audited tests for FDN 28 — Vanguard Seraph."""
from __future__ import annotations
from card_impl import VanguardSeraph
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game
from engine.events import GainsLifeTriggeredEvent

class TestVanguardSeraphBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = VanguardSeraph(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = VanguardSeraph(owner=None)
        assert card.name == 'Vanguard Seraph'

    def test_mana_cost(self) -> None:
        card = VanguardSeraph(owner=None)
        assert card.mana_cost == ManaCost.parse('{3}{W}')

    def test_power_toughness(self) -> None:
        card = VanguardSeraph(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        card = VanguardSeraph(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_subtypes(self) -> None:
        card = VanguardSeraph(owner=None)
        assert 'Angel' in card.subtypes
        assert 'Warrior' in card.subtypes

class TestVanguardSeraphSurveil:
    """First life gain each turn triggers surveil 1."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        seraph = VanguardSeraph(owner=p1, controller=p1)
        game.get_battlefield(p1).add(seraph)
        seraph.register_triggers(game)
        top_card = Creature(name='TopCard', base_power=1, base_toughness=1, owner=p1, controller=p1)
        p1.zones[Zone.LIBRARY].add(top_card)
        return (game, p1, seraph, top_card)

    def test_first_life_gain_triggers_surveil(self) -> None:
        game, p1, seraph, top_card = self._setup()
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(True)
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=2))
        self._resolve_stack(game)
        assert p1.zones[Zone.GRAVEYARD].contains(top_card)

    def test_surveil_keep_on_top(self) -> None:
        game, p1, seraph, top_card = self._setup()
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(False)
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=2))
        self._resolve_stack(game)
        assert p1.zones[Zone.LIBRARY].contains(top_card)
        assert not p1.zones[Zone.GRAVEYARD].contains(top_card)

    def test_second_life_gain_same_turn_no_surveil(self) -> None:
        game, p1, seraph, top_card = self._setup()
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(False)
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=2))
        self._resolve_stack(game)
        second_card = Creature(name='SecondCard', base_power=1, base_toughness=1, owner=p1, controller=p1)
        p1.zones[Zone.LIBRARY].add(second_card)
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=1))
        self._resolve_stack(game)
        assert p1.zones[Zone.LIBRARY].contains(second_card)

    def test_opponent_life_gain_does_not_trigger(self) -> None:
        game, p1, seraph, top_card = self._setup()
        p2 = game.players[1]
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p2, amount=3))
        self._resolve_stack(game)
        assert p1.zones[Zone.LIBRARY].contains(top_card)
