"""Tests for SOS 159 — Shopkeeper's Bane."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_159.card_impl import ShopkeepersBane
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestShopkeepersBaneProperties:
    """Static card data should match the SOS 159 spec."""

    def test_is_badger_pest_creature_with_trample(self) -> None:
        card = ShopkeepersBane(owner=None)

        assert isinstance(card, Creature)
        assert "Badger" in card.subtypes
        assert "Pest" in card.subtypes
        assert Keyword.TRAMPLE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = ShopkeepersBane(owner=None)

        assert card.name == "Shopkeeper's Bane"
        assert card.mana_cost == ManaCost.parse("{2}{G}")
        assert card.base_power == 4
        assert card.base_toughness == 2


class TestShopkeepersBaneAttackTrigger:
    """Shopkeeper's Bane should gain you life when it attacks."""

    def test_registers_an_attack_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ShopkeepersBane(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent

    def test_when_it_attacks_you_gain_two_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ShopkeepersBane(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )

        assert len(game.stack) == 1
        resolve_top(game)

        assert p1.life == 22

    def test_another_creature_attacking_does_not_trigger_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bane = ShopkeepersBane(owner=p1, controller=p1)
        other = Creature(
            name="Helpful Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[bane, other])
        bane.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=other, attacker=other),
        )

        assert game.stack.is_empty()
        assert p1.life == 20
