"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.casting import cast_spell as cast_spell_to_stack
from engine.card import Creature, Instant, Land, Sorcery
from engine.state_based_actions import resolve_state_based_actions
from engine.types import Color, ManaCost, ManaType, Phase
from test_utils import advance_to_phase, create_game, set_board_state


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _set_precombat_main(game) -> None:
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _put_library_bottom_to_top(game, player, cards) -> None:
    library = game.get_library(player)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


def _instant(name: str, cost: str) -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse(cost))


def _creature(name: str, cost: str, power: int, toughness: int) -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse(cost),
        base_power=power,
        base_toughness=toughness,
    )


class TestImprovisationCapstoneProperties:
    def test_is_a_red_sorcery_lesson_with_paradigm_text(self) -> None:
        card = ImprovisationCapstone(owner=None)

        assert isinstance(card, Sorcery)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert "Lesson" in card.subtypes
        assert card.colors == {Color.RED}
        assert "Paradigm" in card.rules_text


class TestImprovisationCapstoneResolution:
    def test_exiles_from_the_top_until_total_mana_value_is_four_or_more(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        untouched = _creature("Deep Library Titan", "{6}", 6, 6)
        three_drop = _creature("Hill Giant", "{2}{R}", 3, 3)
        one_drop = _instant("Spark", "{R}")
        land = Land(name="Forgotten Crag")

        _put_library_bottom_to_top(game, p1, [untouched, three_drop, one_drop, land])
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        p1._script.extend([False, False])
        _set_precombat_main(game)

        cast_spell_to_stack(game, p1, card)
        game.stack.pop().on_resolve(game)

        assert game.get_exile(p1).contains(land)
        assert game.get_exile(p1).contains(one_drop)
        assert game.get_exile(p1).contains(three_drop)
        assert game.get_library(p1).contains(untouched)
        assert len(game.get_library(p1).get_all()) == 1

    def test_declined_spells_stay_in_exile_and_are_not_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        two_drop = _instant("Twin Bolt", "{1}{R}")
        another_two_drop = _creature("Pensive Ogre", "{1}{R}", 2, 2)

        _put_library_bottom_to_top(game, p1, [another_two_drop, two_drop])
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        p1._script.extend([False, False])
        _set_precombat_main(game)

        cast_spell_to_stack(game, p1, card)
        game.stack.pop().on_resolve(game)

        assert game.stack.is_empty()
        assert game.get_exile(p1).contains(two_drop)
        assert game.get_exile(p1).contains(another_two_drop)

    def test_accepting_exiled_spells_casts_each_nonland_spell_for_free(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        creature_spell = _creature("Workshop Brute", "{2}{R}", 3, 3)
        instant_spell = _instant("Improvised Burst", "{R}")
        land = Land(name="Forgotten Crag")

        _put_library_bottom_to_top(game, p1, [creature_spell, instant_spell, land])
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        p1._script.extend([True, True])
        _set_precombat_main(game)

        cast_spell_to_stack(game, p1, card)
        game.stack.pop().on_resolve(game)

        assert p1.mana_pool.total() == 0
        assert len(game.stack.objects()) == 2
        assert {obj.source for obj in game.stack.objects()} == {creature_spell, instant_spell}
        assert not game.get_exile(p1).contains(creature_spell)
        assert not game.get_exile(p1).contains(instant_spell)
        assert game.get_exile(p1).contains(land)

        _resolve_all(game)

        assert game.get_battlefield(p1).contains(creature_spell)
        assert game.get_graveyard(p1).contains(instant_spell)

    def test_resolved_spell_exiles_itself_for_paradigm(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        _set_precombat_main(game)

        cast_spell_to_stack(game, p1, card)
        game.stack.pop().on_resolve(game)

        assert game.get_exile(p1).contains(card)
        assert not game.get_graveyard(p1).contains(card)


class TestImprovisationCapstoneParadigm:
    def test_paradigm_offers_a_copy_on_your_next_precombat_main_only(self) -> None:
        game = create_game(scripts=([True], []))
        p1, p2 = game.players
        card = ImprovisationCapstone(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        _set_precombat_main(game)

        cast_spell_to_stack(game, p1, card)
        game.stack.pop().on_resolve(game)

        assert game.get_exile(p1).contains(card)

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        assert game.stack.is_empty()

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p2
        assert game.stack.is_empty()

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        top = game.stack.peek()
        assert top is not None
        assert top.controller is p1
        assert top.source.name == "Improvisation Capstone"
        assert top.source is not card
        assert game.get_exile(p1).contains(card)
