"""Tests for SOS 45 — Emeritus of Ideation // Ancestral Recall."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_45.card_impl import EmeritusOfIdeationAncestralRecall
from benchmarks.sos.workspace.engine.casting import CastingError, cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, declare_attackers, set_board_state


class CreatureTargetingTestInstant(Instant):
    """Simple instant used to exercise Ward against a targeted spell."""

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


class TestEmeritusOfIdeationProperties:
    """Static front-face data should match the SOS 45 spec."""

    def test_is_human_wizard_creature_with_flying_and_ward(self) -> None:
        card = EmeritusOfIdeationAncestralRecall(owner=None)
        assert isinstance(card, Creature)
        assert "Human" in card.subtypes
        assert "Wizard" in card.subtypes
        assert Keyword.FLYING in card.keywords
        assert Keyword.WARD in card.keywords

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = EmeritusOfIdeationAncestralRecall(owner=None)
        assert card.name == "Emeritus of Ideation"
        assert card.mana_cost == ManaCost.parse("{3}{U}{U}")
        assert card.base_power == 5
        assert card.base_toughness == 5


class TestEmeritusOfIdeationWard:
    """Emeritus of Ideation should enforce Ward {2} against opposing targeted spells."""

    def test_opponents_targeting_spell_is_countered_when_they_cannot_pay_ward(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfIdeationAncestralRecall(owner=p1, controller=p1)
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
        card = EmeritusOfIdeationAncestralRecall(owner=p1, controller=p1)
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


class TestEmeritusOfIdeationPrepared:
    """Emeritus of Ideation should enter prepared and cast Ancestral Recall copies."""

    def test_enters_prepared_on_resolve(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfIdeationAncestralRecall(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.on_resolve(game)

        assert card.is_prepared is True

    def test_prepared_spell_copy_is_ancestral_recall_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfIdeationAncestralRecall(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Ancestral Recall"
        assert isinstance(stack_obj.source, Instant)
        assert stack_obj.source.mana_cost == ManaCost.parse("{U}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfIdeationAncestralRecall(owner=p1, controller=p1)

        with pytest.raises(CastingError, match="not prepared"):
            card.cast_prepared_spell_copy(game)


class TestEmeritusOfIdeationAttackTrigger:
    """Emeritus of Ideation should be able to become prepared again by attacking."""

    def test_registers_an_attacks_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfIdeationAncestralRecall(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent

    def test_attack_trigger_may_exile_eight_graveyard_cards_to_become_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        graveyard_cards = [CardImpl(name=f"Study Note {idx}") for idx in range(8)]
        card = EmeritusOfIdeationAncestralRecall(owner=p1, controller=p1)
        card.summoning_sick = False

        set_board_state(game, 0, battlefield=[card], graveyard=graveyard_cards)
        card.become_unprepared()
        card.register_triggers(game)
        p1._script.append(True)

        declare_attackers(game, ["Emeritus of Ideation"])

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert card.is_prepared is True
        assert game.get_graveyard(p1).get_all() == []
        assert len(game.get_exile(p1).get_all()) == 8

    def test_attack_trigger_does_not_prepare_it_with_fewer_than_eight_graveyard_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        graveyard_cards = [CardImpl(name=f"Study Note {idx}") for idx in range(7)]
        card = EmeritusOfIdeationAncestralRecall(owner=p1, controller=p1)
        card.summoning_sick = False

        set_board_state(game, 0, battlefield=[card], graveyard=graveyard_cards)
        card.become_unprepared()
        card.register_triggers(game)
        p1._script.append(True)

        declare_attackers(game, ["Emeritus of Ideation"])

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert card.is_prepared is False
        assert len(game.get_graveyard(p1).get_all()) == 7
        assert game.get_exile(p1).get_all() == []
