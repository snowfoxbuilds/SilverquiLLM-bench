"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land, Sorcery
from engine.casting import cast_spell as engine_cast_spell
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


def _set_library(player, cards: list[object]) -> None:
    """Replace a player's library with *cards* in bottom-to-top order."""
    library = player.zones[Zone.LIBRARY]
    for card in library.get_all():
        library.remove(card)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


def _resolve_capstone(game, player, capstone: ImprovisationCapstone) -> None:
    engine_cast_spell(game, player, capstone)
    stack_obj = game.stack.pop()
    assert stack_obj.source is capstone
    stack_obj.on_resolve(game)


def _advance_to_next_precombat_main_for(game, player) -> None:
    for _ in range(30):
        game.advance_phase()
        if (
            game.active_player is player
            and game.phase == Phase.PRECOMBAT_MAIN
            and game.step is None
        ):
            return
    raise AssertionError("Did not reach the requested player's next precombat main phase")


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_is_sorcery_lesson_named_and_costed(self) -> None:
        card = ImprovisationCapstone(owner=None)

        assert isinstance(card, Sorcery)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert CardType.SORCERY in card.card_types
        assert "Lesson" in card.subtypes


class TestImprovisationCapstoneResolution:
    """Resolution should exile cards, optionally free-cast spells, and self-exile."""

    def test_exiles_from_the_top_until_total_mana_value_four_or_greater(self) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        one_drop = Instant(name="Spark Note", mana_cost=ManaCost.parse("{R}"))
        three_drop = Creature(
            name="Stage Lion",
            mana_cost=ManaCost.parse("{2}{R}"),
            base_power=3,
            base_toughness=3,
        )
        untouched = Sorcery(name="Left Behind", mana_cost=ManaCost.parse("{5}{R}"))

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        _set_library(p1, [untouched, one_drop, three_drop])
        p1.choose_yes_no = lambda _prompt: False

        _resolve_capstone(game, p1, capstone)

        assert game.get_exile(p1).contains(three_drop)
        assert game.get_exile(p1).contains(one_drop)
        assert not game.get_exile(p1).contains(untouched)
        assert game.get_library(p1).contains(untouched)
        assert game.get_exile(p1).contains(capstone)
        assert not game.get_graveyard(p1).contains(capstone)

    def test_you_may_decline_to_cast_the_exiled_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        two_drop_a = Instant(name="Quick Sketch", mana_cost=ManaCost.parse("{1}{R}"))
        two_drop_b = Sorcery(name="Final Draft", mana_cost=ManaCost.parse("{1}{R}"))

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        _set_library(p1, [two_drop_a, two_drop_b])
        p1.choose_yes_no = lambda _prompt: False

        _resolve_capstone(game, p1, capstone)

        assert game.stack.is_empty()
        assert game.get_exile(p1).contains(two_drop_a)
        assert game.get_exile(p1).contains(two_drop_b)

    def test_can_cast_multiple_exiled_spells_without_paying_their_mana_costs(self) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        free_instant = Instant(name="Quick Sketch", mana_cost=ManaCost.parse("{1}{R}"))
        free_creature = Creature(
            name="Stage Lion",
            mana_cost=ManaCost.parse("{1}{R}"),
            base_power=2,
            base_toughness=2,
        )

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        _set_library(p1, [free_instant, free_creature])
        p1.choose_yes_no = lambda _prompt: True

        _resolve_capstone(game, p1, capstone)

        assert p1.mana_pool.total() == 0
        assert len(game.stack.objects()) == 2
        assert p1.zones[Zone.STACK].contains(free_instant)
        assert p1.zones[Zone.STACK].contains(free_creature)
        assert not game.get_exile(p1).contains(free_instant)
        assert not game.get_exile(p1).contains(free_creature)

    def test_only_spells_among_the_exiled_cards_can_be_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        mountain = Land(name="Mountain")
        mountain.card_types = {CardType.LAND}
        four_drop = Sorcery(name="Curtain Call", mana_cost=ManaCost.parse("{3}{R}"))

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        _set_library(p1, [four_drop, mountain])
        p1.choose_yes_no = lambda _prompt: True

        _resolve_capstone(game, p1, capstone)

        assert game.get_exile(p1).contains(mountain)
        assert not p1.zones[Zone.STACK].contains(mountain)
        assert not game.get_battlefield(p1).contains(mountain)
        assert p1.zones[Zone.STACK].contains(four_drop)

    def test_empty_library_still_resolves_and_exiles_capstone_itself(self) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        p1.choose_yes_no = lambda _prompt: True

        _resolve_capstone(game, p1, capstone)

        assert game.get_exile(p1).contains(capstone)
        assert len(game.get_exile(p1).get_all()) == 1
        assert game.stack.is_empty()


class TestImprovisationCapstoneParadigm:
    """Paradigm should recur from exile on future first main phases."""

    def test_paradigm_waits_for_your_next_precombat_main_not_postcombat_main(self) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        p1.choose_yes_no = lambda _prompt: False

        _resolve_capstone(game, p1, capstone)

        while game.phase != Phase.POSTCOMBAT_MAIN:
            game.advance_phase()
        assert game.stack.is_empty()

        p1.choose_yes_no = lambda _prompt: True
        _advance_to_next_precombat_main_for(game, p1)

        copy_obj = game.stack.peek()
        assert copy_obj is not None
        assert copy_obj.source.name == "Improvisation Capstone"
        assert copy_obj.source is not capstone
        assert game.get_exile(p1).contains(capstone)

    def test_declining_one_paradigm_copy_does_not_stop_future_first_main_phase_offers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        p1.choose_yes_no = lambda _prompt: False

        _resolve_capstone(game, p1, capstone)
        _advance_to_next_precombat_main_for(game, p1)

        assert game.stack.is_empty()

        p1.choose_yes_no = lambda _prompt: True
        _advance_to_next_precombat_main_for(game, p1)

        copy_obj = game.stack.peek()
        assert copy_obj is not None
        assert copy_obj.source.name == "Improvisation Capstone"
        assert game.get_exile(p1).contains(capstone)
