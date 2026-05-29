"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase
from test_utils import cast_spell, create_game, set_board_state


class TestImprovisationCapstoneProperties:
    """Static card data should match the card spec."""

    def test_is_a_sorcery(self) -> None:
        assert isinstance(ImprovisationCapstone(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_has_lesson_subtype(self) -> None:
        assert "Lesson" in ImprovisationCapstone(owner=None).subtypes

    def test_has_a_real_paradigm_keyword_flag(self) -> None:
        assert hasattr(Keyword, "PARADIGM")
        assert Keyword.PARADIGM in ImprovisationCapstone(owner=None).keywords


class TestImprovisationCapstoneResolution:
    """Resolution should exile cards, offer free casts, and exile the spell."""

    @staticmethod
    def _set_library(game, player, cards) -> None:
        library = game.get_library(player)
        for existing in library.get_all():
            library.remove(existing)
        for card in cards:
            card.owner = player
            card.controller = player
            library.add(card)

    def test_on_resolve_exiles_from_the_top_until_total_mana_value_is_four_or_more(self) -> None:
        game = create_game(scripts=([False, False], []))
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        remaining = Creature(
            name="Still in Library",
            mana_cost=ManaCost.parse("{4}"),
            base_power=4,
            base_toughness=4,
        )
        one_drop = Instant(name="One Drop", mana_cost=ManaCost.parse("{R}"))
        three_drop = Sorcery(name="Three Drop", mana_cost=ManaCost.parse("{2}{R}"))
        self._set_library(game, p1, [remaining, one_drop, three_drop])

        spell.on_resolve(game)

        exile = game.get_exile(p1)
        library = game.get_library(p1)
        assert exile.contains(three_drop)
        assert exile.contains(one_drop)
        assert not exile.contains(remaining)
        assert library.contains(remaining)
        assert not library.contains(three_drop)
        assert not library.contains(one_drop)

    def test_casting_it_can_free_cast_any_number_of_exiled_nonland_spells(self) -> None:
        game = create_game(scripts=([True, True], []))
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1)
        free_creature = Creature(
            name="Free Creature",
            mana_cost=ManaCost.parse("{1}{R}"),
            base_power=2,
            base_toughness=2,
        )
        free_instant = Instant(name="Free Instant", mana_cost=ManaCost.parse("{1}{R}"))
        exiled_land = Land(name="Exiled Mountain")
        remaining = Creature(
            name="Left Behind",
            mana_cost=ManaCost.parse("{4}"),
            base_power=4,
            base_toughness=4,
        )
        self._set_library(game, p1, [remaining, free_creature, free_instant, exiled_land])
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_battlefield(p1).contains(free_creature)
        assert game.get_graveyard(p1).contains(free_instant)
        assert game.get_exile(p1).contains(exiled_land)
        assert not game.get_battlefield(p1).contains(exiled_land)
        assert not game.get_graveyard(p1).contains(exiled_land)
        assert game.get_library(p1).contains(remaining)
        assert p1.mana_pool.total() == 0

    def test_declining_the_free_casts_leaves_the_exiled_spells_in_exile(self) -> None:
        game = create_game(scripts=([False, False], []))
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1)
        free_creature = Creature(
            name="Declined Creature",
            mana_cost=ManaCost.parse("{1}{R}"),
            base_power=2,
            base_toughness=2,
        )
        free_instant = Instant(name="Declined Instant", mana_cost=ManaCost.parse("{1}{R}"))
        self._set_library(game, p1, [free_creature, free_instant])
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        exile = game.get_exile(p1)
        assert exile.contains(free_creature)
        assert exile.contains(free_instant)
        assert not game.get_battlefield(p1).contains(free_creature)
        assert not game.get_graveyard(p1).contains(free_instant)

    def test_casting_with_an_empty_library_exiles_the_spell_instead_of_putting_it_into_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1)
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)


class TestImprovisationCapstoneParadigm:
    """Paradigm should keep offering a free copy from exile on later first main phases."""

    @staticmethod
    def _set_library(game, player, cards) -> None:
        library = game.get_library(player)
        for existing in library.get_all():
            library.remove(existing)
        for card in cards:
            card.owner = player
            card.controller = player
            library.add(card)

    @staticmethod
    def _advance_until_precombat_main_for(game, player) -> None:
        for _ in range(40):
            game.advance_phase()
            if game.active_player is player and game.phase == Phase.PRECOMBAT_MAIN and game.step is None:
                return
        raise AssertionError("Did not reach the player's next precombat main phase")

    @staticmethod
    def _resolve_stack(game) -> None:
        from engine.state_based_actions import resolve_state_based_actions

        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
            resolve_state_based_actions(game)

    def test_first_resolution_sets_up_a_copy_cast_from_exile_on_your_next_precombat_main(self) -> None:
        game = create_game(scripts=([False, False, True, True], []))
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1)
        future_creature = Creature(
            name="Future Lesson",
            mana_cost=ManaCost.parse("{3}{R}"),
            base_power=4,
            base_toughness=4,
        )
        one_drop = Instant(name="Earlier One Drop", mana_cost=ManaCost.parse("{R}"))
        three_drop = Sorcery(name="Earlier Three Drop", mana_cost=ManaCost.parse("{2}{R}"))
        self._set_library(game, p1, [future_creature, one_drop, three_drop])
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )

        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p1).contains(spell)
        assert game.get_library(p1).contains(future_creature)

        self._advance_until_precombat_main_for(game, p1)
        self._resolve_stack(game)

        assert game.get_battlefield(p1).contains(future_creature)
        assert game.get_exile(p1).contains(spell)
        assert not game.get_library(p1).contains(future_creature)

    def test_paradigm_repeats_on_later_precombat_main_phases(self) -> None:
        game = create_game(scripts=([False, False, True, True, True, True], []))
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1)
        first_future_creature = Creature(
            name="First Future Creature",
            mana_cost=ManaCost.parse("{3}{R}"),
            base_power=4,
            base_toughness=4,
        )
        second_future_creature = Creature(
            name="Second Future Creature",
            mana_cost=ManaCost.parse("{3}{R}"),
            base_power=4,
            base_toughness=4,
        )
        one_drop = Instant(name="Setup One Drop", mana_cost=ManaCost.parse("{R}"))
        three_drop = Sorcery(name="Setup Three Drop", mana_cost=ManaCost.parse("{2}{R}"))
        self._set_library(
            game,
            p1,
            [second_future_creature, first_future_creature, one_drop, three_drop],
        )
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        self._advance_until_precombat_main_for(game, p1)
        self._resolve_stack(game)
        self._advance_until_precombat_main_for(game, p1)
        self._resolve_stack(game)

        battlefield = game.get_battlefield(p1)
        assert battlefield.contains(first_future_creature)
        assert battlefield.contains(second_future_creature)
        assert game.get_exile(p1).contains(spell)
        assert CardType.SORCERY in spell.card_types
