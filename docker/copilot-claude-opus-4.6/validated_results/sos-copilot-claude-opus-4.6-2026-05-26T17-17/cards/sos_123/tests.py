"""Tests for SOS 123 — Magmablood Archaic."""

from __future__ import annotations

import pytest

from cards.sos.sos_123.card_impl import MagmabloodArchaic
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestMagmabloodArchaicProperties:
    """Static card data should match the SOS 123 spec."""

    def test_is_creature(self) -> None:
        card = MagmabloodArchaic(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert MagmabloodArchaic(owner=None).name == "Magmablood Archaic"

    def test_mana_cost(self) -> None:
        # {2/R}{2/R}{2/R} — hybrid mana
        assert MagmabloodArchaic(owner=None).mana_cost == ManaCost.parse("{2/R}{2/R}{2/R}")

    def test_power_toughness(self) -> None:
        card = MagmabloodArchaic(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_has_trample(self) -> None:
        card = MagmabloodArchaic(owner=None)
        assert Keyword.TRAMPLE in card.keywords

    def test_has_reach(self) -> None:
        card = MagmabloodArchaic(owner=None)
        assert Keyword.REACH in card.keywords


class TestMagmabloodArchaicConverge:
    """Converge — enters with a +1/+1 counter for each color of mana spent to cast it."""

    def test_one_color_one_counter(self) -> None:
        game = create_game()
        set_board_state(game, 0, hand=[MagmabloodArchaic(owner=None)],
                        mana={ManaType.RED: 3})
        cast_spell(game, 0, "Magmablood Archaic")
        battlefield = game.get_battlefield(game.players[0])
        creature = next(c for c in battlefield if c.name == "Magmablood Archaic")
        # Only red mana spent = 1 color
        assert creature.plus_one_counters == 1

    def test_three_colors_three_counters(self) -> None:
        game = create_game()
        set_board_state(game, 0, hand=[MagmabloodArchaic(owner=None)],
                        mana={ManaType.RED: 1, ManaType.GREEN: 2, ManaType.BLUE: 2})
        cast_spell(game, 0, "Magmablood Archaic", mana_payment={ManaType.RED: 1, ManaType.GREEN: 2, ManaType.BLUE: 2})
        battlefield = game.get_battlefield(game.players[0])
        creature = next(c for c in battlefield if c.name == "Magmablood Archaic")
        # 3 colors spent
        assert creature.plus_one_counters == 3


class TestMagmabloodArchaicSpellTrigger:
    """Whenever you cast an instant or sorcery, creatures get +1/+0 for each color of mana spent."""

    def test_spell_gives_power_boost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = MagmabloodArchaic(owner=p1, controller=p1)
        archaic.card_types = {CardType.CREATURE}
        other = Creature(name="Test Bear", owner=p1, controller=p1,
                         base_power=2, base_toughness=2)
        other.card_types = {CardType.CREATURE}
        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[archaic, other],
                        hand=[bolt],
                        mana={ManaType.RED: 1, ManaType.BLUE: 1})
        cast_spell(game, 0, "Test Bolt", mana_payment={ManaType.RED: 1, ManaType.BLUE: 1})
        # 2 colors of mana spent, so +2/+0 to all creatures we control
        assert other.get_power() >= 4
        assert archaic.get_power() >= 4
