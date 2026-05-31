"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.casting import cast_spell as engine_cast_spell
from engine.card import CardImpl, Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, Phase
from test_utils import advance_to_phase, create_game, set_board_state


class _TrackingInstant(Instant):
    """Simple instant used to verify free-cast behavior."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tracking Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)
        self.was_resolved = False

    def on_resolve(self, game) -> None:
        self.was_resolved = True


class _TrackingSorcery(Sorcery):
    """Simple sorcery used to verify free-cast behavior."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tracking Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        super().__init__(**kwargs)
        self.was_resolved = False

    def on_resolve(self, game) -> None:
        self.was_resolved = True


class _TrackingLand(CardImpl):
    """Simple land used to verify only spells can be cast from the exiled pile."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tracking Land")
        kwargs.setdefault("card_types", {CardType.LAND})
        super().__init__(**kwargs)


def _set_library_top_first(game, player, cards_top_first: list[Any]) -> None:
    """Replace *player*'s library using a top-first card list."""
    library = game.get_library(player)
    for obj in library.get_all():
        library.remove(obj)

    for card in reversed(cards_top_first):
        card.owner = player
        card.controller = player
        library.add(card)


def _advance_to_next_precombat_main(game, player) -> None:
    """Advance until *player* reaches their next precombat main phase."""
    for _ in range(40):
        game.advance_phase()
        if game.active_player is player and game.phase == Phase.PRECOMBAT_MAIN and game.step is None:
            return
    raise AssertionError("failed to reach the requested player's next precombat main phase")


def _capstone_mana() -> dict[ManaType, int]:
    return {
        ManaType.COLORLESS: 5,
        ManaType.RED: 2,
    }


def _cast_and_resolve_capstone(game, player, capstone: ImprovisationCapstone) -> None:
    """Cast the card object directly and resolve it."""
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    engine_cast_spell(game, player, capstone)
    stack_obj = game.stack.pop()
    stack_obj.on_resolve(game)


class TestImprovisationCapstoneProperties:
    """Static characteristics should match the card spec."""

    def test_is_a_lesson_sorcery_named_improvisation_capstone_with_the_printed_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)

        assert isinstance(card, Sorcery)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert "Lesson" in card.subtypes
        assert "Paradigm" in card.rules_text


class TestImprovisationCapstoneResolution:
    """Resolution should exile cards until total mana value 4+ and optionally free-cast spells."""

    def test_exiles_from_the_top_of_your_library_until_the_exiled_total_reaches_four_or_more(self) -> None:
        game = create_game()
        p1 = game.players[0]

        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        one_drop = _TrackingInstant(name="One Drop", owner=p1, controller=p1)
        land = _TrackingLand(name="Mountain Stand-In", owner=p1, controller=p1)
        three_drop = _TrackingSorcery(name="Three Drop", owner=p1, controller=p1)
        stay_in_library = _TrackingInstant(
            name="Still in Library",
            mana_cost=ManaCost.parse("{1}{R}"),
            owner=p1,
            controller=p1,
        )

        _set_library_top_first(game, p1, [one_drop, land, three_drop, stay_in_library])
        p1.choose_yes_no = lambda prompt: False

        capstone.on_resolve(game)

        exile = game.get_exile(p1)
        library = game.get_library(p1)

        assert exile.contains(one_drop)
        assert exile.contains(land)
        assert exile.contains(three_drop)
        assert not exile.contains(stay_in_library)
        assert library.contains(stay_in_library)
        assert len(game.stack) == 0

    def test_may_cast_any_number_of_the_exiled_nonland_spells_without_paying_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]

        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        one_drop = _TrackingInstant(name="One Drop", owner=p1, controller=p1)
        land = _TrackingLand(name="Mountain Stand-In", owner=p1, controller=p1)
        three_drop = _TrackingSorcery(name="Three Drop", owner=p1, controller=p1)

        _set_library_top_first(game, p1, [one_drop, land, three_drop])
        p1.choose_yes_no = lambda prompt: True

        capstone.on_resolve(game)

        stack_sources = [obj.source for obj in game.stack.objects()]

        assert len(stack_sources) == 2
        assert set(stack_sources) == {one_drop, three_drop}
        assert game.get_exile(p1).contains(land)
        assert not game.get_exile(p1).contains(one_drop)
        assert not game.get_exile(p1).contains(three_drop)
        assert p1.mana_pool.total() == 0


class TestImprovisationCapstoneParadigm:
    """Paradigm should exile the spell and offer a recurring copy on future first main phases."""

    def test_resolving_the_spell_exiles_it_instead_of_putting_it_into_the_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        set_board_state(game, 0, hand=[capstone], mana=_capstone_mana())
        _cast_and_resolve_capstone(game, p1, capstone)

        assert game.get_exile(p1).contains(capstone)
        assert not game.get_graveyard(p1).contains(capstone)

    def test_paradigm_offers_a_free_copy_only_at_your_next_first_main_phase(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        p1.choose_yes_no = lambda prompt: True
        set_board_state(game, 0, hand=[capstone], mana=_capstone_mana())
        _cast_and_resolve_capstone(game, p1, capstone)

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        assert len(game.stack) == 0

        _advance_to_next_precombat_main(game, p2)
        assert len(game.stack) == 0

        _advance_to_next_precombat_main(game, p1)

        copy_obj = game.stack.peek()
        assert copy_obj is not None
        assert len(game.stack) == 1
        assert copy_obj.source.name == "Improvisation Capstone"
        assert copy_obj.source is not capstone
        assert game.get_exile(p1).contains(capstone)
        assert p1.mana_pool.total() == 0

    def test_you_may_decline_to_cast_the_paradigm_copy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        p1.choose_yes_no = lambda prompt: False
        set_board_state(game, 0, hand=[capstone], mana=_capstone_mana())
        _cast_and_resolve_capstone(game, p1, capstone)

        _advance_to_next_precombat_main(game, p1)

        assert len(game.stack) == 0
        assert game.get_exile(p1).contains(capstone)

    def test_only_the_first_resolution_sets_up_the_recurring_paradigm_copy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        p1.choose_yes_no = lambda prompt: True
        set_board_state(game, 0, hand=[capstone], mana=_capstone_mana())
        _cast_and_resolve_capstone(game, p1, capstone)

        _advance_to_next_precombat_main(game, p1)
        assert len(game.stack) == 1

        first_copy = game.stack.pop()
        first_copy.on_resolve(game)
        assert len(game.stack) == 0

        _advance_to_next_precombat_main(game, p1)
        assert len(game.stack) == 1
