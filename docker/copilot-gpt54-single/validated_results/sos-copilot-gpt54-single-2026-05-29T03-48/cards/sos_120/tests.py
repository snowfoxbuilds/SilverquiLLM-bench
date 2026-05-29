"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Instant, Land, Sorcery
from engine.types import ManaCost, ManaType, Phase
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state

ORACLE_TEXT = (
    "Exile cards from the top of your library until you exile cards with total "
    "mana value 4 or greater. You may cast any number of spells from among them "
    "without paying their mana costs.\n"
    "Paradigm (Then exile this spell. After you first resolve a spell with this "
    "name, you may cast a copy of it from exile without paying its mana cost at "
    "the beginning of each of your first main phases.)"
)


def _make_instant(name: str, cost: str) -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse(cost))


def _make_sorcery(name: str, cost: str) -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse(cost))


def _make_land(name: str) -> Land:
    return Land(name=name)


def _set_library_top_to_bottom(game, player, cards: list[object]) -> None:
    library = game.get_library(player)
    for existing in library.get_all():
        library.remove(existing)
    for card in reversed(cards):
        card.owner = player
        card.controller = player
        library.add(card)


def _advance_to_next_precombat_main(game, player, *, after_turn: int) -> None:
    for _ in range(40):
        if (
            game.active_player is player
            and game.phase is Phase.PRECOMBAT_MAIN
            and game.step is None
            and game.turn_number > after_turn
        ):
            return
        game.advance_phase()
    raise AssertionError("did not reach the player's next precombat main phase")


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(ImprovisationCapstone(owner=None), Sorcery)

    def test_name(self) -> None:
        assert ImprovisationCapstone(owner=None).name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        assert ImprovisationCapstone(owner=None).mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_has_lesson_subtype_and_full_oracle_text(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert "Lesson" in card.subtypes
        assert card.rules_text == ORACLE_TEXT


class TestImprovisationCapstoneResolution:
    """Resolution should exile cards up to the mana-value threshold, then offer free casts."""

    def test_exiles_until_total_mana_value_reaches_four(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        one_drop = _make_instant("Spark Note", "{R}")
        three_drop = _make_sorcery("Final Refrain", "{2}{R}")
        untouched = _make_instant("Left Behind", "{1}")
        _set_library_top_to_bottom(game, p1, [one_drop, three_drop, untouched])

        p1.choose_yes_no = lambda _prompt: False  # type: ignore[method-assign]

        card.on_resolve(game)

        assert game.get_exile(p1).contains(one_drop)
        assert game.get_exile(p1).contains(three_drop)
        assert game.get_library(p1).contains(untouched)

    def test_resolution_with_empty_library_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        card.on_resolve(game)

        assert game.get_exile(p1).get_all() == []
        assert game.stack.is_empty()

    def test_casts_any_number_of_exiled_spells_for_free(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        one_drop = _make_instant("Spark Note", "{R}")
        three_drop = _make_sorcery("Final Refrain", "{2}{R}")
        _set_library_top_to_bottom(game, p1, [one_drop, three_drop])
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        answers = iter([True, True])
        p1.choose_yes_no = lambda _prompt: next(answers)  # type: ignore[method-assign]

        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_graveyard(p1).contains(one_drop)
        assert game.get_graveyard(p1).contains(three_drop)
        assert game.get_exile(p1).contains(card)

    def test_declining_free_cast_leaves_exiled_spell_in_exile(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        four_drop = _make_sorcery("Big Finish", "{3}{R}")
        _set_library_top_to_bottom(game, p1, [four_drop])
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        p1.choose_yes_no = lambda _prompt: False  # type: ignore[method-assign]

        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_exile(p1).contains(four_drop)
        assert not game.get_graveyard(p1).contains(four_drop)

    def test_lands_are_exiled_but_not_offered_as_free_casts(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        land = _make_land("Forgotten Stage")
        four_drop = _make_sorcery("Big Finish", "{3}{R}")
        untouched = _make_instant("Still Waiting", "{R}")
        _set_library_top_to_bottom(game, p1, [land, four_drop, untouched])
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        prompt_count = 0

        def _choose_yes_no(_prompt: str) -> bool:
            nonlocal prompt_count
            prompt_count += 1
            return True

        p1.choose_yes_no = _choose_yes_no  # type: ignore[method-assign]

        cast_spell(game, 0, "Improvisation Capstone")

        assert prompt_count == 1
        assert game.get_exile(p1).contains(land)
        assert game.get_graveyard(p1).contains(four_drop)
        assert game.get_library(p1).contains(untouched)


class TestImprovisationCapstoneParadigm:
    """Paradigm should exile the spell and offer recurring copies from exile."""

    def test_paradigm_exiles_capstone_after_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_exile(p1).contains(card)
        assert not game.get_graveyard(p1).contains(card)

    def test_paradigm_does_not_trigger_in_same_turn_postcombat_main(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        p1.choose_yes_no = lambda _prompt: True  # type: ignore[method-assign]

        cast_spell(game, 0, "Improvisation Capstone")
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert game.stack.is_empty()
        assert game.get_exile(p1).contains(card)

    def test_paradigm_casts_a_copy_from_exile_at_your_next_precombat_main(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        p1.choose_yes_no = lambda _prompt: True  # type: ignore[method-assign]

        cast_spell(game, 0, "Improvisation Capstone")
        resolved_on_turn = game.turn_number
        _advance_to_next_precombat_main(game, p1, after_turn=resolved_on_turn)

        top = game.stack.peek()
        assert top is not None
        assert top.source is not card
        assert top.source.name == "Improvisation Capstone"
        assert game.get_exile(p1).contains(card)

    def test_paradigm_repeats_on_later_first_main_phases_after_a_decline(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        answers = iter([False, True])
        p1.choose_yes_no = lambda _prompt: next(answers)  # type: ignore[method-assign]

        cast_spell(game, 0, "Improvisation Capstone")
        resolved_on_turn = game.turn_number
        _advance_to_next_precombat_main(game, p1, after_turn=resolved_on_turn)
        assert game.stack.is_empty()

        first_offer_turn = game.turn_number
        _advance_to_next_precombat_main(game, p1, after_turn=first_offer_turn)

        top = game.stack.peek()
        assert top is not None
        assert top.source.name == "Improvisation Capstone"
        assert top.source is not card
