"""Tests for SOS 42 — Deluge Virtuoso."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_42.card_impl import DelugeVirtuoso
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CheapTestInstant(Instant):
    """Simple instant used to exercise Opus triggers."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Cheap Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class FiveManaTestSorcery(Sorcery):
    """Simple sorcery with mana value five for Opus trigger tests."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Five-Mana Test Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}"))
        super().__init__(**kwargs)


class TestDelugeVirtuosoProperties:
    """Static card data should match the SOS 42 spec."""

    def test_is_human_wizard_creature(self) -> None:
        card = DelugeVirtuoso(owner=None)
        assert isinstance(card, Creature)
        assert "Human" in card.subtypes
        assert "Wizard" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = DelugeVirtuoso(owner=None)
        assert card.name == "Deluge Virtuoso"
        assert card.mana_cost == ManaCost.parse("{2}{U}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestDelugeVirtuosoTargeting:
    """The ETB effect should target a creature an opponent controls."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = DelugeVirtuoso(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_only_an_opponents_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        req = DelugeVirtuoso(owner=p1, controller=p1).get_targets(game)[0]

        friendly_creature = Creature(
            name="Friendly Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opposing_creature = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        assert req.filter_fn(friendly_creature) is False
        assert req.filter_fn(opposing_creature) is True


class TestDelugeVirtuosoResolution:
    """Deluge Virtuoso should tap and stun its chosen ETB target."""

    def test_on_resolve_taps_the_chosen_target_and_adds_a_stun_counter(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p2).add(target)
        card = DelugeVirtuoso(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.on_resolve(game)

        assert target.is_tapped is True
        assert getattr(target, "counters", {}).get("stun", 0) == 1


class TestDelugeVirtuosoOpus:
    """Deluge Virtuoso should reward instant and sorcery casts with a temporary boost."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = DelugeVirtuoso(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_an_instant_gives_plus_one_plus_one_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = DelugeVirtuoso(owner=p1, controller=p1)
        spell = CheapTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert card.power == 3
        assert card.toughness == 3

    def test_granted_plus_one_plus_one_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = DelugeVirtuoso(owner=p1, controller=p1)
        spell = CheapTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert card.power == 3
        assert card.toughness == 3

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert card.power == 2
        assert card.toughness == 2

    def test_casting_a_five_mana_sorcery_gives_plus_two_plus_two_instead(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = DelugeVirtuoso(owner=p1, controller=p1)
        spell = FiveManaTestSorcery(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.BLUE: 5},
        )
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert card.power == 4
        assert card.toughness == 4

    def test_casting_a_non_instant_non_sorcery_spell_does_not_trigger_opus(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = DelugeVirtuoso(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Lecture Hall Cub",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{U}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[creature_spell],
            mana={ManaType.BLUE: 2},
        )
        card.register_triggers(game)

        cast_spell_paid(game, p1, creature_spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is creature_spell
