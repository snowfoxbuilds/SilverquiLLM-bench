"""Tests for SOS 183 — Cuboid Colony."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_183.card_impl import CuboidColony
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import cast_spell, create_game, set_board_state


class TwoManaTestSorcery(Sorcery):
    """Two-mana sorcery used to exercise Increment."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Two-Mana Test Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        super().__init__(**kwargs)


class TestCuboidColonyProperties:
    """Static card data should match the SOS 183 spec."""

    def test_is_insect_with_flash_flying_and_trample(self) -> None:
        card = CuboidColony(owner=None)

        assert isinstance(card, Creature)
        assert "Insect" in card.subtypes
        assert Keyword.FLASH in card.keywords
        assert Keyword.FLYING in card.keywords
        assert Keyword.TRAMPLE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = CuboidColony(owner=None)

        assert card.name == "Cuboid Colony"
        assert card.mana_cost == ManaCost.parse("{G}{U}")
        assert card.base_power == 1
        assert card.base_toughness == 1


class TestCuboidColonyIncrement:
    """Cuboid Colony should grow from qualifying spells."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CuboidColony(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_a_two_mana_spell_adds_a_plus_one_plus_one_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = TwoManaTestSorcery(owner=p1, controller=p1)
        card = CuboidColony(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1},
        )
        card.register_triggers(game)

        cast_spell(game, 0, "Two-Mana Test Sorcery")

        assert card.plus_one_counters == 1
        assert game.get_graveyard(p1).contains(spell)

    def test_casting_a_two_mana_spell_does_not_trigger_increment_once_it_is_two_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = TwoManaTestSorcery(owner=p1, controller=p1)
        card = CuboidColony(owner=p1, controller=p1)
        card.plus_one_counters = 1
        card._base_plus_one_counters = 1
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1},
        )
        card.register_triggers(game)

        cast_spell(game, 0, "Two-Mana Test Sorcery")

        assert card.plus_one_counters == 1
        assert card.power == 2
        assert card.toughness == 2
