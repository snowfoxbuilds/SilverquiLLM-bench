"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Instant, Land, Sorcery
from engine.casting import cast_spell as engine_cast_spell
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


def _set_library(player, cards: list[object]) -> None:
    """Replace *player*'s library with *cards* in bottom-to-top order."""
    library = player.zones[Zone.LIBRARY]
    for obj in library.get_all():
        library.remove(obj)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


def _advance_until(game, predicate, *, max_steps: int = 40) -> None:
    """Advance phases until *predicate(game)* becomes true."""
    for _ in range(max_steps):
        game.advance_phase()
        if predicate(game):
            return
    raise AssertionError('target game state not reached in allotted phase advances')


def _cast_and_resolve(game, player, card: ImprovisationCapstone) -> None:
    """Cast *card* from hand and resolve it plus any free-cast spells it creates."""
    player_index = game.players.index(player)
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    engine_cast_spell(game, player, card)
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_is_a_red_sorcery_lesson_with_paradigm_rules_text(self) -> None:
        card = ImprovisationCapstone(owner=None)

        assert isinstance(card, Sorcery)
        assert card.name == 'Improvisation Capstone'
        assert card.mana_cost == ManaCost.parse('{5}{R}{R}')
        assert CardType.SORCERY in card.card_types
        assert 'Lesson' in card.subtypes
        assert card.rules_text == (
            'Exile cards from the top of your library until you exile cards with '
            'total mana value 4 or greater. You may cast any number of spells '
            'from among them without paying their mana costs.\n'
            'Paradigm (Then exile this spell. After you first resolve a spell '
            'with this name, you may cast a copy of it from exile without paying '
            'its mana cost at the beginning of each of your first main phases.)'
        )
        assert 'Paradigm' in getattr(card, 'mechanic_keywords', set())


class TestImprovisationCapstoneResolution:
    """Resolution should exile cards, then optionally free-cast spells among them."""

    def test_exiles_from_the_top_until_exiled_cards_total_four_mana_value(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        one_mana_spell = Instant(name='Spark Note', mana_cost=ManaCost.parse('{R}'))
        land = Land(name='Mountain')
        three_mana_spell = Sorcery(name='Study Break', mana_cost=ManaCost.parse('{2}{U}'))
        reserve_spell = Instant(name='Deep Reserve', mana_cost=ManaCost.parse('{5}'))
        p1.choose_yes_no = lambda prompt: False
        p1.choose_card = lambda cards, description: cards[0] if cards else None
        p1.choose = lambda options, description: None
        _set_library(p1, [reserve_spell, three_mana_spell, land, one_mana_spell])

        card.on_resolve(game)

        exiled = game.get_exile(p1).get_all()
        assert one_mana_spell in exiled
        assert land in exiled
        assert three_mana_spell in exiled
        assert reserve_spell not in exiled
        assert game.get_library(p1).get_all() == [reserve_spell]

    def test_can_cast_multiple_exiled_spells_for_free_while_leaving_exiled_lands_unplayed(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1)
        two_mana_instant = Instant(name='Flash Insight', mana_cost=ManaCost.parse('{1}{U}'))
        land = Land(name='Mountain')
        two_mana_sorcery = Sorcery(name='Burning Notes', mana_cost=ManaCost.parse('{1}{R}'))
        reserve_spell = Instant(name='Held Back', mana_cost=ManaCost.parse('{5}'))
        _set_library(p1, [reserve_spell, two_mana_sorcery, land, two_mana_instant])
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )
        p1.choose_yes_no = lambda prompt: True

        _cast_and_resolve(game, p1, card)

        assert game.get_graveyard(p1).contains(two_mana_instant)
        assert game.get_graveyard(p1).contains(two_mana_sorcery)
        assert game.get_exile(p1).contains(land)
        assert game.get_exile(p1).contains(card)
        assert not game.get_exile(p1).contains(two_mana_instant)
        assert not game.get_exile(p1).contains(two_mana_sorcery)
        assert game.get_library(p1).get_all() == [reserve_spell]


class TestImprovisationCapstoneParadigm:
    """Paradigm should exile the original spell and offer recurring first-main copies."""

    def test_may_decline_the_future_first_main_phase_copy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1)
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )
        p1.choose_yes_no = lambda prompt: False

        _cast_and_resolve(game, p1, card)
        assert game.get_exile(p1).contains(card)

        _advance_until(
            game,
            lambda g: g.active_player is p1
            and g.phase is Phase.PRECOMBAT_MAIN
            and g.turn_number > 1,
        )

        assert game.stack.is_empty()
        assert game.get_exile(p1).contains(card)

    def test_offers_a_free_copy_on_each_of_your_future_first_main_phases_only(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ImprovisationCapstone(owner=p1)
        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )
        p1.choose_yes_no = lambda prompt: True

        _cast_and_resolve(game, p1, card)

        assert game.get_exile(p1).contains(card)
        assert game.stack.is_empty()

        _advance_until(
            game,
            lambda g: g.active_player is p1 and g.phase is Phase.POSTCOMBAT_MAIN,
        )
        assert game.stack.is_empty()

        _advance_until(
            game,
            lambda g: g.active_player is p2 and g.phase is Phase.PRECOMBAT_MAIN,
        )
        assert game.stack.is_empty()

        _advance_until(
            game,
            lambda g: g.active_player is p1
            and g.phase is Phase.PRECOMBAT_MAIN
            and g.turn_number > 1,
        )

        first_copy = game.stack.peek()
        assert first_copy is not None
        assert first_copy.source is not card
        assert first_copy.source.name == 'Improvisation Capstone'
        assert p1.mana_pool.total() == 0
        assert game.get_exile(p1).contains(card)

        resolved_copy = game.stack.pop()
        resolved_copy.on_resolve(game)
        assert game.get_exile(p1).contains(card)

        _advance_until(
            game,
            lambda g: g.active_player is p1
            and g.phase is Phase.PRECOMBAT_MAIN
            and g.turn_number > 3,
        )

        next_copy = game.stack.peek()
        assert next_copy is not None
        assert next_copy.source.name == 'Improvisation Capstone'
        assert game.get_exile(p1).contains(card)
