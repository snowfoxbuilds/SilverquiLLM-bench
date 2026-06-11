"""Tests for SOS 197 — Killian's Confidence."""

from __future__ import annotations

import pytest

from cards.sos.sos_197.card_impl import KilliansConfidence
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell, declare_attackers


class TestKilliansConfidenceProperties:
    """Static card data should match the SOS 197 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(KilliansConfidence(owner=None), Sorcery)

    def test_name(self) -> None:
        assert KilliansConfidence(owner=None).name == "Killian's Confidence"

    def test_mana_cost(self) -> None:
        assert KilliansConfidence(owner=None).mana_cost == ManaCost.parse("{W}{B}")


class TestKilliansConfidenceResolution:
    """First part: target creature gets +1/+1 and draw a card."""

    def test_target_gets_plus_one(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = KilliansConfidence(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.BLACK: 1})
        cast_spell(game, 0, "Killian's Confidence", targets=[bear])

        assert bear.power == 3
        assert bear.toughness == 3

    def test_draws_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        # Put a card in library to draw
        lib_card = Creature(name="Library Card", owner=p1, base_power=1, base_toughness=1)
        game.get_library(p1).add_top(lib_card)

        hand_size_before = len(game.get_hand(p1))
        spell = KilliansConfidence(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.BLACK: 1})
        cast_spell(game, 0, "Killian's Confidence", targets=[bear])

        # Should have drawn one card (net hand size change accounts for spell leaving)
        assert lib_card in game.get_hand(p1)

    def test_buff_is_until_end_of_turn(self) -> None:
        """The +1/+1 is until end of turn, not permanent."""
        game = create_game()
        p1 = game.players[0]

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = KilliansConfidence(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.BLACK: 1})
        cast_spell(game, 0, "Killian's Confidence", targets=[bear])

        game.end_turn()
        assert bear.power == 2
        assert bear.toughness == 2


class TestKilliansConfidenceGraveyardAbility:
    """Graveyard triggered ability: return to hand when creatures deal combat damage."""

    def test_returns_to_hand_on_combat_damage(self) -> None:
        """When creatures deal combat damage, pay {W/B} to return from graveyard."""
        game = create_game()
        p1 = game.players[0]

        spell = KilliansConfidence(owner=p1, controller=p1)
        game.get_graveyard(p1).add(spell)

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        declare_attackers(game, ["Grizzly Bears"])
        # Resolve combat damage to player
        game.resolve_combat()

        # After paying {W/B}, spell should return to hand
        assert spell in game.get_hand(p1)
        assert spell not in game.get_graveyard(p1)

    def test_stays_in_graveyard_if_no_payment(self) -> None:
        """If you choose not to pay, the card stays in graveyard."""
        game = create_game()
        p1 = game.players[0]

        spell = KilliansConfidence(owner=p1, controller=p1)
        game.get_graveyard(p1).add(spell)

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        # No mana available to pay
        set_board_state(game, 0, mana={})
        declare_attackers(game, ["Grizzly Bears"])
        game.resolve_combat()

        assert spell in game.get_graveyard(p1)

    def test_no_trigger_if_not_in_graveyard(self) -> None:
        """If the card is not in graveyard, the ability doesn't trigger."""
        game = create_game()
        p1 = game.players[0]

        spell = KilliansConfidence(owner=p1, controller=p1)
        # Card is in exile, not graveyard
        game.get_exile(p1).add(spell)

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        declare_attackers(game, ["Grizzly Bears"])
        game.resolve_combat()

        assert spell not in game.get_hand(p1)
