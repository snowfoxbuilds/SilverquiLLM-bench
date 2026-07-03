"""Tests for SOS 17 — Group Project.

Group Project is a {1}{W} Sorcery:
"Create a 2/2 red and white Spirit creature token.
Flashback—Tap three untapped creatures you control."
"""

from __future__ import annotations

import pytest
from cards.sos.sos_17.card_impl import GroupProject
from engine.card import Creature
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestGroupProjectProperties:
    """Static card data should match the SOS 17 spec."""

    def test_name(self) -> None:
        assert GroupProject(owner=None).name == "Group Project"

    def test_mana_cost(self) -> None:
        assert GroupProject(owner=None).mana_cost == ManaCost.parse("{1}{W}")

    def test_card_type_is_sorcery(self) -> None:
        card = GroupProject(owner=None)
        assert CardType.SORCERY in card.card_types


class TestGroupProjectResolution:
    """On resolution, creates a 2/2 red and white Spirit token."""

    def test_creates_spirit_token(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = GroupProject(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Group Project")

        battlefield = game.get_battlefield(p1).get_all()
        spirits = [c for c in battlefield if isinstance(c, Creature)
                   and "Spirit" in getattr(c, "subtypes", set())]
        assert len(spirits) == 1

    def test_spirit_token_is_2_2(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = GroupProject(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Group Project")

        battlefield = game.get_battlefield(p1).get_all()
        spirits = [c for c in battlefield if isinstance(c, Creature)
                   and "Spirit" in getattr(c, "subtypes", set())]
        assert spirits[0].base_power == 2
        assert spirits[0].base_toughness == 2

    def test_spirit_token_is_red_and_white(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = GroupProject(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Group Project")

        battlefield = game.get_battlefield(p1).get_all()
        spirits = [c for c in battlefield if isinstance(c, Creature)
                   and "Spirit" in getattr(c, "subtypes", set())]
        token = spirits[0]
        assert "W" in token.colors or "white" in str(token.colors).lower()
        assert "R" in token.colors or "red" in str(token.colors).lower()


class TestGroupProjectFlashback:
    """Flashback cost is tapping three untapped creatures you control."""

    def test_can_cast_from_graveyard_with_flashback(self) -> None:
        """With three untapped creatures, Group Project can be cast from graveyard."""
        game = create_game()
        p1 = game.players[0]

        card = GroupProject(owner=p1, controller=p1)
        c1 = Creature(name="Creature A", owner=p1, controller=p1, base_power=1, base_toughness=1)
        c2 = Creature(name="Creature B", owner=p1, controller=p1, base_power=1, base_toughness=1)
        c3 = Creature(name="Creature C", owner=p1, controller=p1, base_power=1, base_toughness=1)
        for c in [c1, c2, c3]:
            c.card_types = {CardType.CREATURE}
            c.is_tapped = False

        set_board_state(game, 0, graveyard=[card], battlefield=[c1, c2, c3])
        cast_spell(game, 0, "Group Project")  # from graveyard via flashback

        # After flashback, creatures should be tapped
        assert c1.is_tapped is True
        assert c2.is_tapped is True
        assert c3.is_tapped is True

    def test_flashback_exiles_after_resolution(self) -> None:
        """After flashback resolves, the card is exiled, not returned to graveyard."""
        game = create_game()
        p1 = game.players[0]

        card = GroupProject(owner=p1, controller=p1)
        c1 = Creature(name="Creature A", owner=p1, controller=p1, base_power=1, base_toughness=1)
        c2 = Creature(name="Creature B", owner=p1, controller=p1, base_power=1, base_toughness=1)
        c3 = Creature(name="Creature C", owner=p1, controller=p1, base_power=1, base_toughness=1)
        for c in [c1, c2, c3]:
            c.card_types = {CardType.CREATURE}
            c.is_tapped = False

        set_board_state(game, 0, graveyard=[card], battlefield=[c1, c2, c3])
        cast_spell(game, 0, "Group Project")

        # Card should be exiled
        graveyard_cards = game.get_graveyard(p1).get_all()
        assert card not in graveyard_cards

    def test_flashback_still_creates_token(self) -> None:
        """Flashback still produces the 2/2 Spirit token."""
        game = create_game()
        p1 = game.players[0]

        card = GroupProject(owner=p1, controller=p1)
        c1 = Creature(name="Creature A", owner=p1, controller=p1, base_power=1, base_toughness=1)
        c2 = Creature(name="Creature B", owner=p1, controller=p1, base_power=1, base_toughness=1)
        c3 = Creature(name="Creature C", owner=p1, controller=p1, base_power=1, base_toughness=1)
        for c in [c1, c2, c3]:
            c.card_types = {CardType.CREATURE}
            c.is_tapped = False

        set_board_state(game, 0, graveyard=[card], battlefield=[c1, c2, c3])
        cast_spell(game, 0, "Group Project")

        battlefield = game.get_battlefield(p1).get_all()
        spirits = [c for c in battlefield if isinstance(c, Creature)
                   and "Spirit" in getattr(c, "subtypes", set())]
        assert len(spirits) >= 1
