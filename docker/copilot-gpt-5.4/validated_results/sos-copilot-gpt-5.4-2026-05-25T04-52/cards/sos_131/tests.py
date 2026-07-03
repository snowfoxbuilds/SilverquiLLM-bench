"""Tests for SOS 131 — Strife Scholar // Awaken the Ages."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_131.card_impl import StrifeScholarAwakenTheAges
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CreatureTargetingTestInstant(Instant):
    """Simple instant used to exercise ward handling."""

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


class TestStrifeScholarAwakenTheAgesProperties:
    """Static front-face data should match the SOS 131 spec."""

    def test_is_orc_sorcerer_creature_with_ward(self) -> None:
        card = StrifeScholarAwakenTheAges(owner=None)

        assert isinstance(card, Creature)
        assert "Orc" in card.subtypes
        assert "Sorcerer" in card.subtypes
        assert Keyword.WARD in card.keywords

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = StrifeScholarAwakenTheAges(owner=None)

        assert card.name == "Strife Scholar"
        assert card.mana_cost == ManaCost.parse("{2}{R}")
        assert card.base_power == 3
        assert card.base_toughness == 2


class TestStrifeScholarAwakenTheAgesPrepared:
    """Strife Scholar should use the prepared-state contract."""

    def test_enters_prepared_on_resolve(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = StrifeScholarAwakenTheAges(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.on_resolve(game)

        assert card.is_prepared is True

    def test_prepared_spell_copy_is_awaken_the_ages_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = StrifeScholarAwakenTheAges(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Awaken the Ages"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.mana_cost == ManaCost.parse("{5}{R}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card


class TestStrifeScholarAwakenTheAgesWard:
    """Strife Scholar should enforce Ward—Pay 2 life."""

    def test_opponents_targeting_spell_is_countered_when_they_cannot_pay_two_life(self) -> None:
        game = create_game(player2_life=1)
        p1, p2 = game.players
        card = StrifeScholarAwakenTheAges(owner=p1, controller=p1)
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
        assert p2.life == 1

    def test_opponent_may_pay_two_life_to_keep_their_spell_on_the_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = StrifeScholarAwakenTheAges(owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, hand=[spell], mana={ManaType.WHITE: 1})
        p2._script.extend([card, True])

        cast_spell_paid(game, p2, spell)

        assert len(game.stack) == 2
        resolve_top(game)

        assert getattr(spell, "last_ward_outcome", None) == "paid"
        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        assert p2.life == 18
