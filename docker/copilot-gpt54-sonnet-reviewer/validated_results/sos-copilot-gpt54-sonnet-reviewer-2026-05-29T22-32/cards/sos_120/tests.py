"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from types import MethodType

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land, Sorcery
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


def _bind_yes_no(player, answers: list[bool]) -> None:
    remaining = iter(answers)

    def choose_yes_no(self, prompt: str) -> bool:
        try:
            return next(remaining)
        except StopIteration as exc:  # pragma: no cover - defensive failure path
            raise AssertionError(f"Unexpected yes/no prompt: {prompt}") from exc

    player.choose_yes_no = MethodType(choose_yes_no, player)


def _set_library(player, cards: list[object]) -> None:
    library = player.zones[Zone.LIBRARY]
    for existing in library.get_all():
        library.remove(existing)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


def _advance_to_next_precombat_main_for(game, player) -> None:
    start_turn = game.turn_number
    for _ in range(40):
        game.advance_phase()
        if (
            game.phase is Phase.PRECOMBAT_MAIN
            and game.step is None
            and game.active_player is player
            and game.turn_number > start_turn
        ):
            return
    raise AssertionError("Did not reach the requested player's next precombat main phase")


def _make_instant(name: str, cost: str) -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse(cost))


def _make_sorcery(name: str, cost: str) -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse(cost))


def _make_creature(name: str, cost: str) -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse(cost),
        base_power=2,
        base_toughness=2,
    )


def _make_land(name: str = "Test Land") -> Land:
    return Land(name=name)


class TestImprovisationCapstoneProperties:
    """Static characteristics from the card spec."""

    def test_is_a_lesson_sorcery_named_improvisation_capstone(self) -> None:
        card = ImprovisationCapstone(owner=None)

        assert isinstance(card, Sorcery)
        assert CardType.SORCERY in card.card_types
        assert card.name == "Improvisation Capstone"
        assert "Lesson" in card.subtypes

    def test_mana_cost_is_five_red_red(self) -> None:
        assert ImprovisationCapstone(owner=None).mana_cost == ManaCost.parse("{5}{R}{R}")


class TestImprovisationCapstoneResolution:
    """Main spell resolution contract."""

    def test_resolve_exiles_cards_until_total_mana_value_four_or_more(self) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        remaining_library_card = _make_sorcery("Still in Library", "{5}{R}")
        first_exiled = _make_instant("First Exiled", "{R}")
        second_exiled = _make_creature("Second Exiled", "{1}{R}")
        third_exiled = _make_sorcery("Third Exiled", "{R}")

        _set_library(p1, [remaining_library_card, first_exiled, second_exiled, third_exiled])
        _bind_yes_no(p1, [False, False, False])
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        exiled_cards = set(game.get_exile(p1).get_all())
        assert first_exiled in exiled_cards
        assert second_exiled in exiled_cards
        assert third_exiled in exiled_cards
        assert remaining_library_card not in exiled_cards
        assert p1.zones[Zone.LIBRARY].get_all() == [remaining_library_card]

    def test_you_may_cast_any_number_of_exiled_spells_for_free_and_lands_remain_exiled(self) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        remaining_library_card = _make_sorcery("Still in Library", "{5}{R}")
        free_instant = _make_instant("Free Instant", "{1}{R}")
        exiled_land = _make_land("Exiled Land")
        free_creature = _make_creature("Free Creature", "{1}{R}")

        _set_library(p1, [remaining_library_card, free_instant, exiled_land, free_creature])
        _bind_yes_no(p1, [True, True])
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_battlefield(p1).contains(free_creature)
        assert game.get_graveyard(p1).contains(free_instant)
        assert game.get_exile(p1).contains(exiled_land)
        assert p1.zones[Zone.LIBRARY].get_all() == [remaining_library_card]
        assert p1.mana_pool.total() == 0

    def test_you_may_decline_to_cast_the_exiled_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        declined_spell = _make_sorcery("Declined Spell", "{3}{R}")

        _set_library(p1, [declined_spell])
        _bind_yes_no(p1, [False])
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_exile(p1).contains(declined_spell)
        assert not game.get_battlefield(p1).contains(declined_spell)
        assert not game.get_graveyard(p1).contains(declined_spell)


class TestImprovisationCapstoneParadigm:
    """Paradigm exile-and-copy contract."""

    def test_resolving_the_spell_exiles_it_instead_of_putting_it_into_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        revealed_spell = _make_sorcery("Revealed Spell", "{3}{R}")

        _set_library(p1, [revealed_spell])
        _bind_yes_no(p1, [False])
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_exile(p1).contains(capstone)
        assert not game.get_graveyard(p1).contains(capstone)

    def test_paradigm_waits_for_your_next_first_main_phase_and_casts_a_copy_from_exile(self) -> None:
        game = create_game()
        p1, p2 = game.players
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        revealed_spell = _make_sorcery("Revealed Spell", "{3}{R}")

        _set_library(p1, [revealed_spell])
        _bind_yes_no(p1, [False, True])
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )

        cast_spell(game, 0, "Improvisation Capstone")
        _advance_to_next_precombat_main_for(game, p2)

        assert game.stack.is_empty()

        _advance_to_next_precombat_main_for(game, p1)

        stack_object = game.stack.peek()
        assert stack_object is not None
        assert stack_object.source is not capstone
        assert stack_object.source.name == "Improvisation Capstone"
        assert game.get_exile(p1).contains(capstone)

    def test_declining_one_paradigm_copy_does_not_stop_later_first_main_phase_offers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        revealed_spell = _make_sorcery("Revealed Spell", "{3}{R}")

        _set_library(p1, [revealed_spell])
        _bind_yes_no(p1, [False, False, True])
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )

        cast_spell(game, 0, "Improvisation Capstone")
        _advance_to_next_precombat_main_for(game, p1)
        assert game.stack.is_empty()

        _advance_to_next_precombat_main_for(game, p1)
        stack_object = game.stack.peek()

        assert stack_object is not None
        assert stack_object.source is not capstone
        assert stack_object.source.name == "Improvisation Capstone"
