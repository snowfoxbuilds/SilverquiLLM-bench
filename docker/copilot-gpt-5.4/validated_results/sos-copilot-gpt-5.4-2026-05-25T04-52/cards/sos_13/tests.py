"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from collections import deque

from benchmarks.sos.workspace.cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestEmeritusOfTruceProperties:
    """Static front-face data should match the SOS 13 spec."""

    def test_is_cat_cleric_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestEmeritusOfTruceTargeting:
    """The ETB ability should target a player."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = EmeritusOfTruceSwordsToPlowshares(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_players_and_rejects_non_players(self) -> None:
        game = create_game()
        p1 = game.players[0]
        req = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1).get_targets(game)[0]

        non_player = Creature(name="Bear", base_power=2, base_toughness=2)

        assert req.filter_fn(game.players[0]) is True
        assert req.filter_fn(game.players[1]) is True
        assert req.filter_fn(non_player) is False


class TestEmeritusOfTruceResolution:
    """The ETB ability should create the Inkling token for the chosen player."""

    def test_target_player_creates_the_printed_inkling_token(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p2]

        card.on_resolve(game)

        tokens = game.get_battlefield(p2).get_all()
        assert len(tokens) == 1

        token = tokens[0]
        assert isinstance(token, Creature)
        assert token.is_token is True
        assert token.power == 1
        assert token.toughness == 1
        assert "Inkling" in token.subtypes
        assert Keyword.FLYING in token.keywords
        assert get_colors(token) == {Color.WHITE, Color.BLACK}

    def test_no_target_is_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        card.on_resolve(game)

        assert game.get_battlefield(p1).get_all() == []
        assert game.get_battlefield(p2).get_all() == []

    def test_becomes_prepared_when_opponent_controls_more_creatures_than_you(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(
            game,
            1,
            battlefield=[
                Creature(name="Bear A", base_power=2, base_toughness=2),
                Creature(name="Bear B", base_power=2, base_toughness=2),
                Creature(name="Bear C", base_power=2, base_toughness=2),
            ],
        )
        card.chosen_targets = [p1]

        card.on_resolve(game)

        assert card.is_prepared is True

    def test_does_not_become_prepared_when_opponent_does_not_control_more_creatures_than_you(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(
            game,
            1,
            battlefield=[
                Creature(name="Bear A", base_power=2, base_toughness=2),
                Creature(name="Bear B", base_power=2, base_toughness=2),
            ],
        )
        card.chosen_targets = [p1]

        card.on_resolve(game)

        assert card.is_prepared is False

    def test_prepared_spell_copy_exiles_target_creature_gains_life_and_unprepares(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        target = Creature(name="Hill Giant", base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[target])
        p1._script = deque([target])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Swords to Plowshares"

        resolved = game.stack.pop()
        resolved.on_resolve(game)

        assert game.get_battlefield(p2).contains(target) is False
        assert game.get_exile(p2).contains(target) is True
        assert p2.life == 24
