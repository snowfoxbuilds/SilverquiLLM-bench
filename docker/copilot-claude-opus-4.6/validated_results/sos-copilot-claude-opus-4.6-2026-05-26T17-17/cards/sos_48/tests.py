"""Tests for SOS 48 — Exhibition Tidecaller.

Creature — Djinn Wizard, 0/2 for {U}.
Opus — Whenever you cast an instant or sorcery spell, target player mills three cards.
If five or more mana was spent to cast that spell, that player mills ten cards instead.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_48.card_impl import ExhibitionTidecaller
from engine.card import Creature, Instant, Sorcery
from engine.types import ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestExhibitionTidecallerProperties:
    """Static card data should match the SOS 48 spec."""

    def test_is_creature(self) -> None:
        card = ExhibitionTidecaller(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = ExhibitionTidecaller(owner=None)
        assert card.name == "Exhibition Tidecaller"

    def test_mana_cost(self) -> None:
        card = ExhibitionTidecaller(owner=None)
        assert card.mana_cost == ManaCost.parse("{U}")

    def test_power_toughness(self) -> None:
        card = ExhibitionTidecaller(owner=None)
        assert card.base_power == 0
        assert card.base_toughness == 2


class TestExhibitionTidecallerOpus:
    """Opus triggered ability: mill on instant/sorcery cast."""

    def test_mills_three_on_cheap_instant(self) -> None:
        """Casting an instant costing less than 5 mana mills 3 cards."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        tidecaller = ExhibitionTidecaller(owner=p1, controller=p1)
        cheap_spell = Instant(name="Opt")
        cheap_spell.owner = p1
        cheap_spell.controller = p1
        cheap_spell.mana_cost = ManaCost.parse("{U}")
        set_board_state(game, 0, battlefield=[tidecaller], hand=[cheap_spell],
                        mana={ManaType.BLUE: 2})
        # Give p2 a library to mill from
        from engine.card import CardImpl
        library_cards = [CardImpl(name=f"Card {i}", owner=p2) for i in range(10)]
        set_board_state(game, 1, library=library_cards)
        lib_before = len(game.get_library(p2).get_all())
        cast_spell(game, 0, "Opt", targets=[p2])
        lib_after = len(game.get_library(p2).get_all())
        assert lib_before - lib_after == 3

    def test_mills_ten_on_expensive_spell(self) -> None:
        """Casting a spell with 5+ mana spent mills 10 cards instead."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        tidecaller = ExhibitionTidecaller(owner=p1, controller=p1)
        expensive_spell = Sorcery(name="Big Sorcery")
        expensive_spell.owner = p1
        expensive_spell.controller = p1
        expensive_spell.mana_cost = ManaCost.parse("{4}{U}")
        set_board_state(game, 0, battlefield=[tidecaller], hand=[expensive_spell],
                        mana={ManaType.BLUE: 1, ManaType.COLORLESS: 4})
        from engine.card import CardImpl
        library_cards = [CardImpl(name=f"Card {i}", owner=p2) for i in range(15)]
        set_board_state(game, 1, library=library_cards)
        lib_before = len(game.get_library(p2).get_all())
        cast_spell(game, 0, "Big Sorcery", targets=[p2])
        lib_after = len(game.get_library(p2).get_all())
        assert lib_before - lib_after == 10

    def test_does_not_trigger_on_creature_spell(self) -> None:
        """Opus only triggers on instant or sorcery spells, not creatures."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        tidecaller = ExhibitionTidecaller(owner=p1, controller=p1)
        creature = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        creature.owner = p1
        creature.controller = p1
        set_board_state(game, 0, battlefield=[tidecaller], hand=[creature],
                        mana={ManaType.COLORLESS: 2})
        from engine.card import CardImpl
        library_cards = [CardImpl(name=f"Card {i}", owner=p2) for i in range(10)]
        set_board_state(game, 1, library=library_cards)
        lib_before = len(game.get_library(p2).get_all())
        cast_spell(game, 0, "Grizzly Bears")
        lib_after = len(game.get_library(p2).get_all())
        assert lib_before - lib_after == 0

    def test_milled_cards_go_to_graveyard(self) -> None:
        """Milled cards should end up in the target player's graveyard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        tidecaller = ExhibitionTidecaller(owner=p1, controller=p1)
        spell = Instant(name="Zap")
        spell.owner = p1
        spell.controller = p1
        spell.mana_cost = ManaCost.parse("{U}")
        set_board_state(game, 0, battlefield=[tidecaller], hand=[spell],
                        mana={ManaType.BLUE: 2})
        from engine.card import CardImpl
        library_cards = [CardImpl(name=f"Card {i}", owner=p2) for i in range(10)]
        set_board_state(game, 1, library=library_cards)
        gy_before = len(game.get_graveyard(p2).get_all())
        cast_spell(game, 0, "Zap", targets=[p2])
        gy_after = len(game.get_graveyard(p2).get_all())
        assert gy_after - gy_before == 3
