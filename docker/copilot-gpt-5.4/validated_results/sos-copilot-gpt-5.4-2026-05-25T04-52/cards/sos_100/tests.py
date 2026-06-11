"""Tests for SOS 100 — Send in the Pest."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_100.card_impl import SendInThePest
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestSendInThePestProperties:
    """Static card data should match the SOS 100 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(SendInThePest(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = SendInThePest(owner=None)
        assert card.name == "Send in the Pest"
        assert card.mana_cost == ManaCost.parse("{1}{B}")


class TestSendInThePestResolution:
    """Send in the Pest should discard and create the printed Pest token."""

    def test_each_opponent_discards_a_card_and_you_create_a_black_and_green_pest_token(self) -> None:
        game = create_game()
        p1, p2 = game.players
        discarded = CardImpl(name="Discarded Notes", owner=p2, controller=p2)
        set_board_state(game, 1, hand=[discarded])
        p2._script.append(discarded)

        SendInThePest(owner=p1, controller=p1).on_resolve(game)

        assert game.get_graveyard(p2).contains(discarded)
        assert game.get_hand(p2).get_all() == []

        tokens = [
            permanent
            for permanent in game.get_battlefield(p1).get_all()
            if getattr(permanent, "is_token", False)
        ]
        assert len(tokens) == 1

        token = tokens[0]
        assert isinstance(token, Creature)
        assert token.power == 1
        assert token.toughness == 1
        assert "Pest" in token.subtypes
        assert get_colors(token) == {Color.BLACK, Color.GREEN}

    def test_created_pest_token_gains_you_one_life_when_it_attacks(self) -> None:
        game = create_game()
        p1 = game.players[0]

        SendInThePest(owner=p1, controller=p1).on_resolve(game)

        token = next(
            permanent
            for permanent in game.get_battlefield(p1).get_all()
            if getattr(permanent, "is_token", False)
        )

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=token, attacker=token),
        )

        assert len(game.stack) == 1

        resolve_top(game)

        assert p1.life == 21

    def test_opponent_with_no_cards_still_gets_no_discard_and_you_still_create_the_token(self) -> None:
        game = create_game()
        p1, p2 = game.players

        SendInThePest(owner=p1, controller=p1).on_resolve(game)

        assert game.get_hand(p2).get_all() == []
        assert len(game.get_battlefield(p1).get_all()) == 1
