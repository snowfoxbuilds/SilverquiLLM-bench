"""Tests for SOS 18 — Harsh Annotation.

Harsh Annotation is a {1}{W} Instant:
"Destroy target creature. Its controller creates a 1/1 white and black
Inkling creature token with flying."
"""

from __future__ import annotations

import pytest
from cards.sos.sos_18.card_impl import HarshAnnotation
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestHarshAnnotationProperties:
    """Static card data should match the SOS 18 spec."""

    def test_name(self) -> None:
        assert HarshAnnotation(owner=None).name == "Harsh Annotation"

    def test_mana_cost(self) -> None:
        assert HarshAnnotation(owner=None).mana_cost == ManaCost.parse("{1}{W}")

    def test_is_instant(self) -> None:
        assert isinstance(HarshAnnotation(owner=None), Instant)


class TestHarshAnnotationResolution:
    """On resolution: destroy target creature, its controller gets a 1/1
    white/black Inkling with flying."""

    def test_destroys_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Enemy Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}

        spell = HarshAnnotation(owner=p1, controller=p1)
        set_board_state(game, 1, battlefield=[target])
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Harsh Annotation", targets=[target])

        # Target creature should be destroyed (moved to graveyard)
        bf = game.get_battlefield(p2).get_all()
        assert target not in bf

    def test_controller_of_destroyed_creature_gets_inkling_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Enemy Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}

        spell = HarshAnnotation(owner=p1, controller=p1)
        set_board_state(game, 1, battlefield=[target])
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Harsh Annotation", targets=[target])

        # P2 (controller of destroyed creature) should have an Inkling token
        bf = game.get_battlefield(p2).get_all()
        inklings = [c for c in bf if isinstance(c, Creature)
                    and "Inkling" in getattr(c, "subtypes", set())]
        assert len(inklings) == 1

    def test_inkling_token_is_1_1(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Enemy Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}

        spell = HarshAnnotation(owner=p1, controller=p1)
        set_board_state(game, 1, battlefield=[target])
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Harsh Annotation", targets=[target])

        bf = game.get_battlefield(p2).get_all()
        inklings = [c for c in bf if isinstance(c, Creature)
                    and "Inkling" in getattr(c, "subtypes", set())]
        token = inklings[0]
        assert token.base_power == 1
        assert token.base_toughness == 1

    def test_inkling_token_has_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Enemy Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}

        spell = HarshAnnotation(owner=p1, controller=p1)
        set_board_state(game, 1, battlefield=[target])
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Harsh Annotation", targets=[target])

        bf = game.get_battlefield(p2).get_all()
        inklings = [c for c in bf if isinstance(c, Creature)
                    and "Inkling" in getattr(c, "subtypes", set())]
        token = inklings[0]
        assert Keyword.FLYING in token.keywords

    def test_destroying_own_creature_gives_self_token(self) -> None:
        """If you target your own creature, you get the Inkling token."""
        game = create_game()
        p1 = game.players[0]

        target = Creature(
            name="Own Bear", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}

        spell = HarshAnnotation(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[target], hand=[spell],
                        mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Harsh Annotation", targets=[target])

        bf = game.get_battlefield(p1).get_all()
        inklings = [c for c in bf if isinstance(c, Creature)
                    and "Inkling" in getattr(c, "subtypes", set())]
        assert len(inklings) == 1
