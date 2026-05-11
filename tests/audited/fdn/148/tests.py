"""Audited tests for Stroke of Midnight (FDN collector number 148)."""

from __future__ import annotations

import pytest

from card_impl import StrokeOfMidnight

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestStrokeOfMidnightProperties:
    def test_is_instant(self):
        card = StrokeOfMidnight()
        assert isinstance(card, Instant)

    def test_name(self):
        card = StrokeOfMidnight()
        assert card.name == "Stroke of Midnight"

    def test_mana_cost(self):
        card = StrokeOfMidnight()
        assert card.mana_cost == ManaCost.parse("{2}{W}")


@pytest.mark.ability
class TestStrokeOfMidnightResolution:
    def test_destroys_nonland_permanent(self):
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])
        spell = StrokeOfMidnight(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p2).get_all())
        creature_found = any(c is creature for c in bf)
        assert not creature_found

    def test_controller_gets_human_token(self):
        """Destroyed permanent's controller creates a 1/1 white Human token."""
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(name="Target", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])
        initial_p2_bf = len(list(game.get_battlefield(p2).get_all()))
        spell = StrokeOfMidnight(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p2).get_all())
        # The target creature was destroyed, but a Human token was created
        # so p2's battlefield should have at least one creature (the token)
        humans = [c for c in bf if getattr(c, "name", "").lower().startswith("human")]
        assert len(humans) >= 1, "Controller should receive a Human token"

    def test_human_token_is_1_1(self):
        """The Human token created should be a 1/1."""
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(name="Target", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])
        spell = StrokeOfMidnight(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p2).get_all())
        humans = [c for c in bf if getattr(c, "name", "").lower().startswith("human")]
        assert len(humans) >= 1
        token = humans[0]
        assert token.base_power == 1
        assert token.base_toughness == 1

    def test_destroys_artifact_gives_token(self):
        """Destroying an artifact should also create a Human token for its controller."""
        game = create_game()
        p1, p2 = game.players
        art = Artifact(name="Treasure", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[art])
        spell = StrokeOfMidnight(owner=p1, controller=p1)
        spell.chosen_targets = [art]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p2).get_all())
        humans = [c for c in bf if getattr(c, "name", "").lower().startswith("human")]
        assert len(humans) >= 1


@pytest.mark.edge
class TestStrokeOfMidnightEdge:
    def test_no_target_state_unchanged(self):
        """Empty targets list: state should remain unchanged."""
        game = create_game()
        p1 = game.players[0]
        initial_bf = len(list(game.get_battlefield(p1).get_all()))
        spell = StrokeOfMidnight(owner=p1, controller=p1)
        spell.chosen_targets = []
        spell.on_resolve(game)
        assert len(list(game.get_battlefield(p1).get_all())) == initial_bf
