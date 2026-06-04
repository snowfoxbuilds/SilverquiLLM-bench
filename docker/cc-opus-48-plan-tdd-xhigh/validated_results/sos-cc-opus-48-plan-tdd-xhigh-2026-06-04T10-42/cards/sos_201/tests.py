"""Tests for SOS 201 — Lorehold, the Historian (loot + miracle {2})."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import CardImpl, Creature, Instant
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import _resolve_top_of_stack, create_game, set_board_state


class _LifeGain(Instant):
    """Expensive instant ({5}) that gains 3 life — cheap to cast via miracle."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Insight")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 3


def _filler(name: str, owner: Any) -> CardImpl:
    c = CardImpl(name=name)
    c.owner = owner
    c.controller = owner
    return c


class TestLoreholdProperties:
    def test_is_creature(self) -> None:
        assert isinstance(LoreholdTheHistorian(owner=None), Creature)

    def test_name(self) -> None:
        assert (
            LoreholdTheHistorian(owner=None).name == "Lorehold, the Historian"
        )

    def test_mana_cost(self) -> None:
        assert LoreholdTheHistorian(owner=None).mana_cost == ManaCost.parse(
            "{3}{R}{W}"
        )

    def test_pt(self) -> None:
        c = LoreholdTheHistorian(owner=None)
        assert c.base_power == 5
        assert c.base_toughness == 5

    def test_keywords(self) -> None:
        c = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in c.keywords
        assert Keyword.HASTE in c.keywords

    def test_legendary_dragon(self) -> None:
        c = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in c.supertypes
        assert "Dragon" in c.subtypes
        assert "Elder" in c.subtypes


class TestLoreholdLoot:
    def test_loot_on_opponent_upkeep(self) -> None:
        game = create_game()
        p0, p1 = game.players
        lorehold = LoreholdTheHistorian(owner=p0, controller=p0)
        discard_me = _filler("Discard", p0)
        set_board_state(game, 0, battlefield=[lorehold], hand=[discard_me])
        lib_card = _filler("Drawn", p0)
        p0.zones[Zone.LIBRARY].add(lib_card)
        lorehold.register_triggers(game)

        game.active_player_index = 1  # opponent's turn
        p0._script.extend([True, discard_me])

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_top_of_stack(game)

        assert game.get_graveyard(p0).contains(discard_me)
        assert game.get_hand(p0).contains(lib_card)

    def test_loot_declined(self) -> None:
        game = create_game()
        p0, p1 = game.players
        lorehold = LoreholdTheHistorian(owner=p0, controller=p0)
        keep = _filler("Keep", p0)
        set_board_state(game, 0, battlefield=[lorehold], hand=[keep])
        lorehold.register_triggers(game)

        game.active_player_index = 1
        p0._script.append(False)

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_top_of_stack(game)

        assert game.get_hand(p0).contains(keep)
        assert not game.get_graveyard(p0).contains(keep)

    def test_no_loot_on_own_upkeep(self) -> None:
        game = create_game()
        p0, p1 = game.players
        lorehold = LoreholdTheHistorian(owner=p0, controller=p0)
        keep = _filler("Keep", p0)
        set_board_state(game, 0, battlefield=[lorehold], hand=[keep])
        lorehold.register_triggers(game)

        game.active_player_index = 0  # Lorehold's controller's own upkeep
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_top_of_stack(game)

        # No trigger fired → nothing discarded, hand untouched.
        assert game.get_hand(p0).contains(keep)


class TestLoreholdMiracle:
    def _setup(self, scripts: list[Any]) -> tuple[Any, Any, Any]:
        game = create_game(scripts=(scripts, []))
        p0, _ = game.players
        lorehold = LoreholdTheHistorian(owner=p0, controller=p0)
        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            life=20,
            mana={ManaType.COLORLESS: 2},
        )
        lorehold.register_triggers(game)
        p0.cards_drawn_this_turn = 0
        return game, p0, lorehold

    def test_miracle_cast_first_draw(self) -> None:
        game, p0, _ = self._setup([True])
        spell = _LifeGain(owner=p0, controller=p0)
        p0.zones[Zone.LIBRARY].add(spell)

        drawn = draw_card(game, p0)
        assert drawn is spell
        _resolve_top_of_stack(game)

        assert p0.life == 23  # gained 3 from the miracle-cast spell
        assert p0.mana_pool.total() == 0  # paid {2}
        assert game.get_graveyard(p0).contains(spell)

    def test_miracle_declined_keeps_card(self) -> None:
        game, p0, _ = self._setup([False])
        spell = _LifeGain(owner=p0, controller=p0)
        p0.zones[Zone.LIBRARY].add(spell)

        draw_card(game, p0)
        _resolve_top_of_stack(game)

        assert p0.life == 20
        assert game.get_hand(p0).contains(spell)
        assert p0.mana_pool.total() == 2  # nothing spent

    def test_miracle_only_first_card(self) -> None:
        game, p0, _ = self._setup([True])
        spell = _LifeGain(owner=p0, controller=p0)
        p0.zones[Zone.LIBRARY].add(spell)
        # Pretend a card was already drawn this turn → this is the 2nd draw.
        p0.cards_drawn_this_turn = 1

        draw_card(game, p0)
        _resolve_top_of_stack(game)

        assert p0.life == 20
        assert game.get_hand(p0).contains(spell)

    def test_miracle_only_instant_or_sorcery(self) -> None:
        game, p0, _ = self._setup([True])
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        creature.owner = p0
        creature.controller = p0
        p0.zones[Zone.LIBRARY].add(creature)

        draw_card(game, p0)
        _resolve_top_of_stack(game)

        # Not an I/S → no miracle trigger; card stays in hand, mana intact.
        assert game.get_hand(p0).contains(creature)
        assert p0.mana_pool.total() == 2
