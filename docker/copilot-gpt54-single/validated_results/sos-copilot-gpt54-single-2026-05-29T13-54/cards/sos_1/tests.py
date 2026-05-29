"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.events import AttacksTriggeredEvent
from engine.types import (
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Step,
    Supertype,
    Zone,
)
from test_utils import cast_spell, create_game, set_board_state


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_legendary_creature_avatar(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Avatar"} <= card.subtypes

    def test_name_mana_cost_and_power_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_has_reach_keyword(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords


class TestTheDawningArchaicCostReduction:
    """The cost reduction counts only your instant/sorcery cards in graveyard."""

    def test_counts_only_your_instants_and_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]

        your_instant = Instant(name="Spark", mana_cost=ManaCost.parse("{R}"))
        your_sorcery = Sorcery(name="Study", mana_cost=ManaCost.parse("{1}{U}"))
        your_creature = Creature(name="Bear", base_power=2, base_toughness=2)
        opp_instant = Instant(name="Shock", mana_cost=ManaCost.parse("{R}"))
        opp_sorcery = Sorcery(name="Chart", mana_cost=ManaCost.parse("{1}{U}"))

        set_board_state(
            game,
            0,
            graveyard=[your_instant, your_sorcery, your_creature],
        )
        set_board_state(game, 1, graveyard=[opp_instant, opp_sorcery])

        card = TheDawningArchaic(owner=p1, controller=p1)
        assert get_cost_reduction(game, card, p1) == 2

    def test_reduction_is_capped_at_ten_generic_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        graveyard = [
            Instant(name=f"Spell {i}", mana_cost=ManaCost.parse("{U}"))
            for i in range(12)
        ]
        set_board_state(game, 0, graveyard=graveyard)

        card = TheDawningArchaic(owner=p1, controller=p1)
        assert get_cost_reduction(game, card, p1) == 10

    def test_reduced_cost_allows_casting_for_eight_mana_with_two_spells_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            graveyard=[
                Instant(name="Spark", mana_cost=ManaCost.parse("{R}")),
                Sorcery(name="Study", mana_cost=ManaCost.parse("{1}{U}")),
            ],
            mana={ManaType.COLORLESS: 8},
        )

        cast_spell(game, 0, "The Dawning Archaic")

        assert game.get_battlefield(p1).contains(card)
        assert not game.get_hand(p1).contains(card)


class TestTheDawningArchaicAttackTrigger:
    """The attack trigger should free-cast a graveyard instant/sorcery and exile it."""

    @staticmethod
    def _get_attack_trigger(game, card):
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        trigger = triggers[0]
        assert trigger.event_type is AttacksTriggeredEvent
        return trigger

    @staticmethod
    def _choose_card(monkeypatch, player, chosen, *, cast_yes: bool = True) -> None:
        monkeypatch.setattr(player, "choose_yes_no", lambda prompt: cast_yes)
        monkeypatch.setattr(player, "choose_card", lambda cards, description: chosen)
        monkeypatch.setattr(player, "choose_target", lambda options, requirement: chosen)
        monkeypatch.setattr(player, "choose", lambda options, description: chosen)

    def test_registers_an_attacks_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        trigger = self._get_attack_trigger(game, card)
        assert trigger.source is card
        assert trigger.controller is p1

    def test_trigger_condition_matches_only_this_archaic_attacking(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        other = Creature(name="Other", base_power=2, base_toughness=2)

        trigger = self._get_attack_trigger(game, card)

        assert trigger.condition(game, AttacksTriggeredEvent(creature=card, attacker=card)) is True
        assert trigger.condition(game, AttacksTriggeredEvent(creature=other, attacker=other)) is False

    def test_trigger_noops_when_graveyard_has_no_instant_or_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card], graveyard=[bear])

        trigger = self._get_attack_trigger(game, card)
        trigger.effect(game)

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(bear)

    def test_trigger_may_be_declined(self, monkeypatch) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        spell = Instant(name="Opt", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, battlefield=[card], graveyard=[spell])

        trigger = self._get_attack_trigger(game, card)
        self._choose_card(monkeypatch, p1, None, cast_yes=False)
        trigger.effect(game)

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(spell)

    def test_trigger_can_cast_a_sorcery_from_graveyard_without_paying_mana(self, monkeypatch) -> None:
        game = create_game()
        game.phase = Phase.COMBAT
        game.step = Step.DECLARE_ATTACKERS
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        spell = Sorcery(name="Deep Recall", mana_cost=ManaCost.parse("{3}{U}"))
        set_board_state(game, 0, battlefield=[card], graveyard=[spell])

        trigger = self._get_attack_trigger(game, card)
        self._choose_card(monkeypatch, p1, spell, cast_yes=True)
        trigger.effect(game)

        top = game.stack.peek()
        assert top is not None
        assert top.source is spell
        assert not game.get_graveyard(p1).contains(spell)

    def test_spell_cast_by_trigger_is_exiled_instead_of_going_to_graveyard(self, monkeypatch) -> None:
        game = create_game()
        game.phase = Phase.COMBAT
        game.step = Step.DECLARE_ATTACKERS
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        spell = Sorcery(name="Deep Recall", mana_cost=ManaCost.parse("{3}{U}"))
        set_board_state(game, 0, battlefield=[card], graveyard=[spell])

        trigger = self._get_attack_trigger(game, card)
        self._choose_card(monkeypatch, p1, spell, cast_yes=True)
        trigger.effect(game)

        obj = game.stack.pop()
        obj.on_resolve(game)

        assert game.players[0].zones[Zone.EXILE].contains(spell)
        assert not game.get_graveyard(p1).contains(spell)
