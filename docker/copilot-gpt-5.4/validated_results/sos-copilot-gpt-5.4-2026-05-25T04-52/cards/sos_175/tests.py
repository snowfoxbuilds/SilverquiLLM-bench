"""Tests for SOS 175 — Berta, Wise Extrapolator."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_175.card_impl import BertaWiseExtrapolator
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature, Sorcery
from benchmarks.sos.workspace.engine.events import CounterAddedTriggeredEvent, SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, ManaCost, ManaType, Supertype
from benchmarks.sos.workspace.tests.test_utils import cast_spell, create_game, set_board_state


class TwoManaTestSorcery(Sorcery):
    """Two-mana sorcery used to exercise Increment."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Two-Mana Test Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        super().__init__(**kwargs)


class TestBertaWiseExtrapolatorProperties:
    """Static card data should match the SOS 175 spec."""

    def test_is_legendary_frog_druid_creature(self) -> None:
        card = BertaWiseExtrapolator(owner=None)

        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Frog" in card.subtypes
        assert "Druid" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = BertaWiseExtrapolator(owner=None)

        assert card.name == "Berta, Wise Extrapolator"
        assert card.mana_cost == ManaCost.parse("{2}{G}{U}")
        assert card.base_power == 1
        assert card.base_toughness == 4


class TestBertaWiseExtrapolatorTriggers:
    """Berta should grow from Increment and make mana from +1/+1 counters."""

    def test_registers_spell_cast_and_counter_added_triggers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BertaWiseExtrapolator(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 2
        assert {trigger.event_type for trigger in triggers} == {
            SpellCastTriggeredEvent,
            CounterAddedTriggeredEvent,
        }

    def test_casting_a_two_mana_spell_adds_a_plus_one_plus_one_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = TwoManaTestSorcery(owner=p1, controller=p1)
        card = BertaWiseExtrapolator(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )
        card.register_triggers(game)

        cast_spell(game, 0, "Two-Mana Test Sorcery")

        assert card.plus_one_counters == 1

    def test_plus_one_plus_one_counters_added_to_berta_add_only_one_mana_of_the_chosen_color(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BertaWiseExtrapolator(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        p1._script.append(ManaType.RED)
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            CounterAddedTriggeredEvent(
                permanent=card,
                counter_type="+1/+1",
                amount=2,
            ),
        )

        assert len(game.stack) == 1

        resolve_top(game)

        assert p1.mana_pool.get(ManaType.RED) == 1
        assert p1.mana_pool.total() == 1


class TestBertaWiseExtrapolatorActivatedAbility:
    """Berta should tap and spend X to make an X-sized Fractal token."""

    def test_has_a_single_activated_ability(self) -> None:
        abilities = BertaWiseExtrapolator(owner=None).get_activated_abilities()

        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_cost_spends_x_mana_and_taps_berta(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BertaWiseExtrapolator(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[card],
            mana={ManaType.COLORLESS: 3},
        )
        card.x_value = 3  # type: ignore[attr-defined]
        ability = card.get_activated_abilities()[0]

        assert ability.cost(game, card) is True
        assert card.is_tapped is True
        assert p1.mana_pool.total() == 0

    def test_effect_creates_a_green_and_blue_fractal_with_x_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BertaWiseExtrapolator(owner=p1, controller=p1)
        card.x_value = 3  # type: ignore[attr-defined]
        ability = card.get_activated_abilities()[0]

        ability.effect(game)

        tokens = [
            permanent
            for permanent in game.get_battlefield(p1).get_all()
            if getattr(permanent, "is_token", False)
        ]
        assert len(tokens) == 1
        token = tokens[0]
        assert isinstance(token, Creature)
        assert "Fractal" in token.subtypes
        assert get_colors(token) == {Color.GREEN, Color.BLUE}
        assert token.plus_one_counters == 3
        assert token.power == 3
        assert token.toughness == 3
