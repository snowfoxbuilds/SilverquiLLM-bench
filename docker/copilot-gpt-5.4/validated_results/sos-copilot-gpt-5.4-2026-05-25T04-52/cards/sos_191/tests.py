"""Tests for SOS 191 — Geometer's Arthropod."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_191.card_impl import GeometersArthropod
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class XTestSorcery(Sorcery):
    """Simple X-cost sorcery used to exercise the spell-cast trigger."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Variable Formula")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{U}"))
        super().__init__(**kwargs)
        self.x_value = 0


class OrdinarySorcery(Sorcery):
    """Simple non-X sorcery used to prove the trigger is specific."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Ordinary Formula")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        super().__init__(**kwargs)


class TestGeometersArthropodProperties:
    """Static card data should match the SOS 191 spec."""

    def test_is_fractal_crab_creature(self) -> None:
        card = GeometersArthropod(owner=None)

        assert isinstance(card, Creature)
        assert "Fractal" in card.subtypes
        assert "Crab" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = GeometersArthropod(owner=None)

        assert card.name == "Geometer's Arthropod"
        assert card.mana_cost == ManaCost.parse("{G}{U}")
        assert card.base_power == 1
        assert card.base_toughness == 4


class TestGeometersArthropodXSpellTrigger:
    """Geometer's Arthropod should reward you for casting X spells."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GeometersArthropod(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_an_x_spell_looks_at_x_cards_puts_one_into_hand_and_puts_the_rest_on_the_bottom(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = GeometersArthropod(owner=p1, controller=p1)
        spell = XTestSorcery(owner=p1, controller=p1)
        spell.x_value = 3
        deeper = CardImpl(name="Deeper Notes", owner=p1, controller=p1)
        first = CardImpl(name="First Formula", owner=p1, controller=p1)
        second = CardImpl(name="Second Formula", owner=p1, controller=p1)
        third = CardImpl(name="Third Formula", owner=p1, controller=p1)
        game.get_library(p1).add(deeper)
        game.get_library(p1).add(first)
        game.get_library(p1).add(second)
        game.get_library(p1).add(third)
        game.queue_bottom_order(third, first)
        p1._script.append(second)
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.BLUE: 1, ManaType.COLORLESS: 3},
        )
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert game.get_hand(p1).contains(second)
        assert not game.get_library(p1).contains(second)
        assert len(game.look_history) == 1
        assert game.look_history[-1].cards == [first, second, third]
        assert game.look_history[-1].source is card
        assert game.look_history[-1].reason == "Geometer's Arthropod"
        assert len(game.bottom_order_history) == 1
        assert game.bottom_order_history[-1].cards == [first, third]
        assert game.bottom_order_history[-1].ordered_cards == [third, first]
        assert game.bottom_order_history[-1].source is card
        assert game.bottom_order_history[-1].used_queued_order is True
        assert game.get_library(p1).get_all() == [third, first, deeper]
        assert len(game.stack) == 1
        assert game.stack.peek().source is spell

    def test_casting_a_spell_without_x_in_its_mana_cost_does_not_trigger_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = GeometersArthropod(owner=p1, controller=p1)
        spell = OrdinarySorcery(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1},
        )
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        assert game.look_history == []
        assert game.bottom_order_history == []
