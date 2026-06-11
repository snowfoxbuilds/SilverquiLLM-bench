"""Tests for SOS 174 — Aziza, Mage Tower Captain."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_174.card_impl import AzizaMageTowerCaptain
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase, Supertype, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CreatureTargetingTestInstant(Instant):
    """Simple targeted instant used to exercise spell-copy behavior."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Practice Ping")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game: object) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: object) -> None:
        target = getattr(self, "chosen_targets", [None])[0]
        if isinstance(target, Creature):
            target.damage_marked += 2


class TestAzizaMageTowerCaptainProperties:
    """Static card data should match the SOS 174 spec."""

    def test_is_legendary_djinn_sorcerer_creature(self) -> None:
        card = AzizaMageTowerCaptain(owner=None)

        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Djinn" in card.subtypes
        assert "Sorcerer" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = AzizaMageTowerCaptain(owner=None)

        assert card.name == "Aziza, Mage Tower Captain"
        assert card.mana_cost == ManaCost.parse("{R}{W}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestAzizaMageTowerCaptainSpellCopy:
    """Aziza should copy your instant and sorcery spells by tapping creatures."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AzizaMageTowerCaptain(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_may_decline_tapping_three_creatures_and_leave_only_the_original_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        aziza = AzizaMageTowerCaptain(owner=p1, controller=p1)
        ally_a = Creature(name="Ally A", owner=p1, controller=p1, base_power=1, base_toughness=1)
        ally_b = Creature(name="Ally B", owner=p1, controller=p1, base_power=1, base_toughness=1)
        ally_c = Creature(name="Ally C", owner=p1, controller=p1, base_power=1, base_toughness=1)
        target = Creature(name="Target", owner=p2, controller=p2, base_power=2, base_toughness=2)
        spell = CreatureTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[aziza, ally_a, ally_b, ally_c],
            hand=[spell],
            mana={ManaType.RED: 1},
        )
        set_board_state(game, 1, battlefield=[target])
        aziza.register_triggers(game)
        p1._script.extend([target, False])

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2

        resolve_top(game)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        assert ally_a.is_tapped is False
        assert ally_b.is_tapped is False
        assert ally_c.is_tapped is False

    def test_tapping_three_untapped_creatures_copies_the_spell_and_allows_a_new_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        aziza = AzizaMageTowerCaptain(owner=p1, controller=p1)
        ally_a = Creature(name="Ally A", owner=p1, controller=p1, base_power=1, base_toughness=1)
        ally_b = Creature(name="Ally B", owner=p1, controller=p1, base_power=1, base_toughness=1)
        ally_c = Creature(name="Ally C", owner=p1, controller=p1, base_power=1, base_toughness=1)
        first_target = Creature(name="First Target", owner=p2, controller=p2, base_power=2, base_toughness=2)
        second_target = Creature(name="Second Target", owner=p2, controller=p2, base_power=2, base_toughness=2)
        spell = CreatureTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[aziza, ally_a, ally_b, ally_c],
            hand=[spell],
            mana={ManaType.RED: 1},
        )
        set_board_state(game, 1, battlefield=[first_target, second_target])
        aziza.register_triggers(game)
        p1._script.extend([first_target, True, ally_a, ally_b, ally_c, second_target])

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2

        resolve_top(game)

        assert len(game.stack) == 2
        assert game.stack.peek().source is not spell
        assert ally_a.is_tapped is True
        assert ally_b.is_tapped is True
        assert ally_c.is_tapped is True

        resolve_top(game)
        assert second_target.damage_marked == 2
        assert first_target.damage_marked == 0

        resolve_top(game)
        assert first_target.damage_marked == 2

    def test_without_three_untapped_creatures_it_does_not_copy_the_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        aziza = AzizaMageTowerCaptain(owner=p1, controller=p1)
        ally_a = Creature(name="Ally A", owner=p1, controller=p1, base_power=1, base_toughness=1)
        ally_b = Creature(name="Ally B", owner=p1, controller=p1, base_power=1, base_toughness=1)
        busy_ally = Creature(name="Busy Ally", owner=p1, controller=p1, base_power=1, base_toughness=1)
        busy_ally.is_tapped = True
        target = Creature(name="Target", owner=p2, controller=p2, base_power=2, base_toughness=2)
        spell = CreatureTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[aziza, ally_a, ally_b, busy_ally],
            hand=[spell],
            mana={ManaType.RED: 1},
        )
        set_board_state(game, 1, battlefield=[target])
        aziza.register_triggers(game)
        p1._script.extend([target, True])

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        assert ally_a.is_tapped is False
        assert ally_b.is_tapped is False
        assert busy_ally.is_tapped is True
