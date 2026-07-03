"""Tests for SOS 40 — Campus Composer // Aqueous Aria."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_40.card_impl import CampusComposerAqueousAria
from benchmarks.sos.workspace.engine.casting import CastingError, cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
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


class TestCampusComposerAqueousAriaProperties:
    """Static front-face data should match the SOS 40 spec."""

    def test_is_merfolk_bard_creature_with_ward(self) -> None:
        card = CampusComposerAqueousAria(owner=None)
        assert isinstance(card, Creature)
        assert "Merfolk" in card.subtypes
        assert "Bard" in card.subtypes
        assert Keyword.WARD in card.keywords

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = CampusComposerAqueousAria(owner=None)
        assert card.name == "Campus Composer"
        assert card.mana_cost == ManaCost.parse("{3}{U}")
        assert card.base_power == 3
        assert card.base_toughness == 4


class TestCampusComposerAqueousAriaWard:
    """Campus Composer should enforce Ward {2} against opposing targeted spells."""

    def test_opponents_targeting_spell_is_countered_when_they_cannot_pay_ward(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = CampusComposerAqueousAria(owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, hand=[spell], mana={ManaType.WHITE: 1})
        p2._script.append(card)

        cast_spell_paid(game, p2, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert getattr(spell, "last_ward_outcome", None) == "countered"
        assert game.get_graveyard(p2).contains(spell)
        assert game.stack.is_empty()

    def test_opponent_may_pay_ward_to_keep_their_targeting_spell_on_the_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = CampusComposerAqueousAria(owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, hand=[spell], mana={ManaType.WHITE: 3})
        p2._script.extend([card, True])

        cast_spell_paid(game, p2, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert getattr(spell, "last_ward_outcome", None) == "paid"
        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        assert p2.mana_pool.total() == 0


class TestCampusComposerAqueousAriaPrepared:
    """Campus Composer should enter prepared and cast Aqueous Aria copies."""

    def test_enters_prepared_on_resolve(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CampusComposerAqueousAria(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.on_resolve(game)

        assert card.is_prepared is True

    def test_prepared_spell_copy_is_aqueous_aria_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CampusComposerAqueousAria(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Aqueous Aria"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.mana_cost == ManaCost.parse("{4}{U}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CampusComposerAqueousAria(owner=p1, controller=p1)
        assert card.can_be_prepared() is True

        with pytest.raises(CastingError, match="not prepared"):
            card.cast_prepared_spell_copy(game)
