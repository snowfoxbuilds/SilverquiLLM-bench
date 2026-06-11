"""Tests for SOS 7 — Antiquities on the Loose.

{1}{W}{W} Sorcery. Creates two 2/2 red and white Spirit creature tokens.
If cast from anywhere other than hand, put a +1/+1 counter on each Spirit you control.
Has Flashback {4}{W}{W}.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_7.card_impl import AntiquitiesOnTheLoose
from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestAntiquitiesProperties:
    """Static card data should match the SOS 7 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(AntiquitiesOnTheLoose(owner=None), Sorcery)

    def test_name(self) -> None:
        assert AntiquitiesOnTheLoose(owner=None).name == "Antiquities on the Loose"

    def test_mana_cost(self) -> None:
        assert AntiquitiesOnTheLoose(owner=None).mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_has_flashback(self) -> None:
        card = AntiquitiesOnTheLoose(owner=None)
        assert Keyword.FLASHBACK in card.keywords


class TestAntiquitiesResolution:
    """Resolution creates two 2/2 red and white Spirit tokens."""

    def test_creates_two_tokens(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AntiquitiesOnTheLoose(owner=p1, controller=p1)
        card.cast_from_zone = Zone.HAND
        before = len(game.get_battlefield(p1).get_all())
        card.on_resolve(game)
        after = len(game.get_battlefield(p1).get_all())
        assert after - before == 2

    def test_tokens_are_two_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AntiquitiesOnTheLoose(owner=p1, controller=p1)
        card.cast_from_zone = Zone.HAND
        card.on_resolve(game)
        tokens = [
            obj for obj in game.get_battlefield(p1).get_all()
            if isinstance(obj, Creature) and obj.base_power == 2 and obj.base_toughness == 2
        ]
        assert len(tokens) == 2

    def test_tokens_are_spirits(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AntiquitiesOnTheLoose(owner=p1, controller=p1)
        card.cast_from_zone = Zone.HAND
        card.on_resolve(game)
        tokens = [
            obj for obj in game.get_battlefield(p1).get_all()
            if isinstance(obj, Creature)
        ]
        for tok in tokens:
            assert "Spirit" in getattr(tok, "subtypes", set())


class TestAntiquitiesCastFromNonHand:
    """When cast from non-hand (e.g. flashback), +1/+1 on each Spirit."""

    def test_counters_on_new_tokens_when_cast_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AntiquitiesOnTheLoose(owner=p1, controller=p1)
        card.cast_from_zone = Zone.GRAVEYARD  # flashback
        card.on_resolve(game)
        tokens = [
            obj for obj in game.get_battlefield(p1).get_all()
            if isinstance(obj, Creature)
        ]
        # Each new spirit should have a +1/+1 counter
        assert len(tokens) >= 2
        for tok in tokens:
            assert tok.plus_one_counters >= 1

    def test_counters_on_existing_spirits_when_cast_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # Create a pre-existing Spirit
        existing_spirit = Creature(
            name="Spirit Token", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        existing_spirit.subtypes = {"Spirit"}
        existing_spirit.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(existing_spirit)

        card = AntiquitiesOnTheLoose(owner=p1, controller=p1)
        card.cast_from_zone = Zone.GRAVEYARD
        before_counters = existing_spirit.plus_one_counters
        card.on_resolve(game)
        assert existing_spirit.plus_one_counters == before_counters + 1

    def test_no_counters_when_cast_from_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AntiquitiesOnTheLoose(owner=p1, controller=p1)
        card.cast_from_zone = Zone.HAND
        card.on_resolve(game)
        tokens = [
            obj for obj in game.get_battlefield(p1).get_all()
            if isinstance(obj, Creature)
        ]
        for tok in tokens:
            assert tok.plus_one_counters == 0
