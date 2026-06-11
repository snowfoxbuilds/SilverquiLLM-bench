"""Tests for SOS 164 — Thornfist Striker."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_164.card_impl import ThornfistStriker
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CreatureTargetingTestInstant(Instant):
    """Simple instant used to exercise ward against a targeted spell."""

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


class TestThornfistStrikerProperties:
    """Static card data should match the SOS 164 spec."""

    def test_is_elf_druid_creature_with_ward(self) -> None:
        card = ThornfistStriker(owner=None)

        assert isinstance(card, Creature)
        assert "Elf" in card.subtypes
        assert "Druid" in card.subtypes
        assert Keyword.WARD in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = ThornfistStriker(owner=None)

        assert card.name == "Thornfist Striker"
        assert card.mana_cost == ManaCost.parse("{2}{G}")
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestThornfistStrikerWard:
    """Thornfist Striker should enforce Ward {1} against opposing targeted spells."""

    def test_opponents_targeting_spell_is_countered_when_they_do_not_pay_ward(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ThornfistStriker(owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, hand=[spell], mana={ManaType.WHITE: 1})
        p2._script.append(card)

        cast_spell_paid(game, p2, spell)

        assert len(game.stack) == 2
        resolve_top(game)

        assert getattr(spell, "last_ward_outcome", None) == "countered"
        assert game.get_graveyard(p2).contains(spell)
        assert game.stack.is_empty()

    def test_opponent_may_pay_ward_to_keep_their_spell_on_the_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ThornfistStriker(owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, hand=[spell], mana={ManaType.WHITE: 2})
        p2._script.extend([card, True])

        cast_spell_paid(game, p2, spell)

        assert len(game.stack) == 2
        resolve_top(game)

        assert getattr(spell, "last_ward_outcome", None) == "paid"
        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        assert p2.mana_pool.total() == 0


class TestThornfistStrikerInfusion:
    """Thornfist Striker should boost only your creatures after you gain life."""

    def test_without_life_gain_apply_continuous_effect_leaves_your_creatures_unchanged(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ThornfistStriker(owner=p1, controller=p1)
        ally = Creature(
            name="Friendly Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card, ally])

        card.apply_continuous_effect(game)
        game.effect_manager.apply_all(game)

        assert card.power == 3
        assert card.toughness == 3
        assert ally.power == 2
        assert ally.toughness == 2
        assert Keyword.TRAMPLE not in card.keywords
        assert Keyword.TRAMPLE not in ally.keywords

    def test_if_you_gained_life_this_turn_your_creatures_get_plus_one_plus_zero_and_trample(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ThornfistStriker(owner=p1, controller=p1)
        ally = Creature(
            name="Friendly Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        enemy = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card, ally])
        set_board_state(game, 1, battlefield=[enemy])
        p1.life_gained_this_turn = 1

        card.apply_continuous_effect(game)
        game.effect_manager.apply_all(game)

        assert card.power == 4
        assert card.toughness == 3
        assert ally.power == 3
        assert ally.toughness == 2
        assert enemy.power == 2
        assert enemy.toughness == 2
        assert Keyword.TRAMPLE in card.keywords
        assert Keyword.TRAMPLE in ally.keywords
        assert Keyword.TRAMPLE not in enemy.keywords
