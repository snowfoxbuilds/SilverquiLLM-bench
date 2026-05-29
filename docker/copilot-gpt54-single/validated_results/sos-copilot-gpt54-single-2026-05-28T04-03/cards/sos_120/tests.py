"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land, Sorcery
from engine.casting import cast_spell as engine_cast_spell
from engine.types import CardMechanic, CardType, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, fire_beginning_of_main_phase, set_board_state


def _instant(name: str, cost: str) -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse(cost))


def _sorcery(name: str, cost: str) -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse(cost))


def _creature(name: str, cost: str) -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse(cost),
        base_power=2,
        base_toughness=2,
    )


def _land(name: str) -> Land:
    return Land(name=name)


def _load_library(player, cards_bottom_to_top: list) -> None:
    library = player.zones[Zone.LIBRARY]
    for card in list(library.get_all()):
        library.remove(card)

    for card in cards_bottom_to_top:
        card.owner = player
        card.controller = player
        library.add(card)


def _cast_and_resolve_capstone(game, player, capstone: ImprovisationCapstone) -> None:
    engine_cast_spell(game, player, capstone)
    game.stack.pop().on_resolve(game)


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_is_a_sorcery_lesson(self) -> None:
        card = ImprovisationCapstone(owner=None)

        assert isinstance(card, Sorcery)
        assert CardType.SORCERY in card.card_types
        assert "Lesson" in card.subtypes

    def test_name_and_mana_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)

        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_has_public_paradigm_mechanic_marker(self) -> None:
        card = ImprovisationCapstone(owner=None)

        assert CardMechanic.PARADIGM in card.mechanics
        assert card.has_mechanic(CardMechanic.PARADIGM) is True


class TestImprovisationCapstoneResolution:
    """Improvisation Capstone should exile cards, then optionally free-cast spells."""

    def test_exiles_cards_until_total_mana_value_reaches_four_and_leaves_the_rest_of_the_library(self) -> None:
        game = create_game()
        player = game.players[0]
        capstone = ImprovisationCapstone(owner=player, controller=player)
        untouched = _creature("Dormant Colossus", "{5}")
        three_drop = _sorcery("Burst of Insight", "{2}{R}")
        one_drop = _instant("Quick Note", "{U}")
        land = _land("Campus")

        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )
        _load_library(player, [untouched, three_drop, one_drop, land])

        decisions = iter([False, False])
        player.choose_yes_no = lambda prompt: next(decisions)

        _cast_and_resolve_capstone(game, player, capstone)

        exile = player.zones[Zone.EXILE]
        library = player.zones[Zone.LIBRARY]

        assert exile.contains(capstone)
        assert exile.contains(land)
        assert exile.contains(one_drop)
        assert exile.contains(three_drop)
        assert not exile.contains(untouched)
        assert library.contains(untouched)
        assert len(library.get_all()) == 1
        assert game.stack.is_empty()

    def test_may_free_cast_multiple_exiled_spells_without_paying_their_mana_costs(self) -> None:
        game = create_game()
        player = game.players[0]
        capstone = ImprovisationCapstone(owner=player, controller=player)
        instant = _instant("Flash of Theory", "{1}{U}")
        creature = _creature("Studio Assistant", "{1}{R}")

        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )
        _load_library(player, [creature, instant])

        decisions = iter([True, True])
        player.choose_yes_no = lambda prompt: next(decisions)

        _cast_and_resolve_capstone(game, player, capstone)

        stack_names = {obj.source.name for obj in game.stack.objects()}

        assert len(game.stack.objects()) == 2
        assert stack_names == {"Flash of Theory", "Studio Assistant"}
        assert player.mana_pool.total() == 0
        assert player.zones[Zone.EXILE].contains(capstone)
        assert not player.zones[Zone.EXILE].contains(instant)
        assert not player.zones[Zone.EXILE].contains(creature)

        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        assert player.zones[Zone.GRAVEYARD].contains(instant)
        assert player.zones[Zone.BATTLEFIELD].contains(creature)

    def test_exiles_every_available_card_if_the_library_runs_out_before_total_mana_value_four(self) -> None:
        game = create_game()
        player = game.players[0]
        capstone = ImprovisationCapstone(owner=player, controller=player)
        two_drop = _instant("Loose Thread", "{1}{U}")
        one_drop = _sorcery("Margin Note", "{R}")
        land = _land("Practice Yard")

        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )
        _load_library(player, [two_drop, one_drop, land])

        decisions = iter([False, False])
        player.choose_yes_no = lambda prompt: next(decisions)

        _cast_and_resolve_capstone(game, player, capstone)

        exile = player.zones[Zone.EXILE]

        assert exile.contains(capstone)
        assert exile.contains(two_drop)
        assert exile.contains(one_drop)
        assert exile.contains(land)
        assert len(player.zones[Zone.LIBRARY].get_all()) == 0
        assert game.stack.is_empty()


class TestImprovisationCapstoneParadigm:
    """Paradigm should exile the spell and offer a copy during first main phases."""

    def test_paradigm_offers_a_copy_at_the_beginning_of_your_precombat_main_phase(self) -> None:
        game = create_game()
        player = game.players[0]
        capstone = ImprovisationCapstone(owner=player, controller=player)
        setup_land = _land("Training Grounds")
        copy_reveal = _creature("Capstone Example", "{4}")

        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )
        _load_library(player, [setup_land])
        _cast_and_resolve_capstone(game, player, capstone)

        _load_library(player, [copy_reveal])
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        decisions = iter([True, False])
        player.choose_yes_no = lambda prompt: next(decisions)

        fire_beginning_of_main_phase(game)

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        copy_obj = game.stack.peek()
        assert copy_obj is not None
        assert copy_obj.source.name == "Improvisation Capstone"
        assert player.mana_pool.total() == 0

        game.stack.pop().on_resolve(game)

        assert player.zones[Zone.EXILE].contains(capstone)
        assert player.zones[Zone.EXILE].contains(copy_reveal)
        assert not player.zones[Zone.GRAVEYARD].contains(capstone)
        assert game.stack.is_empty()

    def test_paradigm_does_not_trigger_during_your_postcombat_main_phase(self) -> None:
        game = create_game()
        player = game.players[0]
        capstone = ImprovisationCapstone(owner=player, controller=player)
        setup_land = _land("Training Grounds")

        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )
        _load_library(player, [setup_land])
        _cast_and_resolve_capstone(game, player, capstone)

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.POSTCOMBAT_MAIN
        game.step = None
        player.choose_yes_no = lambda prompt: True

        fire_beginning_of_main_phase(game)

        assert game.stack.is_empty()
