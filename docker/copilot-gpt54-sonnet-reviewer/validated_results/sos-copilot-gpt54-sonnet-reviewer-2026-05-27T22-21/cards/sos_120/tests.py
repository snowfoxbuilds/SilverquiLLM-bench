"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Land, Sorcery
from engine.casting import resolve_top
from engine.types import Color, ManaCost, ManaType, Phase, Zone
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state


class TwoManaPracticeSpell(Sorcery):
    """Simple spell used for free-cast and exile tests."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Two-Mana Practice Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        super().__init__(**kwargs)
        self.times_resolved = 0

    def on_resolve(self, game) -> None:
        self.times_resolved += 1


class OneManaPracticeSpell(Sorcery):
    """Simple low-mana spell used to prove the exile stop condition."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "One-Mana Practice Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)


class PracticeLand(Land):
    """Land card used to verify only spells can be cast from among the exiled cards."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Practice Land")
        super().__init__(**kwargs)


def _set_library(player, cards_bottom_to_top) -> None:
    """Replace *player*'s library with *cards_bottom_to_top* order."""

    library = player.zones[Zone.LIBRARY]
    for card in library.get_all():
        library.remove(card)

    for card in cards_bottom_to_top:
        card.owner = player
        card.controller = player
        library.add(card)


def _advance_to_next_precombat_main_for(game, player) -> None:
    """Advance until *player* becomes the active player in precombat main."""

    for _ in range(30):
        game.advance_phase()
        if game.phase is Phase.PRECOMBAT_MAIN and game.active_player is player:
            return
    pytest.fail("Did not reach the requested player's next precombat main phase")


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(ImprovisationCapstone(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_is_red_lesson_with_paradigm_rules_text(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.colors == {Color.RED}
        assert "Lesson" in card.subtypes
        assert "Paradigm" in card.rules_text


class TestImprovisationCapstoneResolution:
    """The front-face spell should exile cards, then free-cast spells from among them."""

    def test_on_resolve_exiles_until_total_mana_value_reaches_four_or_more(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        bottom = OneManaPracticeSpell(name="Bottom Card")
        two_a = TwoManaPracticeSpell(name="Two A")
        two_b = TwoManaPracticeSpell(name="Two B")

        _set_library(p1, [bottom, two_a, two_b])
        p1.choose_yes_no = lambda prompt: False

        spell.on_resolve(game)

        assert game.get_exile(p1).contains(two_b)
        assert game.get_exile(p1).contains(two_a)
        assert not game.get_exile(p1).contains(bottom)
        assert game.get_library(p1).contains(bottom)
        assert len(game.get_exile(p1).get_all()) == 2
        assert game.stack.is_empty()

    def test_on_resolve_can_cast_multiple_exiled_spells_for_free_and_leaves_lands_exiled(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        bottom = OneManaPracticeSpell(name="Bottom Card")
        spell_a = TwoManaPracticeSpell(name="Spell A")
        land = PracticeLand()
        spell_b = TwoManaPracticeSpell(name="Spell B")

        _set_library(p1, [bottom, spell_a, land, spell_b])
        p1.choose_yes_no = lambda prompt: True

        spell.on_resolve(game)

        stacked_sources = {obj.source for obj in game.stack.objects()}
        assert stacked_sources == {spell_a, spell_b}
        assert not game.get_exile(p1).contains(spell_a)
        assert not game.get_exile(p1).contains(spell_b)
        assert game.get_exile(p1).contains(land)
        assert game.get_library(p1).contains(bottom)

        resolve_top(game)
        resolve_top(game)

        assert spell_a.times_resolved == 1
        assert spell_b.times_resolved == 1
        assert game.get_graveyard(p1).contains(spell_a)
        assert game.get_graveyard(p1).contains(spell_b)
        assert game.get_exile(p1).contains(land)

class TestImprovisationCapstoneParadigm:
    """Paradigm should exile the original spell and recast copies on later first main phases."""

    def test_resolving_from_the_stack_exiles_capstone_instead_of_putting_it_into_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_exile(p1).contains(card)
        assert not game.get_graveyard(p1).contains(card)

    def test_paradigm_casts_one_copy_at_each_of_your_future_precombat_main_phases_only(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ImprovisationCapstone(owner=p1, controller=p1)
        answers = iter([True, True])
        p1.choose_yes_no = lambda prompt: next(answers)

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_exile(p1).contains(card)
        assert game.stack.is_empty()

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        assert game.stack.is_empty()

        _advance_to_next_precombat_main_for(game, p2)
        assert game.stack.is_empty()

        _advance_to_next_precombat_main_for(game, p1)
        assert len(game.stack.objects()) == 1
        first_copy = game.stack.peek()
        assert first_copy is not None
        assert first_copy.source is not card
        assert first_copy.source.name == "Improvisation Capstone"
        assert game.get_exile(p1).contains(card)

        resolve_top(game)

        assert game.stack.is_empty()
        assert game.get_exile(p1).contains(card)

        _advance_to_next_precombat_main_for(game, p2)
        assert game.stack.is_empty()

        _advance_to_next_precombat_main_for(game, p1)
        assert len(game.stack.objects()) == 1
        second_copy = game.stack.peek()
        assert second_copy is not None
        assert second_copy.source is not card
        assert second_copy.source.name == "Improvisation Capstone"
        assert game.get_exile(p1).contains(card)
