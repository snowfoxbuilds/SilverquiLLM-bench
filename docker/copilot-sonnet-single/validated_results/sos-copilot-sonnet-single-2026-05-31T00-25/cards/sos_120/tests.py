"""Tests for Improvisation Capstone (sos_120)."""

from __future__ import annotations

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestImprovisationCapstoneProperties:
    def test_name(self):
        card = ImprovisationCapstone()
        assert card.name == "Improvisation Capstone"

    def test_mana_cost_cmc(self):
        card = ImprovisationCapstone()
        assert card.mana_cost.cmc == 7  # {5}{R}{R}

    def test_mana_cost_generic(self):
        card = ImprovisationCapstone()
        assert card.mana_cost.generic == 5

    def test_mana_cost_red_pips(self):
        card = ImprovisationCapstone()
        assert card.mana_cost.pips.get(ManaType.RED, 0) == 2

    def test_is_sorcery(self):
        card = ImprovisationCapstone()
        assert CardType.SORCERY in card.card_types

    def test_subtype_lesson(self):
        card = ImprovisationCapstone()
        assert "Lesson" in card.subtypes

    def test_paradigm_initially_false(self):
        card = ImprovisationCapstone()
        assert card.paradigm_resolved is False


class TestImprovisationCapstoneResolve:
    def test_on_resolve_removes_cards_from_library(self):
        """Cards should be removed from library (moved to exile or cast)."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        # Library cards with MV=2 each; need at least 2 to reach total MV>=4
        lib1 = Instant(name="LibCard1", mana_cost=ManaCost.parse("{1}{U}"), owner=p1, controller=p1)
        lib2 = Instant(name="LibCard2", mana_cost=ManaCost.parse("{1}{R}"), owner=p1, controller=p1)
        lib3 = Sorcery(name="LibCard3", mana_cost=ManaCost.parse("{3}"), owner=p1, controller=p1)

        library = game.get_library(p1)
        for c in [lib3, lib1, lib2]:  # lib2 is on top (last added)
            library.add(c)

        initial_count = len(library.get_all())
        card.on_resolve(game)
        assert len(library.get_all()) < initial_count

    def test_on_resolve_exiles_until_mv_4(self):
        """Should exile until total MV reaches at least 4."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        # Cards with MV=1 each; need at least 4 to reach >=4
        lib_cards = [
            Instant(name=f"Card{i}", mana_cost=ManaCost.parse("{1}"), owner=p1, controller=p1)
            for i in range(6)
        ]
        library = game.get_library(p1)
        for c in lib_cards:
            library.add(c)

        card.on_resolve(game)
        # At most 2 cards remain (exiled at least 4 of the 6)
        assert len(library.get_all()) <= 2

    def test_on_resolve_sets_paradigm_resolved(self):
        """After resolution, paradigm_resolved should be True."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        # Put one card with MV>=4 on top of library
        big = Sorcery(name="BigCard", mana_cost=ManaCost.parse("{4}"), owner=p1, controller=p1)
        game.get_library(p1).add(big)

        card.on_resolve(game)
        assert card.paradigm_resolved is True

    def test_on_resolve_works_with_empty_library(self):
        """Should handle an empty library gracefully."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        # Ensure library is empty
        library = game.get_library(p1)
        for c in list(library.get_all()):
            library.remove(c)

        card.on_resolve(game)
        assert card.paradigm_resolved is True


class TestImprovisationCapstoneParadigm:
    def test_on_cast_registers_replacement_effect(self):
        """on_cast should register a replacement effect for the paradigm exile."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        card.on_cast(game)
        effects = game.replacement_manager.get_effects()
        assert any(e.source is card for e in effects)

    def test_replacement_effect_exiles_this_spell(self):
        """The paradigm replacement should redirect this spell to exile."""
        from engine.events import SpellMovesToGraveyardReplacementEvent

        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        card.on_cast(game)  # registers the replacement effect

        event = SpellMovesToGraveyardReplacementEvent(
            spell=card, destination="graveyard", controller=p1, owner=p1
        )
        result = game.replacement_manager.apply(game, event)
        assert result.destination == "exile"

    def test_replacement_effect_does_not_apply_to_other_spells(self):
        """The paradigm replacement should only apply to this specific card."""
        from engine.events import SpellMovesToGraveyardReplacementEvent

        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        other = Sorcery(name="OtherSpell", owner=p1, controller=p1)

        card.on_cast(game)

        event = SpellMovesToGraveyardReplacementEvent(
            spell=other, destination="graveyard", controller=p1, owner=p1
        )
        result = game.replacement_manager.apply(game, event)
        assert result.destination == "graveyard"  # unchanged

    def test_replacement_not_double_registered(self):
        """Calling register_replacement_effects twice should not duplicate effects."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        card.register_replacement_effects(game)
        card.register_replacement_effects(game)

        effects = [e for e in game.replacement_manager.get_effects() if e.source is card]
        assert len(effects) == 1
