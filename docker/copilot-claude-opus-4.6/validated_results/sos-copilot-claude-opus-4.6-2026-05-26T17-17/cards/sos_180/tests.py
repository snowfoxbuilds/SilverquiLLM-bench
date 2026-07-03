"""Tests for SOS 180 — Colorstorm Stallion."""

from __future__ import annotations

import pytest

from cards.sos.sos_180.card_impl import ColorstormStallion
from engine.card import Creature, Sorcery, Instant
from engine.types import ManaCost, ManaType, Keyword
from test_utils import create_game, set_board_state, cast_spell


class TestColorstormStallionProperties:
    """Static card properties match spec."""

    def test_is_creature(self) -> None:
        assert isinstance(ColorstormStallion(owner=None), Creature)

    def test_name(self) -> None:
        assert ColorstormStallion(owner=None).name == "Colorstorm Stallion"

    def test_mana_cost(self) -> None:
        assert ColorstormStallion(owner=None).mana_cost == ManaCost.parse("{1}{U}{R}")

    def test_power_toughness(self) -> None:
        card = ColorstormStallion(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_has_haste(self) -> None:
        card = ColorstormStallion(owner=None)
        assert Keyword.HASTE in card.keywords

    def test_has_ward(self) -> None:
        card = ColorstormStallion(owner=None)
        assert Keyword.WARD in card.keywords


class TestColorstormStallionOpusTrigger:
    """
    Whenever you cast an instant or sorcery spell, this gets +1/+1 until end of turn.
    If 5+ mana was spent, create a token copy of this creature.
    """

    def test_casting_instant_gives_plus_one(self) -> None:
        game = create_game()
        stallion = ColorstormStallion(owner=game.players[0])
        set_board_state(game, 0, battlefield=[stallion])
        # Create a cheap instant to cast
        bolt = Instant(name="Test Bolt", mana_cost=ManaCost.parse("{R}"))
        bolt.owner = game.players[0]
        set_board_state(game, 0, hand=[bolt],
                        mana={ManaType.RED: 1})
        cast_spell(game, 0, "Test Bolt")
        # Stallion should be 4/4 until end of turn
        assert stallion.power == 4
        assert stallion.toughness == 4

    def test_casting_sorcery_gives_plus_one(self) -> None:
        game = create_game()
        stallion = ColorstormStallion(owner=game.players[0])
        set_board_state(game, 0, battlefield=[stallion])
        sorc = Sorcery(name="Test Sorcery", mana_cost=ManaCost.parse("{1}{U}"))
        sorc.owner = game.players[0]
        set_board_state(game, 0, hand=[sorc],
                        mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Test Sorcery")
        assert stallion.power == 4
        assert stallion.toughness == 4

    def test_five_mana_spell_creates_token_copy(self) -> None:
        game = create_game()
        stallion = ColorstormStallion(owner=game.players[0])
        set_board_state(game, 0, battlefield=[stallion])
        # Cast a spell costing 5+ mana
        big_spell = Sorcery(name="Big Spell", mana_cost=ManaCost.parse("{3}{U}{R}"))
        big_spell.owner = game.players[0]
        set_board_state(game, 0, hand=[big_spell],
                        mana={ManaType.BLUE: 1, ManaType.RED: 1, ManaType.COLORLESS: 3})
        cast_spell(game, 0, "Big Spell")
        # Should have stallion + a token copy on battlefield
        stallions_on_bf = [c for c in game.players[0].battlefield
                          if c.name == "Colorstorm Stallion"]
        assert len(stallions_on_bf) >= 2

    def test_four_mana_spell_does_not_create_token(self) -> None:
        game = create_game()
        stallion = ColorstormStallion(owner=game.players[0])
        set_board_state(game, 0, battlefield=[stallion])
        medium_spell = Sorcery(name="Medium Spell", mana_cost=ManaCost.parse("{2}{U}{R}"))
        medium_spell.owner = game.players[0]
        set_board_state(game, 0, hand=[medium_spell],
                        mana={ManaType.BLUE: 1, ManaType.RED: 1, ManaType.COLORLESS: 2})
        # 4 mana total — under threshold
        cast_spell(game, 0, "Medium Spell")
        stallions_on_bf = [c for c in game.players[0].battlefield
                          if c.name == "Colorstorm Stallion"]
        assert len(stallions_on_bf) == 1  # no copy created

    def test_multiple_spells_stack_bonus(self) -> None:
        game = create_game()
        stallion = ColorstormStallion(owner=game.players[0])
        set_board_state(game, 0, battlefield=[stallion])
        bolt1 = Instant(name="Bolt A", mana_cost=ManaCost.parse("{R}"))
        bolt1.owner = game.players[0]
        bolt2 = Instant(name="Bolt B", mana_cost=ManaCost.parse("{R}"))
        bolt2.owner = game.players[0]
        set_board_state(game, 0, hand=[bolt1, bolt2],
                        mana={ManaType.RED: 2})
        cast_spell(game, 0, "Bolt A")
        cast_spell(game, 0, "Bolt B")
        # Should be +2/+2 total => 5/5
        assert stallion.power == 5
        assert stallion.toughness == 5

    def test_bonus_wears_off_at_end_of_turn(self) -> None:
        game = create_game()
        stallion = ColorstormStallion(owner=game.players[0])
        set_board_state(game, 0, battlefield=[stallion])
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        bolt.owner = game.players[0]
        set_board_state(game, 0, hand=[bolt], mana={ManaType.RED: 1})
        cast_spell(game, 0, "Bolt")
        assert stallion.power == 4
        # End the turn
        from test_utils import advance_to_phase
        from engine.types import Phase, Step
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        assert stallion.power == 3
        assert stallion.toughness == 3
