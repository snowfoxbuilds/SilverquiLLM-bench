"""Tests for SOS 91 — Moseo, Vein's New Dean."""

from __future__ import annotations

import pytest

from cards.sos.sos_91.card_impl import MoseoVeinsNewDean
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


class TestMoseoProperties:
    """Static card data should match the SOS 91 spec."""

    def test_is_creature(self) -> None:
        card = MoseoVeinsNewDean(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_name(self) -> None:
        assert MoseoVeinsNewDean(owner=None).name == "Moseo, Vein's New Dean"

    def test_mana_cost(self) -> None:
        assert MoseoVeinsNewDean(owner=None).mana_cost == ManaCost.parse("{2}{B}")

    def test_power_toughness(self) -> None:
        card = MoseoVeinsNewDean(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 1

    def test_has_flying(self) -> None:
        card = MoseoVeinsNewDean(owner=None)
        assert card.keywords & Keyword.FLYING

    def test_is_legendary(self) -> None:
        card = MoseoVeinsNewDean(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = MoseoVeinsNewDean(owner=None)
        assert "Bird" in card.subtypes
        assert "Skeleton" in card.subtypes
        assert "Warlock" in card.subtypes


class TestMoseoEntersTrigger:
    """When Moseo enters, create a 1/1 black and green Pest creature token."""

    def test_enters_creates_pest_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        moseo = MoseoVeinsNewDean(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[moseo], mana={ManaType.BLACK: 1, ManaType.COLORLESS: 2})

        from test_utils import cast_spell
        cast_spell(game, 0, "Moseo, Vein's New Dean")

        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield if getattr(c, 'is_token', False)]
        assert len(tokens) >= 1
        pest = tokens[0]
        assert pest.base_power == 1
        assert pest.base_toughness == 1
        assert "Pest" in pest.subtypes

    def test_pest_token_gains_life_on_attack(self) -> None:
        """The Pest token has 'Whenever this token attacks, you gain 1 life.'"""
        game = create_game()
        p1 = game.players[0]
        moseo = MoseoVeinsNewDean(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[moseo], mana={ManaType.BLACK: 1, ManaType.COLORLESS: 2})

        from test_utils import cast_spell, declare_attackers
        cast_spell(game, 0, "Moseo, Vein's New Dean")

        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield if getattr(c, 'is_token', False)]
        assert len(tokens) >= 1
        pest = tokens[0]
        pest.summoning_sick = False

        life_before = p1.life
        declare_attackers(game, [pest.name])
        assert p1.life == life_before + 1


class TestMoseoInfusionAbility:
    """End step: if you gained life this turn, return creature card with MV <= X from graveyard."""

    def test_infusion_returns_creature_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        moseo = MoseoVeinsNewDean(owner=p1, controller=p1)
        # Put a cheap creature in graveyard
        bear = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
            mana_cost=ManaCost.parse("{1}{G}"),
        )
        set_board_state(game, 0, battlefield=[moseo], graveyard=[bear])

        # Simulate gaining life this turn
        p1.life_gained_this_turn = 3
        
        # Trigger end step
        from test_utils import advance_to_phase
        from engine.types import Phase, Step
        advance_to_phase(game, Phase.ENDING, Step.END)

        # Bear's MV is 2 which is <= 3 life gained, so it should return
        battlefield = game.get_battlefield(p1)
        assert any(c.name == "Grizzly Bears" for c in battlefield)

    def test_infusion_does_nothing_without_life_gain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        moseo = MoseoVeinsNewDean(owner=p1, controller=p1)
        bear = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
            mana_cost=ManaCost.parse("{1}{G}"),
        )
        set_board_state(game, 0, battlefield=[moseo], graveyard=[bear])

        # No life gained
        p1.life_gained_this_turn = 0

        from test_utils import advance_to_phase
        from engine.types import Phase, Step
        advance_to_phase(game, Phase.ENDING, Step.END)

        # Bear should stay in graveyard
        graveyard = game.get_graveyard(p1)
        assert any(c.name == "Grizzly Bears" for c in graveyard)
