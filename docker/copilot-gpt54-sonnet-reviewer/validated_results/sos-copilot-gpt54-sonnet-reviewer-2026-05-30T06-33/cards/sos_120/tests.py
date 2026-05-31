"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state

ORACLE_TEXT = (
    "Exile cards from the top of your library until you exile cards with total "
    "mana value 4 or greater. You may cast any number of spells from among "
    "them without paying their mana costs.\n"
    "Paradigm (Then exile this spell. After you first resolve a spell with "
    "this name, you may cast a copy of it from exile without paying its mana "
    "cost at the beginning of each of your first main phases.)"
)


class TestBurst(Instant):
    """Simple instant that records resolution via life gain."""

    def __init__(self, *, name: str, mana_cost: str, life_gain: int = 1, **kwargs) -> None:
        kwargs.setdefault("name", name)
        kwargs.setdefault("mana_cost", ManaCost.parse(mana_cost))
        super().__init__(**kwargs)
        self.life_gain = life_gain
        self.was_resolved = False

    def on_resolve(self, game) -> None:
        self.was_resolved = True
        if self.controller is not None:
            self.controller.life += self.life_gain


class TestWorkshopGolem(Creature):
    """Simple creature used to verify free casts of permanents."""

    def __init__(self, *, name: str, mana_cost: str, **kwargs) -> None:
        kwargs.setdefault("name", name)
        kwargs.setdefault("mana_cost", ManaCost.parse(mana_cost))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)


def _set_library(player, cards_bottom_to_top) -> None:
    library = player.zones[Zone.LIBRARY]
    for card in library.get_all():
        library.remove(card)
    for card in cards_bottom_to_top:
        card.owner = player
        card.controller = player
        library.add(card)


def _resolve_top_of_stack(game) -> None:
    obj = game.stack.pop()
    obj.on_resolve(game)


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        _resolve_top_of_stack(game)


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(ImprovisationCapstone(owner=None), Sorcery)

    def test_name_mana_cost_lesson_and_rules_text(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert "Lesson" in card.subtypes
        assert card.rules_text == ORACLE_TEXT


class TestImprovisationCapstoneResolution:
    """Resolution should exile cards correctly and free-cast eligible spells."""

    def test_exiles_until_total_mana_value_four_or_more_and_stops(self, monkeypatch) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        one_drop = TestBurst(name="One Drop", mana_cost="{1}")
        three_drop = TestWorkshopGolem(name="Three Drop", mana_cost="{3}")
        untouched = TestBurst(name="Untouched", mana_cost="{5}")

        _set_library(p1, [untouched, three_drop, one_drop])
        set_board_state(game, 0, hand=[capstone], mana={ManaType.COLORLESS: 7})
        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: False)

        cast_spell(game, 0, "Improvisation Capstone")

        assert p1.zones[Zone.EXILE].contains(capstone)
        assert p1.zones[Zone.EXILE].contains(one_drop)
        assert p1.zones[Zone.EXILE].contains(three_drop)
        assert not p1.zones[Zone.EXILE].contains(untouched)
        assert p1.zones[Zone.LIBRARY].contains(untouched)
        assert not p1.zones[Zone.GRAVEYARD].contains(capstone)

    def test_exiles_entire_library_if_total_never_reaches_four(self, monkeypatch) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        first = TestBurst(name="First", mana_cost="{1}")
        second = TestBurst(name="Second", mana_cost="{1}")

        _set_library(p1, [second, first])
        set_board_state(game, 0, hand=[capstone], mana={ManaType.COLORLESS: 7})
        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: False)

        cast_spell(game, 0, "Improvisation Capstone")

        assert p1.zones[Zone.EXILE].contains(first)
        assert p1.zones[Zone.EXILE].contains(second)
        assert len(p1.zones[Zone.LIBRARY].get_all()) == 0

    def test_may_cast_multiple_exiled_spells_without_paying_mana_cost(self, monkeypatch) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        burst = TestBurst(name="Capstone Burst", mana_cost="{1}", life_gain=4)
        golem = TestWorkshopGolem(name="Studio Golem", mana_cost="{3}")
        untouched = TestBurst(name="Library Sentinel", mana_cost="{5}")

        _set_library(p1, [untouched, golem, burst])
        set_board_state(game, 0, hand=[capstone], mana={ManaType.COLORLESS: 7})
        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: True)

        cast_spell(game, 0, "Improvisation Capstone")

        assert burst.was_resolved is True
        assert p1.life == 24
        assert p1.zones[Zone.BATTLEFIELD].contains(golem)
        assert p1.zones[Zone.LIBRARY].contains(untouched)
        assert p1.mana_pool.total() == 0

    def test_nonspell_cards_among_the_exiled_cards_stay_in_exile(self, monkeypatch) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        lesson_land = Land(name="Practice Campus")
        burst = TestBurst(name="Capstone Reward", mana_cost="{4}", life_gain=4)

        _set_library(p1, [burst, lesson_land])
        set_board_state(game, 0, hand=[capstone], mana={ManaType.COLORLESS: 7})
        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: True)

        cast_spell(game, 0, "Improvisation Capstone")

        assert burst.was_resolved is True
        assert p1.life == 24
        assert p1.zones[Zone.EXILE].contains(lesson_land)
        assert not p1.zones[Zone.BATTLEFIELD].contains(lesson_land)


class TestImprovisationCapstoneParadigm:
    """Paradigm should exile the spell and offer recurring precombat casts."""

    def test_paradigm_only_triggers_on_your_first_main_phase(self, monkeypatch) -> None:
        game = create_game()
        p1, p2 = game.players
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        set_board_state(game, 0, hand=[capstone], mana={ManaType.COLORLESS: 7})
        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: False)
        cast_spell(game, 0, "Improvisation Capstone")

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p2, phase=Phase.PRECOMBAT_MAIN),
        )
        assert game.stack.is_empty()

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.POSTCOMBAT_MAIN),
        )
        assert game.stack.is_empty()

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )
        assert len(game.stack) == 1

    def test_paradigm_copy_may_be_declined(self, monkeypatch) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        future_spell = TestBurst(name="Deferred Burst", mana_cost="{4}", life_gain=4)

        set_board_state(game, 0, hand=[capstone], mana={ManaType.COLORLESS: 7})
        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: False)
        cast_spell(game, 0, "Improvisation Capstone")
        _set_library(p1, [future_spell])

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )
        assert len(game.stack) == 1

        _resolve_top_of_stack(game)

        assert game.stack.is_empty()
        assert p1.zones[Zone.LIBRARY].contains(future_spell)
        assert p1.life == 20

    def test_resolving_the_paradigm_copy_does_not_create_duplicate_future_triggers(
        self, monkeypatch
    ) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        set_board_state(game, 0, hand=[capstone], mana={ManaType.COLORLESS: 7})
        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: True)
        cast_spell(game, 0, "Improvisation Capstone")

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )
        assert len(game.stack) == 1

        _resolve_top_of_stack(game)

        copy_obj = game.stack.peek()
        assert copy_obj is not None
        assert copy_obj.source is not capstone
        assert copy_obj.source.name == "Improvisation Capstone"
        assert p1.zones[Zone.EXILE].contains(capstone)

        _resolve_all(game)

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )
        assert len(game.stack) == 1
