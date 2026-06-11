"""Tests for SOS 168 — Wildgrowth Archaic."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_168.card_impl import WildgrowthArchaic
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class ThreeColorTestCreature(Creature):
    """Creature spell used to exercise multicolor converge rewards."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Three-Color Test Creature")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{G}{U}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)


class CheapTestInstant(Instant):
    """Noncreature spell used to confirm the trigger is creature-only."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Cheap Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        super().__init__(**kwargs)


class TestWildgrowthArchaicProperties:
    """Static card data should match the SOS 168 spec."""

    def test_is_avatar_creature_with_trample_and_reach(self) -> None:
        card = WildgrowthArchaic(owner=None)

        assert isinstance(card, Creature)
        assert "Avatar" in card.subtypes
        assert Keyword.TRAMPLE in card.keywords
        assert Keyword.REACH in card.keywords

    def test_name_mana_cost_and_power_toughness(self) -> None:
        card = WildgrowthArchaic(owner=None)

        assert card.name == "Wildgrowth Archaic"
        assert card.mana_cost == ManaCost.parse("{2/G}{2/G}")
        assert card.base_power == 0
        assert card.base_toughness == 0


class TestWildgrowthArchaicConverge:
    """Wildgrowth Archaic should enter with counters per color spent."""

    def test_empty_colors_spent_adds_no_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WildgrowthArchaic(owner=p1, controller=p1)

        card.colors_spent = []
        card.on_resolve(game)

        assert card.plus_one_counters == 0
        assert card.power == 0
        assert card.toughness == 0

    def test_duplicate_colors_spent_only_count_once_for_enters_with_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WildgrowthArchaic(owner=p1, controller=p1)

        card.colors_spent = [Color.GREEN, Color.GREEN, Color.BLUE]
        card.on_resolve(game)

        assert card.plus_one_counters == 2
        assert card.power == 2
        assert card.toughness == 2


class TestWildgrowthArchaicCreatureSpellTrigger:
    """Wildgrowth Archaic should reward creature spells based on colors spent."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WildgrowthArchaic(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_a_three_color_creature_spell_makes_that_creature_enter_with_three_additional_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        archaic = WildgrowthArchaic(owner=p1, controller=p1)
        creature_spell = ThreeColorTestCreature(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[archaic],
            hand=[creature_spell],
            mana={ManaType.RED: 1, ManaType.GREEN: 1, ManaType.BLUE: 1},
        )
        archaic.register_triggers(game)

        cast_spell_paid(game, p1, creature_spell)

        assert len(game.stack) == 2
        resolve_top(game)
        assert len(game.stack) == 1
        assert game.stack.peek().source is creature_spell

        resolve_top(game)

        assert game.get_battlefield(p1).contains(creature_spell)
        assert creature_spell.plus_one_counters == 3
        assert creature_spell.power == 5
        assert creature_spell.toughness == 5

    def test_casting_a_noncreature_spell_does_not_trigger_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        archaic = WildgrowthArchaic(owner=p1, controller=p1)
        spell = CheapTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[archaic],
            hand=[spell],
            mana={ManaType.GREEN: 1},
        )
        archaic.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        resolve_top(game)
        assert game.get_graveyard(p1).contains(spell)
        assert archaic.plus_one_counters == 0
