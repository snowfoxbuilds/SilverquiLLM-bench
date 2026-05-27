"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.events import AttacksTriggeredEvent
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    Phase,
    Step,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


class TrackingSorcery(Sorcery):
    """Simple graveyard spell used to verify free-cast + exile behavior."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Tracking Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        super().__init__(**kwargs)
        self.resolved = False

    def on_resolve(self, game) -> None:
        self.resolved = True


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_a_legendary_avatar_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes

    def test_has_ten_generic_mana_cost_reach_and_seven_seven_stats(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.mana_cost == ManaCost.parse("{10}")
        assert Keyword.REACH in card.keywords
        assert card.base_power == 7
        assert card.base_toughness == 7


class TestTheDawningArchaicCostReduction:
    """Its self-cost reduction should only count your graveyard's spells."""

    def test_counts_only_instants_and_sorceries_in_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Shock")
        sorcery = Sorcery(name="Divination")
        creature = Creature(name="Runeclaw Bear", base_power=2, base_toughness=2)

        set_board_state(
            game,
            0,
            graveyard=[instant, sorcery, creature],
        )

        assert get_cost_reduction(game, card, p1) == 2

    def test_ignores_instants_and_sorceries_in_opponents_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = TheDawningArchaic(owner=p1, controller=p1)
        your_spell = Instant(name="Your Spell")
        opposing_spell = Sorcery(name="Opposing Spell")

        set_board_state(game, 0, graveyard=[your_spell])
        set_board_state(game, 1, graveyard=[opposing_spell])

        assert get_cost_reduction(game, card, p1) == 1

    def test_reduction_is_clamped_to_the_generic_portion_of_its_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        graveyard_spells = [Instant(name=f"Spell {i}") for i in range(12)]
        set_board_state(game, 0, graveyard=graveyard_spells)

        assert get_cost_reduction(game, card, p1) == 10


class TestTheDawningArchaicAttackTrigger:
    """Attack trigger should cast a graveyard instant/sorcery for free."""

    def test_registers_one_attack_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)

        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent
        assert triggers[0].controller is p1

    def test_other_creatures_attacking_do_not_trigger_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        other_attacker = Creature(
            name="Other Attacker",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=other_attacker, attacker=other_attacker),
        )

        assert game.stack.is_empty()

    def test_trigger_is_a_noop_when_your_graveyard_has_no_instant_or_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        filler = Creature(
            name="Graveyard Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, battlefield=[card], graveyard=[filler])
        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )

        assert len(game.stack) == 1
        game.stack.pop().on_resolve(game)
        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(filler)

    def test_may_decline_to_cast_the_targeted_graveyard_spell(self) -> None:
        spell = Instant(name="Opt")
        game = create_game(scripts=([spell, False], []))
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], graveyard=[spell])
        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(spell)
        assert not p1.zones[Zone.STACK].contains(spell)

    def test_attack_trigger_free_casts_sorcery_from_graveyard_and_exiles_it(self) -> None:
        spell = TrackingSorcery()
        game = create_game(scripts=([spell, True], []))
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        game.phase = Phase.COMBAT
        game.step = Step.DECLARE_ATTACKERS
        set_board_state(game, 0, battlefield=[card], graveyard=[spell])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert len(game.stack) == 1
        cast_spell = game.stack.peek()
        assert cast_spell is not None
        assert cast_spell.source is spell
        assert not game.get_graveyard(p1).contains(spell)

        game.stack.pop().on_resolve(game)

        assert spell.resolved is True
        assert p1.zones[Zone.EXILE].contains(spell)
        assert not game.get_graveyard(p1).contains(spell)
