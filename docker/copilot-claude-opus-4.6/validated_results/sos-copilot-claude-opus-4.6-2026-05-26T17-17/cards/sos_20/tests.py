"""Tests for SOS 20 — Informed Inkwright.

Informed Inkwright is a {1}{W} Creature — Human Wizard 2/2
Vigilance.
Repartee — Whenever you cast an instant or sorcery spell that targets a
creature, create a 1/1 white and black Inkling creature token with flying.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_20.card_impl import InformedInkwright
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestInformedInkwrightProperties:
    """Static card data should match the SOS 20 spec."""

    def test_name(self) -> None:
        assert InformedInkwright(owner=None).name == "Informed Inkwright"

    def test_mana_cost(self) -> None:
        assert InformedInkwright(owner=None).mana_cost == ManaCost.parse("{1}{W}")

    def test_is_creature(self) -> None:
        assert isinstance(InformedInkwright(owner=None), Creature)

    def test_power_toughness(self) -> None:
        card = InformedInkwright(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_has_vigilance(self) -> None:
        card = InformedInkwright(owner=None)
        assert Keyword.VIGILANCE in card.keywords


class TestInformedInkwrightRepartee:
    """Repartee trigger: casting an instant/sorcery that targets a creature
    creates a 1/1 white/black Inkling with flying."""

    def test_trigger_creates_inkling_token(self) -> None:
        game = create_game()
        p1 = game.players[0]

        inkwright = InformedInkwright(owner=p1, controller=p1)
        bear = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[inkwright, bear],
                        mana={ManaType.WHITE: 5})

        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        bolt.card_types = {CardType.INSTANT}
        set_board_state(game, 0, hand=[bolt])

        cast_spell(game, 0, "Test Bolt", targets=[bear])

        bf = game.get_battlefield(p1).get_all()
        inklings = [c for c in bf if isinstance(c, Creature)
                    and "Inkling" in getattr(c, "subtypes", set())]
        assert len(inklings) == 1

    def test_inkling_token_is_1_1_with_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]

        inkwright = InformedInkwright(owner=p1, controller=p1)
        bear = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[inkwright, bear],
                        mana={ManaType.WHITE: 5})

        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        bolt.card_types = {CardType.INSTANT}
        set_board_state(game, 0, hand=[bolt])

        cast_spell(game, 0, "Test Bolt", targets=[bear])

        bf = game.get_battlefield(p1).get_all()
        inklings = [c for c in bf if isinstance(c, Creature)
                    and "Inkling" in getattr(c, "subtypes", set())]
        token = inklings[0]
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert Keyword.FLYING in token.keywords

    def test_no_trigger_on_nontargeting_spell(self) -> None:
        """A spell that doesn't target a creature should not trigger."""
        game = create_game()
        p1 = game.players[0]

        inkwright = InformedInkwright(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[inkwright],
                        mana={ManaType.WHITE: 5})

        divination = Instant(name="Divination", owner=p1, controller=p1)
        divination.card_types = {CardType.INSTANT}
        set_board_state(game, 0, hand=[divination])
        cast_spell(game, 0, "Divination")

        bf = game.get_battlefield(p1).get_all()
        inklings = [c for c in bf if isinstance(c, Creature)
                    and "Inkling" in getattr(c, "subtypes", set())]
        assert len(inklings) == 0

    def test_multiple_triggers_on_multiple_spells(self) -> None:
        """Each qualifying spell creates a separate token."""
        game = create_game()
        p1 = game.players[0]

        inkwright = InformedInkwright(owner=p1, controller=p1)
        bear = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[inkwright, bear],
                        mana={ManaType.WHITE: 10})

        bolt1 = Instant(name="Bolt One", owner=p1, controller=p1)
        bolt1.card_types = {CardType.INSTANT}
        bolt2 = Instant(name="Bolt Two", owner=p1, controller=p1)
        bolt2.card_types = {CardType.INSTANT}
        set_board_state(game, 0, hand=[bolt1, bolt2])

        cast_spell(game, 0, "Bolt One", targets=[bear])
        cast_spell(game, 0, "Bolt Two", targets=[bear])

        bf = game.get_battlefield(p1).get_all()
        inklings = [c for c in bf if isinstance(c, Creature)
                    and "Inkling" in getattr(c, "subtypes", set())]
        assert len(inklings) == 2
