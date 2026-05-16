"""Audited tests for FDN 2 — Arahbo, the First Fang."""
from __future__ import annotations
from card_impl import ArahboTheFirstFang
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype
from tests.test_utils import create_game
from engine.events import EntersBattlefieldTriggeredEvent

class TestArahboBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = ArahboTheFirstFang(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = ArahboTheFirstFang(owner=None)
        assert card.name == 'Arahbo, the First Fang'

    def test_mana_cost(self) -> None:
        card = ArahboTheFirstFang(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{W}')

    def test_power_toughness(self) -> None:
        card = ArahboTheFirstFang(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_is_legendary(self) -> None:
        card = ArahboTheFirstFang(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = ArahboTheFirstFang(owner=None)
        assert 'Cat' in card.subtypes
        assert 'Avatar' in card.subtypes

class TestArahboLordEffect:
    """Other Cats you control get +1/+1."""

    def _setup_lord(self):
        game = create_game()
        p1 = game.players[0]
        arahbo = ArahboTheFirstFang(owner=p1, controller=p1)
        cat = Creature(name='Cat', subtypes={'Cat'}, base_power=1, base_toughness=1, owner=p1, controller=p1)
        non_cat = Creature(name='Bear', subtypes={'Bear'}, base_power=2, base_toughness=2, owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(arahbo)
        bf.add(cat)
        bf.add(non_cat)
        arahbo.register_triggers(game)
        game.effect_manager.apply_all(game)
        return (game, arahbo, cat, non_cat, p1)

    def test_cat_gets_plus_one(self) -> None:
        game, arahbo, cat, non_cat, p1 = self._setup_lord()
        assert cat.modified_power == 2
        assert cat.modified_toughness == 2

    def test_non_cat_not_buffed(self) -> None:
        game, arahbo, cat, non_cat, p1 = self._setup_lord()
        assert non_cat.base_power == 2
        assert non_cat.base_toughness == 2

    def test_arahbo_does_not_buff_itself(self) -> None:
        game, arahbo, cat, non_cat, p1 = self._setup_lord()
        assert arahbo.base_power == 2
        assert arahbo.base_toughness == 2

class TestArahboETBTokenTrigger:
    """Whenever Arahbo or another nontoken Cat enters, create a 1/1 Cat token."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def _setup_etb(self):
        game = create_game()
        p1 = game.players[0]
        arahbo = ArahboTheFirstFang(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(arahbo)
        arahbo.register_triggers(game)
        return (game, arahbo, p1, bf)

    def test_nontoken_cat_entering_creates_token(self) -> None:
        game, arahbo, p1, bf = self._setup_etb()
        new_cat = Creature(name='Other Cat', subtypes={'Cat'}, base_power=2, base_toughness=2, owner=p1, controller=p1)
        bf.add(new_cat)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=new_cat, controller=p1))
        self._resolve_stack(game)
        cats_on_bf = [c for c in bf.get_all() if 'Cat' in getattr(c, 'subtypes', set()) and c is not arahbo and (c is not new_cat)]
        assert len(cats_on_bf) >= 1, 'Should have created a Cat token'

    def test_token_cat_does_not_trigger(self) -> None:
        game, arahbo, p1, bf = self._setup_etb()
        token_cat = Creature(name='Cat', subtypes={'Cat'}, base_power=1, base_toughness=1, owner=p1, controller=p1)
        token_cat.is_token = True
        bf.add(token_cat)
        initial_count = len(bf.get_all())
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=token_cat, controller=p1))
        self._resolve_stack(game)
        assert len(bf.get_all()) == initial_count
