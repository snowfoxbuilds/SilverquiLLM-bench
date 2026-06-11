"""Tests for SOS 114 — Expressive Firedancer."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_114.card_impl import ExpressiveFiredancer
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CheapTestInstant(Instant):
    """Simple instant used to exercise Opus triggers."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Cheap Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)


class FiveManaTestSorcery(Sorcery):
    """Simple sorcery used to exercise the five-mana threshold."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Five-Mana Test Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        super().__init__(**kwargs)


class TestExpressiveFiredancerProperties:
    """Static card data should match the SOS 114 spec."""

    def test_is_human_sorcerer_creature(self) -> None:
        card = ExpressiveFiredancer(owner=None)
        assert isinstance(card, Creature)
        assert "Human" in card.subtypes
        assert "Sorcerer" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = ExpressiveFiredancer(owner=None)
        assert card.name == "Expressive Firedancer"
        assert card.mana_cost == ManaCost.parse("{1}{R}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestExpressiveFiredancerOpus:
    """Expressive Firedancer should reward instant and sorcery casts."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ExpressiveFiredancer(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_an_instant_gives_plus_one_plus_one_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = ExpressiveFiredancer(owner=p1, controller=p1)
        spell = CheapTestInstant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[spell], mana={ManaType.RED: 1})
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        resolve_top(game)

        assert card.power == 3
        assert card.toughness == 3
        assert Keyword.DOUBLE_STRIKE not in card.keywords

    def test_granted_plus_one_plus_one_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = ExpressiveFiredancer(owner=p1, controller=p1)
        spell = CheapTestInstant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[spell], mana={ManaType.RED: 1})
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)
        assert card.power == 3
        assert card.toughness == 3

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert card.power == 2
        assert card.toughness == 2

    def test_five_or_more_mana_spell_also_grants_double_strike_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = ExpressiveFiredancer(owner=p1, controller=p1)
        spell = FiveManaTestSorcery(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[spell], mana={ManaType.RED: 5})
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert card.power == 3
        assert card.toughness == 3
        assert Keyword.DOUBLE_STRIKE in card.keywords

    def test_granted_double_strike_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = ExpressiveFiredancer(owner=p1, controller=p1)
        spell = FiveManaTestSorcery(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[spell], mana={ManaType.RED: 5})
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)
        assert Keyword.DOUBLE_STRIKE in card.keywords

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert Keyword.DOUBLE_STRIKE not in card.keywords

    def test_casting_a_noninstant_nonsorcery_spell_does_not_trigger_opus(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = ExpressiveFiredancer(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Lecture Hall Cub",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{R}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, battlefield=[card], hand=[creature_spell], mana={ManaType.RED: 2})
        card.register_triggers(game)

        cast_spell_paid(game, p1, creature_spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is creature_spell
