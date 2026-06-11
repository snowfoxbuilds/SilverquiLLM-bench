"""Tests for SOS 113 — Emeritus of Conflict // Lightning Bolt."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_113.card_impl import EmeritusOfConflictLightningBolt
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CheapTestInstant(Instant):
    """Simple instant used to drive third-spell trigger tests."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Cheap Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)


class TestEmeritusOfConflictLightningBoltProperties:
    """Static front-face data should match the SOS 113 spec."""

    def test_is_human_wizard_creature_with_first_strike(self) -> None:
        card = EmeritusOfConflictLightningBolt(owner=None)
        assert isinstance(card, Creature)
        assert "Human" in card.subtypes
        assert "Wizard" in card.subtypes
        assert Keyword.FIRST_STRIKE in card.keywords

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = EmeritusOfConflictLightningBolt(owner=None)
        assert card.name == "Emeritus of Conflict"
        assert card.mana_cost == ManaCost.parse("{1}{R}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestEmeritusOfConflictLightningBoltPrepared:
    """Emeritus of Conflict should use the prepared-state contract."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfConflictLightningBolt(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_becomes_prepared_on_your_third_spell_each_turn_not_before(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = EmeritusOfConflictLightningBolt(owner=p1, controller=p1)
        spell_a = CheapTestInstant(owner=p1, controller=p1)
        spell_b = CheapTestInstant(owner=p1, controller=p1)
        spell_c = CheapTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell_a, spell_b, spell_c],
            mana={ManaType.RED: 3},
        )
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell_a)
        assert card.is_prepared is False
        resolve_top(game)

        cast_spell_paid(game, p1, spell_b)
        assert card.is_prepared is False
        resolve_top(game)

        cast_spell_paid(game, p1, spell_c)

        assert len(game.stack) == 2
        resolve_top(game)

        assert card.is_prepared is True

    def test_prepared_spell_copy_is_lightning_bolt_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfConflictLightningBolt(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()
        p1._script.append(p2)

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Lightning Bolt"
        assert isinstance(stack_obj.source, Instant)
        assert stack_obj.source.mana_cost == ManaCost.parse("{R}")
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_lightning_bolt_copy_deals_three_damage_to_a_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Study Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p2).add(target)
        card = EmeritusOfConflictLightningBolt(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()
        p1._script.append(target)

        card.cast_prepared_spell_copy(game)
        resolve_top(game)

        assert target.damage_marked == 3

    def test_lightning_bolt_copy_can_target_a_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfConflictLightningBolt(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()
        before_life = p2.life
        p1._script.append(p2)

        card.cast_prepared_spell_copy(game)
        resolve_top(game)

        assert p2.life == before_life - 3
