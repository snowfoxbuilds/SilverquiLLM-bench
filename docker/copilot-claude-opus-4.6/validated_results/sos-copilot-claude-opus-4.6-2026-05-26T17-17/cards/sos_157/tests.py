"""Tests for SOS 157 — Pestbrood Sloth."""

from __future__ import annotations

from cards.sos.sos_157.card_impl import PestbroodSloth
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestPestbroodSlothProperties:
    """Static card data should match the SOS 157 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(PestbroodSloth(owner=None), Creature)

    def test_name(self) -> None:
        assert PestbroodSloth(owner=None).name == "Pestbrood Sloth"

    def test_mana_cost(self) -> None:
        assert PestbroodSloth(owner=None).mana_cost == ManaCost.parse("{3}{G}")

    def test_power_toughness(self) -> None:
        sloth = PestbroodSloth(owner=None)
        assert sloth.power == 4
        assert sloth.toughness == 4

    def test_has_reach(self) -> None:
        sloth = PestbroodSloth(owner=None)
        assert Keyword.REACH in sloth.keywords


class TestPestbroodSlothDiesTrigger:
    """When Pestbrood Sloth dies, create two 1/1 Pest tokens."""

    def test_creates_two_tokens_on_death(self) -> None:
        game = create_game()
        p1 = game.players[0]

        sloth = PestbroodSloth(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[sloth])

        # Move sloth to graveyard (simulate dying)
        game.move_to_zone(sloth, Zone.GRAVEYARD)
        game.process_triggers()

        battlefield = game.get_battlefield(p1).get_all()
        tokens = [c for c in battlefield if "Pest" in c.name]
        assert len(tokens) == 2

    def test_pest_tokens_are_one_one(self) -> None:
        game = create_game()
        p1 = game.players[0]

        sloth = PestbroodSloth(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[sloth])

        game.move_to_zone(sloth, Zone.GRAVEYARD)
        game.process_triggers()

        battlefield = game.get_battlefield(p1).get_all()
        tokens = [c for c in battlefield if "Pest" in c.name]
        for token in tokens:
            assert token.power == 1
            assert token.toughness == 1

    def test_pest_tokens_gain_life_on_attack(self) -> None:
        """Pest tokens have 'Whenever this token attacks, you gain 1 life.'"""
        game = create_game()
        p1 = game.players[0]

        sloth = PestbroodSloth(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[sloth])

        game.move_to_zone(sloth, Zone.GRAVEYARD)
        game.process_triggers()

        battlefield = game.get_battlefield(p1).get_all()
        tokens = [c for c in battlefield if "Pest" in c.name]
        assert len(tokens) >= 1

        # Simulate attacking with a pest token
        token = tokens[0]
        life_before = p1.life
        token.declare_attack(game)
        game.process_triggers()
        assert p1.life == life_before + 1
