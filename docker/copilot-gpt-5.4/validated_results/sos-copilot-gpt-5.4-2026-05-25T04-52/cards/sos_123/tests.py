"""Tests for SOS 123 — Magmablood Archaic."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_123.card_impl import MagmabloodArchaic
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class OneColorTestInstant(Instant):
    """Simple instant used to exercise one-color converge rewards."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "One-Color Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)


class ThreeColorTestSorcery(Sorcery):
    """Simple sorcery used to exercise multicolor converge rewards."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Three-Color Test Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{G}{U}"))
        super().__init__(**kwargs)


class TestMagmabloodArchaicProperties:
    """Static card data should match the SOS 123 spec."""

    def test_is_avatar_creature_with_trample_and_reach(self) -> None:
        card = MagmabloodArchaic(owner=None)
        assert isinstance(card, Creature)
        assert "Avatar" in card.subtypes
        assert Keyword.TRAMPLE in card.keywords
        assert Keyword.REACH in card.keywords

    def test_name_mana_value_and_power_toughness(self) -> None:
        card = MagmabloodArchaic(owner=None)
        assert card.name == "Magmablood Archaic"
        assert card.mana_cost.cmc == 6
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_mana_cost_preserves_canonical_two_or_red_hybrid_symbols(self) -> None:
        card = MagmabloodArchaic(owner=None)
        assert card.mana_cost == ManaCost.parse("{2/R}{2/R}{2/R}")
        assert str(card.mana_cost) == "{2/R}{2/R}{2/R}"


class TestMagmabloodArchaicConverge:
    """Magmablood Archaic should enter with counters per color spent."""

    def test_empty_colors_spent_adds_no_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MagmabloodArchaic(owner=p1, controller=p1)

        card.colors_spent = []
        card.on_resolve(game)

        assert card.plus_one_counters == 0
        assert card.power == 2
        assert card.toughness == 2

    def test_three_colors_spent_adds_three_plus_one_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MagmabloodArchaic(owner=p1, controller=p1)

        card.colors_spent = [Color.RED, Color.GREEN, Color.BLUE]
        card.on_resolve(game)

        assert card.plus_one_counters == 3
        assert card.power == 5
        assert card.toughness == 5


class TestMagmabloodArchaicSpellTrigger:
    """Magmablood Archaic should boost your creatures based on spell colors spent."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MagmabloodArchaic(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_a_one_color_instant_gives_your_creatures_plus_one_power_until_end_of_turn(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        archaic = MagmabloodArchaic(owner=p1, controller=p1)
        ally = Creature(
            name="Friendly Assistant",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        enemy = Creature(
            name="Opposing Assistant",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        spell = OneColorTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[archaic, ally],
            hand=[spell],
            mana={ManaType.RED: 1},
        )
        set_board_state(game, 1, battlefield=[enemy])
        archaic.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        resolve_top(game)

        assert archaic.power == 3
        assert ally.power == 3
        assert enemy.power == 2

    def test_casting_a_three_color_spell_gives_your_creatures_plus_three_power_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        archaic = MagmabloodArchaic(owner=p1, controller=p1)
        ally = Creature(
            name="Friendly Assistant",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = ThreeColorTestSorcery(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[archaic, ally],
            hand=[spell],
            mana={ManaType.RED: 1, ManaType.GREEN: 1, ManaType.BLUE: 1},
        )
        archaic.register_triggers(game)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert archaic.power == 5
        assert ally.power == 5

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert archaic.power == 2
        assert ally.power == 2

    def test_casting_a_creature_spell_does_not_trigger_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        archaic = MagmabloodArchaic(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Lecture Hall Cub",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{R}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=[archaic],
            hand=[creature_spell],
            mana={ManaType.RED: 2},
        )
        archaic.register_triggers(game)

        cast_spell_paid(game, p1, creature_spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is creature_spell
