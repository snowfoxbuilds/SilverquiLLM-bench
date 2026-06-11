"""Tests for SOS 151 — Hungry Graffalon."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_151.card_impl import HungryGraffalon
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import cast_spell, create_game, set_board_state


class FourManaTestSorcery(Sorcery):
    """Four-mana sorcery used to exercise Increment."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Four-Mana Test Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        super().__init__(**kwargs)


class TestHungryGraffalonProperties:
    """Static card data should match the SOS 151 spec."""

    def test_is_giraffe_creature_with_reach(self) -> None:
        card = HungryGraffalon(owner=None)

        assert isinstance(card, Creature)
        assert "Giraffe" in card.subtypes
        assert Keyword.REACH in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = HungryGraffalon(owner=None)

        assert card.name == "Hungry Graffalon"
        assert card.mana_cost == ManaCost.parse("{3}{G}")
        assert card.base_power == 3
        assert card.base_toughness == 4


class TestHungryGraffalonIncrement:
    """Hungry Graffalon should grow from qualifying spells."""

    def test_casting_a_four_mana_spell_adds_a_plus_one_plus_one_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = FourManaTestSorcery(owner=p1, controller=p1)
        card = HungryGraffalon(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 3},
        )
        card.register_triggers(game)

        cast_spell(game, 0, "Four-Mana Test Sorcery")

        assert card.plus_one_counters == 1
        assert game.get_graveyard(p1).contains(spell)

    def test_casting_a_four_mana_spell_does_not_trigger_increment_once_it_is_a_four_five(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = FourManaTestSorcery(owner=p1, controller=p1)
        card = HungryGraffalon(owner=p1, controller=p1)
        card.plus_one_counters = 1
        card._base_plus_one_counters = 1
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 3},
        )
        card.register_triggers(game)

        cast_spell(game, 0, "Four-Mana Test Sorcery")

        assert card.plus_one_counters == 1
        assert card.power == 4
        assert card.toughness == 5
