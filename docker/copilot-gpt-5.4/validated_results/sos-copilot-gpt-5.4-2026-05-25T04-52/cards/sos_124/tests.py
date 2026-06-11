"""Tests for SOS 124 — Mica, Reader of Ruins."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_124.card_impl import MicaReaderOfRuins
from benchmarks.sos.workspace.engine.card import Artifact, Creature, Instant
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, Phase, Supertype, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CreatureTargetingTestInstant(Instant):
    """Simple targeted instant used to exercise ward and spell-copy behavior."""

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


class TestMicaReaderOfRuinsProperties:
    """Static card data should match the SOS 124 spec."""

    def test_is_legendary_human_artificer_with_ward(self) -> None:
        card = MicaReaderOfRuins(owner=None)
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Human" in card.subtypes
        assert "Artificer" in card.subtypes
        assert Keyword.WARD in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = MicaReaderOfRuins(owner=None)
        assert card.name == "Mica, Reader of Ruins"
        assert card.mana_cost == ManaCost.parse("{3}{R}")
        assert card.base_power == 4
        assert card.base_toughness == 4


class TestMicaReaderOfRuinsWard:
    """Mica should enforce Ward—Pay 3 life."""

    def test_opponents_targeting_spell_is_countered_when_they_cannot_pay_three_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        mica = MicaReaderOfRuins(owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p2, controller=p2)
        p2.life = 2

        set_board_state(game, 0, battlefield=[mica])
        set_board_state(game, 1, hand=[spell], mana={ManaType.RED: 1})
        p2._script.append(mica)

        cast_spell_paid(game, p2, spell)

        assert len(game.stack) == 2
        resolve_top(game)

        assert getattr(spell, "last_ward_outcome", None) == "countered"
        assert game.get_graveyard(p2).contains(spell)
        assert game.stack.is_empty()

    def test_opponent_may_pay_three_life_to_keep_their_spell_on_the_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        mica = MicaReaderOfRuins(owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[mica])
        set_board_state(game, 1, hand=[spell], mana={ManaType.RED: 1})
        p2._script.extend([mica, True])

        cast_spell_paid(game, p2, spell)

        assert len(game.stack) == 2
        resolve_top(game)

        assert getattr(spell, "last_ward_outcome", None) == "paid"
        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        assert p2.life == 17


class TestMicaReaderOfRuinsSpellCopy:
    """Mica should copy your instant and sorcery spells if you sacrifice an artifact."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MicaReaderOfRuins(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_may_decline_the_artifact_sacrifice_and_leave_only_the_original_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        mica = MicaReaderOfRuins(owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p1, controller=p1)
        target = Creature(
            name="Target Creature",
            owner=game.players[1],
            controller=game.players[1],
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=[mica],
            hand=[spell],
            mana={ManaType.RED: 1},
        )
        set_board_state(game, 1, battlefield=[target])
        mica.register_triggers(game)
        p1._script.extend([target, False])

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        resolve_top(game)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell

    def test_sacrificing_an_artifact_copies_the_spell_and_allows_a_new_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        mica = MicaReaderOfRuins(owner=p1, controller=p1)
        relic = Artifact(name="Spare Relic", owner=p1, controller=p1)
        first_target = Creature(
            name="First Target",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        second_target = Creature(
            name="Second Target",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        spell = CreatureTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[mica, relic],
            hand=[spell],
            mana={ManaType.RED: 1},
        )
        set_board_state(game, 1, battlefield=[first_target, second_target])
        mica.register_triggers(game)
        p1._script.extend([first_target, True, relic, second_target])

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        resolve_top(game)

        assert len(game.stack) == 2
        assert game.stack.peek().source is not spell
        assert game.get_graveyard(p1).contains(relic)

        resolve_top(game)
        assert second_target.damage_marked == 2
        assert first_target.damage_marked == 0

        resolve_top(game)
        assert first_target.damage_marked == 2
