"""Audited tests for Akroma's Memorial (SPG collector number 81, dir 81b)."""
from __future__ import annotations
import pytest
from card_impl import AkromasMemorial
from engine.card import Artifact, Creature
from engine.types import Keyword, ManaCost, Supertype
from tests.test_utils import create_game, set_board_state


@pytest.mark.basic
class TestAkromasMemorialBasic:
    def test_is_artifact(self) -> None:
        card = AkromasMemorial()
        assert isinstance(card, Artifact)

    def test_name(self) -> None:
        card = AkromasMemorial()
        assert card.name == "Akroma's Memorial"

    def test_mana_cost(self) -> None:
        card = AkromasMemorial()
        assert card.mana_cost == ManaCost.parse("{7}")

    def test_is_legendary(self) -> None:
        card = AkromasMemorial()
        assert Supertype.LEGENDARY in card.supertypes


@pytest.mark.ability
class TestAkromasMemorialAbility:
    def test_register_triggers_succeeds(self) -> None:
        game = create_game()
        p = game.players[0]
        card = AkromasMemorial(owner=p)
        card.controller = p
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

    def test_grants_keywords_to_creatures(self) -> None:
        """After applying effects, creatures should have flying, first strike, etc."""
        game = create_game()
        p = game.players[0]
        creature = Creature(name="Bear", owner=p, base_power=2, base_toughness=2)
        creature.controller = p
        card = AkromasMemorial(owner=p)
        card.controller = p
        set_board_state(game, 0, battlefield=[creature, card])
        card.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert Keyword.FLYING & creature.keywords
        assert Keyword.FIRST_STRIKE & creature.keywords
        assert Keyword.VIGILANCE & creature.keywords
        assert Keyword.TRAMPLE & creature.keywords
        assert Keyword.HASTE & creature.keywords

    def test_grants_protection_from_black(self) -> None:
        """Creatures should gain protection from black."""
        from engine.protection import has_protection_from
        from engine.types import Color
        game = create_game()
        p = game.players[0]
        creature = Creature(name="Bear", owner=p, base_power=2, base_toughness=2)
        creature.controller = p
        card = AkromasMemorial(owner=p)
        card.controller = p
        set_board_state(game, 0, battlefield=[creature, card])
        card.register_triggers(game)
        game.effect_manager.apply_all(game)
        # Check protection from black via the protection list
        assert hasattr(creature, "protections")
        black_prots = [pr for pr in creature.protections if pr.quality == Color.BLACK]
        assert len(black_prots) >= 1

    def test_grants_protection_from_red(self) -> None:
        """Creatures should gain protection from red."""
        from engine.types import Color
        game = create_game()
        p = game.players[0]
        creature = Creature(name="Bear", owner=p, base_power=2, base_toughness=2)
        creature.controller = p
        card = AkromasMemorial(owner=p)
        card.controller = p
        set_board_state(game, 0, battlefield=[creature, card])
        card.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert hasattr(creature, "protections")
        red_prots = [pr for pr in creature.protections if pr.quality == Color.RED]
        assert len(red_prots) >= 1
