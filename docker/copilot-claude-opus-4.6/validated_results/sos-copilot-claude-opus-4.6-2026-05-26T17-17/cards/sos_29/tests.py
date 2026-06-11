"""Tests for SOS 29 — Rehearsed Debater."""

from __future__ import annotations

import pytest
from cards.sos.sos_29.card_impl import RehearsedDebater
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state, cast_spell


class TestRehearsedDebaterProperties:
    """Static card data should match the SOS 29 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(RehearsedDebater(owner=None), Creature)

    def test_name(self) -> None:
        assert RehearsedDebater(owner=None).name == "Rehearsed Debater"

    def test_mana_cost(self) -> None:
        assert RehearsedDebater(owner=None).mana_cost == ManaCost.parse("{2}{W}")

    def test_power_toughness(self) -> None:
        card = RehearsedDebater(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_has_vigilance(self) -> None:
        card = RehearsedDebater(owner=None)
        assert Keyword.VIGILANCE in card.keywords


class TestRehearsedDebaterRepartee:
    """Repartee — Whenever you cast an instant or sorcery spell that targets a creature, this gets +1/+1 until end of turn."""

    def test_gets_plus_one_when_instant_targets_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        debater = RehearsedDebater(owner=p1, controller=p1)
        game.get_battlefield(p1).add(debater)
        # Create a target creature on opponent's side
        p2 = game.players[1]
        bear = Creature(name="Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        set_board_state(game, 1, battlefield=[bear])
        # Cast an instant that targets a creature
        from cards.sos.sos_28.card_impl import RapierWit
        set_board_state(game, 0, hand=[RapierWit(owner=p1)], mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Rapier Wit", targets=[bear])
        # Debater should have gotten +1/+1
        assert debater.get_power() >= 4
        assert debater.get_toughness() >= 4

    def test_no_bonus_from_spell_that_does_not_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        debater = RehearsedDebater(owner=p1, controller=p1)
        game.get_battlefield(p1).add(debater)
        # Cast a spell that doesn't target a creature (targeting player or no target)
        from engine.card import Sorcery
        non_targeting = Sorcery(name="Divination", owner=p1, controller=p1)
        non_targeting.mana_cost = ManaCost.parse("{2}{U}")
        set_board_state(game, 0, hand=[non_targeting], mana={ManaType.BLUE: 3, ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Divination")
        # Debater should NOT have gotten a bonus
        assert debater.get_power() == 3
        assert debater.get_toughness() == 3

    def test_bonus_stacks_from_multiple_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        debater = RehearsedDebater(owner=p1, controller=p1)
        game.get_battlefield(p1).add(debater)
        p2 = game.players[1]
        bear = Creature(name="Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        set_board_state(game, 1, battlefield=[bear])
        # Cast two instants targeting a creature
        from cards.sos.sos_28.card_impl import RapierWit
        wit1 = RapierWit(owner=p1)
        wit2 = RapierWit(owner=p1)
        wit2.name = "Rapier Wit"
        set_board_state(game, 0, hand=[wit1, wit2], mana={ManaType.WHITE: 4, ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Rapier Wit", targets=[bear])
        cast_spell(game, 0, "Rapier Wit", targets=[bear])
        # Should get +2/+2 total
        assert debater.get_power() >= 5
        assert debater.get_toughness() >= 5

    def test_bonus_is_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        debater = RehearsedDebater(owner=p1, controller=p1)
        game.get_battlefield(p1).add(debater)
        p2 = game.players[1]
        bear = Creature(name="Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        set_board_state(game, 1, battlefield=[bear])
        from cards.sos.sos_28.card_impl import RapierWit
        set_board_state(game, 0, hand=[RapierWit(owner=p1)], mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Rapier Wit", targets=[bear])
        assert debater.get_power() >= 4
        # End the turn — bonus should expire
        game.end_turn()
        assert debater.get_power() == 3
        assert debater.get_toughness() == 3
