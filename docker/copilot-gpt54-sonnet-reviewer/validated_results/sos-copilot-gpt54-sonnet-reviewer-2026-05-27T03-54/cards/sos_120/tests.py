"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Land, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, Color, ManaCost, ManaType, Phase
from test_utils import cast_spell, create_game, set_board_state


class TestLibrarySpell(Sorcery):
    """Simple sorcery used as an exiled free-cast target in Capstone tests."""

    def __init__(self, *, name: str, mana_cost: str, life_gain: int = 0) -> None:
        super().__init__(name=name, mana_cost=ManaCost.parse(mana_cost))
        self.life_gain = life_gain
        self.resolved = False

    def on_resolve(self, game) -> None:
        self.resolved = True
        if self.controller is not None:
            self.controller.life += self.life_gain


class TestLibraryLand(Land):
    """Simple land used to verify that non-spells are only exiled, not cast."""

    def __init__(self, *, name: str = "Practice Campus") -> None:
        super().__init__(name=name)


def _load_library(game, player, *cards) -> None:
    """Load *cards* into *player*'s library in bottom-to-top order."""
    library = game.get_library(player)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_is_red_lesson_sorcery_with_expected_cost_rules_text_and_paradigm_keyword(self) -> None:
        card = ImprovisationCapstone(owner=None)

        assert isinstance(card, Sorcery)
        assert card.name == "Improvisation Capstone"
        assert CardType.SORCERY in card.card_types
        assert "Lesson" in card.subtypes
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert card.colors == {Color.RED}
        assert card.color_identity == {Color.RED}
        assert card.non_evergreen_keywords == {"Paradigm"}
        assert card.rules_text == (
            "Exile cards from the top of your library until you exile cards "
            "with total mana value 4 or greater. You may cast any number of "
            "spells from among them without paying their mana costs.\n"
            "Paradigm (Then exile this spell. After you first resolve a spell "
            "with this name, you may cast a copy of it from exile without "
            "paying its mana cost at the beginning of each of your first main "
            "phases.)"
        )


class TestImprovisationCapstoneResolution:
    """Resolution should exile enough cards, optionally free-cast spells, and exile itself."""

    def test_exiles_from_the_top_until_total_mana_value_reaches_four_then_stops(self) -> None:
        game = create_game(scripts=([False, False], []))
        player = game.players[0]
        capstone = ImprovisationCapstone(owner=player, controller=player)
        untouched = TestLibrarySpell(name="Held Back", mana_cost="{2}")
        four_total = TestLibrarySpell(name="Big Finish", mana_cost="{3}")
        one_total = TestLibrarySpell(name="Warmup", mana_cost="{1}")
        land = TestLibraryLand()

        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        _load_library(game, player, untouched, four_total, one_total, land)

        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_exile(player).contains(land)
        assert game.get_exile(player).contains(one_total)
        assert game.get_exile(player).contains(four_total)
        assert not game.get_exile(player).contains(untouched)
        assert game.get_library(player).contains(untouched)
        assert game.get_exile(player).contains(capstone)

    def test_exiles_the_entire_library_if_total_mana_value_never_reaches_four(self) -> None:
        game = create_game(scripts=([False, False], []))
        player = game.players[0]
        capstone = ImprovisationCapstone(owner=player, controller=player)
        first = TestLibrarySpell(name="First Draft", mana_cost="{1}")
        second = TestLibrarySpell(name="Second Draft", mana_cost="{1}")

        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        _load_library(game, player, first, second)

        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_library(player).get_all() == []
        assert game.get_exile(player).contains(first)
        assert game.get_exile(player).contains(second)
        assert game.get_exile(player).contains(capstone)

    def test_may_cast_multiple_exiled_spells_without_paying_their_mana_costs(self) -> None:
        game = create_game(scripts=([True, True], []))
        player = game.players[0]
        capstone = ImprovisationCapstone(owner=player, controller=player)
        first = TestLibrarySpell(name="Final Rehearsal", mana_cost="{1}{R}", life_gain=2)
        second = TestLibrarySpell(name="Encore", mana_cost="{1}{R}", life_gain=3)

        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        _load_library(game, player, first, second)

        cast_spell(game, 0, "Improvisation Capstone")

        assert first.resolved is True
        assert second.resolved is True
        assert player.life == 25
        assert game.get_graveyard(player).contains(first)
        assert game.get_graveyard(player).contains(second)
        assert not game.get_exile(player).contains(first)
        assert not game.get_exile(player).contains(second)
        assert game.get_exile(player).contains(capstone)


class TestImprovisationCapstoneParadigm:
    """Paradigm should recur only from your first main phase after the first resolution."""

    def test_paradigm_only_triggers_during_your_first_main_phase(self) -> None:
        game = create_game(scripts=([False], []))
        player = game.players[0]
        opponent = game.players[1]
        capstone = ImprovisationCapstone(owner=player, controller=player)

        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        game.phase = Phase.POSTCOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=player),
        )
        assert game.stack.is_empty()

        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 1
        game.priority_player_index = 1
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=opponent),
        )
        assert game.stack.is_empty()

        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=player),
        )

        assert len(game.stack) == 1
        trigger = game.stack.pop()
        trigger.on_resolve(game)
        assert game.stack.is_empty()

    def test_paradigm_may_cast_a_copy_from_exile_on_your_first_main_phase(self) -> None:
        game = create_game(scripts=([True, False], []))
        player = game.players[0]
        capstone = ImprovisationCapstone(owner=player, controller=player)
        copied_payload = TestLibrarySpell(name="Copied Payload", mana_cost="{4}")

        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        cast_spell(game, 0, "Improvisation Capstone")
        _load_library(game, player, copied_payload)

        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=player),
        )

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        copy_obj = game.stack.peek()
        assert copy_obj is not None
        assert copy_obj.source is not capstone
        assert copy_obj.source.name == "Improvisation Capstone"
        assert getattr(copy_obj.source, "is_spell_copy", False) is True

        copy_obj = game.stack.pop()
        copy_obj.on_resolve(game)

        assert game.get_exile(player).contains(capstone)
        assert game.get_exile(player).contains(copied_payload)
        assert not game.get_library(player).contains(copied_payload)

    def test_only_the_first_resolved_spell_with_this_name_creates_one_recurring_paradigm_trigger(self) -> None:
        game = create_game(scripts=([False, False], []))
        player = game.players[0]
        first_capstone = ImprovisationCapstone(owner=player, controller=player)
        second_capstone = ImprovisationCapstone(owner=player, controller=player)

        set_board_state(
            game,
            0,
            hand=[first_capstone, second_capstone],
            mana={ManaType.COLORLESS: 10, ManaType.RED: 4},
        )

        cast_spell(game, 0, "Improvisation Capstone")
        cast_spell(game, 0, "Improvisation Capstone")

        for turn_number in (2, 4):
            game.turn_number = turn_number
            game.phase = Phase.PRECOMBAT_MAIN
            game.step = None
            game.active_player_index = 0
            game.priority_player_index = 0
            game.trigger_manager.fire_event(
                game,
                BeginningOfMainPhaseTriggeredEvent(player=player),
            )

            assert len(game.stack) == 1
            trigger = game.stack.pop()
            trigger.on_resolve(game)
            assert game.stack.is_empty()
