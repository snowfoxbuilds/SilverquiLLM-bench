"""Tests for SOS 20 — Informed Inkwright."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_20.card_impl import InformedInkwright
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, ManaType, Phase, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CreatureTargetingTestSorcery(Sorcery):
    """Simple sorcery used to exercise repartee-style triggers."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Creature Targeting Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)

    def get_targets(self, game: object) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]


class NonTargetingTestInstant(Instant):
    """Instant with no targets so repartee should not trigger."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Non-Targeting Test Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)


class TestInformedInkwrightProperties:
    """Static card data should match the SOS 20 spec."""

    def test_is_human_wizard_creature_with_vigilance(self) -> None:
        card = InformedInkwright(owner=None)
        assert isinstance(card, Creature)
        assert "Human" in card.subtypes
        assert "Wizard" in card.subtypes
        assert Keyword.VIGILANCE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = InformedInkwright(owner=None)
        assert card.name == "Informed Inkwright"
        assert card.mana_cost == ManaCost.parse("{1}{W}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestInformedInkwrightRepartee:
    """Informed Inkwright should create an Inkling for creature-targeting spells."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InformedInkwright(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_a_creature_targeting_sorcery_puts_trigger_on_stack_and_creates_inkling(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        card = InformedInkwright(owner=p1, controller=p1)
        target = Creature(
            name="Study Partner",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = CreatureTargetingTestSorcery(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card, target],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        card.register_triggers(game)
        p1._script.append(target)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        tokens = [
            permanent
            for permanent in game.get_battlefield(p1).get_all()
            if getattr(permanent, "is_token", False)
        ]
        assert len(tokens) == 1

        token = tokens[0]
        assert isinstance(token, Creature)
        assert token.power == 1
        assert token.toughness == 1
        assert "Inkling" in token.subtypes
        assert Keyword.FLYING in token.keywords
        assert get_colors(token) == {Color.WHITE, Color.BLACK}

        resolve_top(game)

        assert game.get_graveyard(p1).contains(spell)

    def test_non_targeting_spell_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InformedInkwright(owner=p1, controller=p1)
        spell = NonTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell

        resolve_top(game)

        assert game.get_battlefield(p1).get_all() == [card]

