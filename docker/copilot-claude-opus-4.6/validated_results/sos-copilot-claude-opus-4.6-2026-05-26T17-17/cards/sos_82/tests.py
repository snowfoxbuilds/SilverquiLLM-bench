"""Tests for SOS 82 — Eternal Student."""

from __future__ import annotations

from cards.sos.sos_82.card_impl import EternalStudent
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestEternalStudentProperties:
    """Static card data should match the SOS 82 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(EternalStudent(owner=None), Creature)

    def test_name(self) -> None:
        assert EternalStudent(owner=None).name == "Eternal Student"

    def test_mana_cost(self) -> None:
        assert EternalStudent(owner=None).mana_cost == ManaCost.parse("{3}{B}")

    def test_power_toughness(self) -> None:
        card = EternalStudent(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 2


class TestEternalStudentGraveyardAbility:
    """Exile from graveyard to create two 1/1 Inkling tokens with flying."""

    def test_activate_from_graveyard_creates_tokens(self) -> None:
        game = create_game()
        p1 = game.players[0]

        student = EternalStudent(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[student],
                        mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1})

        # Activate the graveyard ability
        student.activate_ability(game, 0)

        # Student should be exiled (not in graveyard anymore)
        gy = game.get_graveyard(p1)
        gy_names = [c.name for c in gy.cards] if hasattr(gy, 'cards') else [c.name for c in gy]
        assert "Eternal Student" not in gy_names

        # Two Inkling tokens should be on the battlefield
        bf = game.get_battlefield(p1)
        bf_cards = bf.cards if hasattr(bf, 'cards') else list(bf)
        inklings = [c for c in bf_cards if "Inkling" in c.name]
        assert len(inklings) == 2

    def test_inkling_tokens_have_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]

        student = EternalStudent(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[student],
                        mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1})

        student.activate_ability(game, 0)

        bf = game.get_battlefield(p1)
        bf_cards = bf.cards if hasattr(bf, 'cards') else list(bf)
        inklings = [c for c in bf_cards if "Inkling" in c.name]
        for token in inklings:
            assert Keyword.FLYING in token.keywords

    def test_inkling_tokens_are_1_1(self) -> None:
        game = create_game()
        p1 = game.players[0]

        student = EternalStudent(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[student],
                        mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1})

        student.activate_ability(game, 0)

        bf = game.get_battlefield(p1)
        bf_cards = bf.cards if hasattr(bf, 'cards') else list(bf)
        inklings = [c for c in bf_cards if "Inkling" in c.name]
        for token in inklings:
            assert token.base_power == 1
            assert token.base_toughness == 1
