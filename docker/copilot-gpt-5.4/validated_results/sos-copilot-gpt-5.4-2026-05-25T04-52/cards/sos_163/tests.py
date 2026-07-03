"""Tests for SOS 163 — Tenured Concocter."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_163.card_impl import TenuredConcocter
from benchmarks.sos.workspace.engine.abilities import ActivatedAbilityInstance, activate_ability
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CreatureTargetingTestInstant(Instant):
    """Simple instant used to target Tenured Concocter."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Creature Targeting Test Spell")
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


class TestTenuredConcocterProperties:
    """Static card data should match the SOS 163 spec."""

    def test_is_troll_druid_creature_with_vigilance(self) -> None:
        card = TenuredConcocter(owner=None)

        assert isinstance(card, Creature)
        assert "Troll" in card.subtypes
        assert "Druid" in card.subtypes
        assert Keyword.VIGILANCE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = TenuredConcocter(owner=None)

        assert card.name == "Tenured Concocter"
        assert card.mana_cost == ManaCost.parse("{4}{G}")
        assert card.base_power == 4
        assert card.base_toughness == 5


class TestTenuredConcocterTargetTrigger:
    """Tenured Concocter should care about opposing spells and abilities targeting it."""

    def test_opponents_targeting_spell_may_draw_a_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = TenuredConcocter(owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p2, controller=p2)
        drawn_card = CardImpl(name="Research Notes", owner=p1, controller=p1)
        game.get_library(p1).add(drawn_card)

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, hand=[spell], mana={ManaType.WHITE: 1})
        card.register_triggers(game)
        p1._script.append(True)
        p2._script.append(card)

        cast_spell_paid(game, p2, spell)

        assert len(game.stack) == 2
        resolve_top(game)

        assert game.get_hand(p1).contains(drawn_card)
        assert len(game.stack) == 1
        assert game.stack.peek().source is spell

    def test_opponents_targeting_ability_may_be_declined(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = TenuredConcocter(owner=p1, controller=p1)
        apparatus = Creature(
            name="Practice Apparatus",
            owner=p2,
            controller=p2,
            base_power=1,
            base_toughness=1,
        )
        undrawn_card = CardImpl(name="Unchosen Discovery", owner=p1, controller=p1)
        game.get_library(p1).add(undrawn_card)

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[apparatus])
        card.register_triggers(game)
        p1._script.append(False)

        activate_ability(
            game,
            p2,
            ActivatedAbilityInstance(
                source=apparatus,
                controller=p2,
                cost=lambda _game, _source: True,
                effect=lambda _game: None,
                targets=[card],
                target_requirements=[
                    TargetRequirement(
                        filter_fn=lambda obj: isinstance(obj, Creature),
                        description="target creature",
                        zone=Zone.BATTLEFIELD,
                    )
                ],
                description="Target creature",
            ),
        )

        assert len(game.stack) == 2
        resolve_top(game)

        assert game.get_library(p1).contains(undrawn_card)
        assert not game.get_hand(p1).contains(undrawn_card)
        assert len(game.stack) == 1
        assert game.stack.peek().source is apparatus

    def test_your_own_targeting_spell_does_not_trigger_the_draw(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TenuredConcocter(owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p1, controller=p1)
        undrawn_card = CardImpl(name="Unread Thesis", owner=p1, controller=p1)
        game.get_library(p1).add(undrawn_card)

        set_board_state(game, 0, battlefield=[card], hand=[spell], mana={ManaType.WHITE: 1})
        card.register_triggers(game)
        p1._script.append(card)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        assert game.get_library(p1).contains(undrawn_card)
        assert not game.get_hand(p1).contains(undrawn_card)


class TestTenuredConcocterInfusion:
    """Tenured Concocter should get +2/+0 only while you gained life this turn."""

    def test_without_life_gain_apply_continuous_effect_leaves_it_at_base_stats(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TenuredConcocter(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.apply_continuous_effect(game)
        game.effect_manager.apply_all(game)

        assert card.power == 4
        assert card.toughness == 5

    def test_if_you_gained_life_this_turn_apply_continuous_effect_gives_plus_two_plus_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TenuredConcocter(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        p1.life_gained_this_turn = 1

        card.apply_continuous_effect(game)
        game.effect_manager.apply_all(game)

        assert card.power == 6
        assert card.toughness == 5
