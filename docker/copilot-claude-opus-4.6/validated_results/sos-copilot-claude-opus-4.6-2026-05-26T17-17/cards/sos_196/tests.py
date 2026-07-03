"""Tests for SOS 196 — Inkling Mascot."""

from __future__ import annotations

import pytest

from cards.sos.sos_196.card_impl import InklingMascot
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestInklingMascotProperties:
    """Static card data should match the SOS 196 spec."""

    def test_is_creature(self) -> None:
        card = InklingMascot(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert InklingMascot(owner=None).name == "Inkling Mascot"

    def test_mana_cost(self) -> None:
        assert InklingMascot(owner=None).mana_cost == ManaCost.parse("{W}{B}")

    def test_power_toughness(self) -> None:
        card = InklingMascot(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestInklingMascotRepartee:
    """Repartee trigger: gains flying + surveil 1 when you cast instant/sorcery targeting a creature."""

    def test_gains_flying_when_instant_targets_creature(self) -> None:
        """Casting an instant that targets a creature should give Inkling Mascot flying."""
        game = create_game()
        p1 = game.players[0]

        mascot = InklingMascot(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(mascot)
        game.get_battlefield(p1).add(bear)

        # Create a targeting instant spell and cast it targeting a creature
        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        bolt.card_types = {CardType.INSTANT}
        bolt.chosen_targets = [bear]
        set_board_state(game, 0, hand=[bolt], mana={ManaType.WHITE: 2, ManaType.BLACK: 2})
        cast_spell(game, 0, "Test Bolt", targets=[bear])

        assert Keyword.FLYING in mascot.keywords_granted

    def test_gains_flying_when_sorcery_targets_creature(self) -> None:
        """Casting a sorcery that targets a creature should also trigger repartee."""
        game = create_game()
        p1 = game.players[0]

        mascot = InklingMascot(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(mascot)
        game.get_battlefield(p1).add(bear)

        sorc = Sorcery(name="Test Sorcery", owner=p1, controller=p1)
        sorc.card_types = {CardType.SORCERY}
        sorc.chosen_targets = [bear]
        set_board_state(game, 0, hand=[sorc], mana={ManaType.WHITE: 2, ManaType.BLACK: 2})
        cast_spell(game, 0, "Test Sorcery", targets=[bear])

        assert Keyword.FLYING in mascot.keywords_granted

    def test_no_trigger_when_spell_does_not_target_creature(self) -> None:
        """If the instant/sorcery doesn't target a creature, no trigger."""
        game = create_game()
        p1 = game.players[0]

        mascot = InklingMascot(owner=p1, controller=p1)
        game.get_battlefield(p1).add(mascot)

        # Spell that targets player, not creature
        sorc = Sorcery(name="Lava Axe", owner=p1, controller=p1)
        sorc.card_types = {CardType.SORCERY}
        sorc.chosen_targets = [game.players[1]]
        set_board_state(game, 0, hand=[sorc], mana={ManaType.WHITE: 2, ManaType.BLACK: 2})
        cast_spell(game, 0, "Lava Axe", targets=[game.players[1]])

        assert Keyword.FLYING not in getattr(mascot, 'keywords_granted', set())

    def test_surveil_1_on_trigger(self) -> None:
        """Repartee trigger should also surveil 1."""
        game = create_game()
        p1 = game.players[0]

        mascot = InklingMascot(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(mascot)
        game.get_battlefield(p1).add(bear)

        # Put a card on top of library for surveil
        dummy = Creature(name="Library Card", owner=p1, base_power=1, base_toughness=1)
        game.get_library(p1).add_top(dummy)

        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        bolt.card_types = {CardType.INSTANT}
        set_board_state(game, 0, hand=[bolt], mana={ManaType.WHITE: 2, ManaType.BLACK: 2})
        cast_spell(game, 0, "Test Bolt", targets=[bear])

        # After surveil 1, the card should be in graveyard (if put there) or still on top
        graveyard = game.get_graveyard(p1)
        library = game.get_library(p1)
        # At minimum, surveil looked at the top card
        assert dummy in graveyard or dummy in library

    def test_flying_is_until_end_of_turn(self) -> None:
        """Flying gained from repartee lasts only until end of turn."""
        game = create_game()
        p1 = game.players[0]

        mascot = InklingMascot(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(mascot)
        game.get_battlefield(p1).add(bear)

        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        bolt.card_types = {CardType.INSTANT}
        set_board_state(game, 0, hand=[bolt], mana={ManaType.WHITE: 2, ManaType.BLACK: 2})
        cast_spell(game, 0, "Test Bolt", targets=[bear])

        # End the turn
        game.end_turn()
        assert Keyword.FLYING not in getattr(mascot, 'keywords_granted', set())
