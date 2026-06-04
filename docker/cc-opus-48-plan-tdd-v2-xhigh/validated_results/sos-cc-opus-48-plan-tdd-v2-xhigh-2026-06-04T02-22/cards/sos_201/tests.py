"""Tests for SOS 201 — Lorehold, the Historian (Miracle grant + loot)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state, _resolve_top_of_stack


class _LifeBolt(Instant):
    """Instant that gains its controller 3 life on resolve (no targets)."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Life Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))  # mv 5
        super().__init__(**kwargs)
        self.resolved = False

    def on_resolve(self, game: Any) -> None:
        self.resolved = True
        if self.controller is not None:
            self.controller.life += 3


def _put_on_top(player: Any, card: Any) -> None:
    card.owner = player
    card.controller = player
    player.zones[Zone.LIBRARY].add(card)  # top of library


class TestProperties:
    def test_is_creature(self) -> None:
        c = LoreholdTheHistorian(owner=None)
        assert isinstance(c, Creature)

    def test_name_cost_pt(self) -> None:
        c = LoreholdTheHistorian(owner=None)
        assert c.name == "Lorehold, the Historian"
        assert c.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert c.base_power == 5
        assert c.base_toughness == 5

    def test_keywords_and_types(self) -> None:
        c = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in c.keywords
        assert Keyword.HASTE in c.keywords
        assert Supertype.LEGENDARY in c.supertypes
        assert {"Elder", "Dragon"} <= c.subtypes


class TestMiracleGrant:
    def test_first_drawn_instant_castable_for_two(self) -> None:
        from engine.game import draw_card

        game = create_game()
        p1, _p2 = game.players
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold],
                        mana={ManaType.COLORLESS: 2}, life=20)
        lorehold.register_triggers(game)
        p1.cards_drawn_this_turn = 0
        bolt = _LifeBolt(owner=p1)
        _put_on_top(p1, bolt)
        p1._script.append(True)  # accept the miracle cast

        draw_card(game, p1)            # first draw of the turn
        _resolve_top_of_stack(game)    # miracle trigger -> cast -> resolve

        assert bolt.resolved is True
        assert bolt in p1.zones[Zone.GRAVEYARD].get_all()
        assert p1.mana_pool.total() == 0   # {2} spent
        assert p1.life == 23               # gained 3 from the bolt

    def test_decline_leaves_card_in_hand(self) -> None:
        from engine.game import draw_card

        game = create_game()
        p1, _p2 = game.players
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold],
                        mana={ManaType.COLORLESS: 2})
        lorehold.register_triggers(game)
        p1.cards_drawn_this_turn = 0
        bolt = _LifeBolt(owner=p1)
        _put_on_top(p1, bolt)
        p1._script.append(False)  # decline the miracle

        draw_card(game, p1)
        _resolve_top_of_stack(game)

        assert bolt.resolved is False
        assert bolt in p1.zones[Zone.HAND].get_all()
        assert p1.mana_pool.total() == 2

    def test_not_offered_on_second_draw(self) -> None:
        from engine.game import draw_card

        game = create_game()
        p1, _p2 = game.players
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold],
                        mana={ManaType.COLORLESS: 2})
        lorehold.register_triggers(game)
        p1.cards_drawn_this_turn = 1  # already drew once this turn
        bolt = _LifeBolt(owner=p1)
        _put_on_top(p1, bolt)

        draw_card(game, p1)            # this is the 2nd draw
        _resolve_top_of_stack(game)

        assert bolt.resolved is False
        assert bolt in p1.zones[Zone.HAND].get_all()

    def test_not_offered_for_noncast_card(self) -> None:
        from engine.game import draw_card

        game = create_game()
        p1, _p2 = game.players
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold],
                        mana={ManaType.COLORLESS: 2})
        lorehold.register_triggers(game)
        p1.cards_drawn_this_turn = 0
        creature = Creature(name="Bear", owner=p1, controller=p1,
                            base_power=2, base_toughness=2,
                            mana_cost=ManaCost.parse("{1}{G}"))
        creature.card_types = {CardType.CREATURE}
        _put_on_top(p1, creature)

        draw_card(game, p1)
        _resolve_top_of_stack(game)

        assert creature in p1.zones[Zone.HAND].get_all()


def _bear(name: str, owner: Any) -> Creature:
    c = Creature(name=name, owner=owner, controller=owner,
                 base_power=2, base_toughness=2,
                 mana_cost=ManaCost.parse("{1}{G}"))
    c.card_types = {CardType.CREATURE}
    return c


def _fire_upkeep(game: Any, active: Any) -> None:
    from engine.events import BeginningOfUpkeepTriggeredEvent

    game.active_player_index = game.players.index(active)
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    _resolve_top_of_stack(game)


class TestOpponentUpkeepLoot:
    def test_discard_then_draw_on_opponent_upkeep(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        discard_me = _bear("Discard", p1)
        set_board_state(game, 0, battlefield=[lorehold], hand=[discard_me])
        lorehold.register_triggers(game)
        p1.cards_drawn_this_turn = 0
        drawn = _bear("Drawn", p1)
        _put_on_top(p1, drawn)
        p1._script.extend([True, discard_me])  # yes, discard this card

        _fire_upkeep(game, p2)  # opponent's upkeep

        assert discard_me in p1.zones[Zone.GRAVEYARD].get_all()
        assert drawn in p1.zones[Zone.HAND].get_all()

    def test_not_on_your_own_upkeep(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        keep = _bear("Keep", p1)
        set_board_state(game, 0, battlefield=[lorehold], hand=[keep])
        lorehold.register_triggers(game)
        drawn = _bear("Drawn", p1)
        _put_on_top(p1, drawn)

        _fire_upkeep(game, p1)  # your own upkeep — loot must not fire

        assert keep in p1.zones[Zone.HAND].get_all()
        assert drawn in p1.zones[Zone.LIBRARY].get_all()

    def test_may_decline_loot(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        keep = _bear("Keep", p1)
        set_board_state(game, 0, battlefield=[lorehold], hand=[keep])
        lorehold.register_triggers(game)
        drawn = _bear("Drawn", p1)
        _put_on_top(p1, drawn)
        p1._script.append(False)  # decline

        _fire_upkeep(game, p2)

        assert keep in p1.zones[Zone.HAND].get_all()
        assert drawn in p1.zones[Zone.LIBRARY].get_all()
