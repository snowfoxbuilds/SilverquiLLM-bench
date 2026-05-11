"""Audited tests for Aegis Turtle (FDN collector number 150) — vanilla creature."""

from __future__ import annotations

import pytest

from card_impl import AegisTurtle

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestAegisTurtleProperties:
    def test_is_creature(self) -> None:
        card = AegisTurtle(name="Aegis Turtle", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = AegisTurtle(name="Aegis Turtle", owner=None)
        assert card.name == "Aegis Turtle"

    def test_power(self) -> None:
        card = AegisTurtle(name="Aegis Turtle", owner=None)
        assert card.power == 0

    def test_toughness(self) -> None:
        card = AegisTurtle(name="Aegis Turtle", owner=None)
        assert card.toughness == 5

    def test_has_turtle_subtype(self) -> None:
        card = AegisTurtle(name="Aegis Turtle", owner=None)
        assert "Turtle" in card.subtypes

    def test_no_keywords(self) -> None:
        card = AegisTurtle(name="Aegis Turtle", owner=None)
        assert card.keywords == Keyword(0)

    def test_mana_cost_cmc(self) -> None:
        """Aegis Turtle costs {U} — converted mana cost 1."""
        card = AegisTurtle(name="Aegis Turtle", owner=None)
        assert card.mana_cost.cmc == 1


@pytest.mark.behavior
class TestAegisTurtleBehavior:
    """Casting and combat behavior tests for Aegis Turtle."""

    def test_can_be_cast_from_hand(self) -> None:
        """Aegis Turtle can be cast from hand with sufficient mana."""
        from tests.test_utils import create_game, set_board_state, cast_spell
        from engine.types import ManaType

        game = create_game()
        card = AegisTurtle(name="Aegis Turtle", owner=game.players[0])
        set_board_state(game, 0, hand=[card], mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Aegis Turtle")
        bf = game.get_battlefield(game.players[0])
        assert card in bf.get_all()

    def test_has_summoning_sickness_when_cast(self) -> None:
        """A freshly cast creature has summoning sickness."""
        from tests.test_utils import create_game, set_board_state, cast_spell
        from engine.types import ManaType

        game = create_game()
        card = AegisTurtle(name="Aegis Turtle", owner=game.players[0])
        set_board_state(game, 0, hand=[card], mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Aegis Turtle")
        assert card.summoning_sick

    def test_deals_zero_combat_damage(self) -> None:
        """Aegis Turtle has 0 power — deals no combat damage when attacking unblocked."""
        from tests.test_utils import create_game, set_board_state, declare_attackers
        from engine.combat import combat_damage_step

        game = create_game()
        card = AegisTurtle(name="Aegis Turtle", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        declare_attackers(game, ["Aegis Turtle"])
        combat_damage_step(game)
        assert game.players[1].life == 20
