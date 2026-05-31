"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import TestSetupError as SetupError, cast_spell, create_game, set_board_state


class GraveyardBolt(Sorcery):
    """Simple sorcery used to verify graveyard casting."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Test Graveyard Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}"))
        super().__init__(**kwargs)
        self.was_resolved = False

    def on_resolve(self, game) -> None:
        self.was_resolved = True
        if self.controller is not None:
            self.controller.life += 3


def _resolve_top_of_stack(game) -> None:
    obj = game.stack.pop()
    obj.on_resolve(game)


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(TheDawningArchaic(owner=None), Creature)

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_is_legendary_avatar(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes

    def test_power_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_has_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords


class TestTheDawningArchaicCostReduction:
    """Casting cost should scale with instant/sorcery cards in your graveyard."""

    def test_cast_succeeds_with_two_instants_or_sorceries_in_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Test Opt", mana_cost=ManaCost.parse("{U}"))
        sorcery = Sorcery(name="Test Flame", mana_cost=ManaCost.parse("{R}"))
        creature = Creature(name="Test Bear", base_power=2, base_toughness=2)

        set_board_state(
            game,
            0,
            hand=[archaic],
            graveyard=[instant, sorcery, creature],
            mana={ManaType.COLORLESS: 8},
        )

        cast_spell(game, 0, "The Dawning Archaic")

        assert game.get_battlefield(p1).contains(archaic)

    def test_cast_does_not_count_opponents_graveyard_cards_toward_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        opposing_instant = Instant(name="Opposing Opt", mana_cost=ManaCost.parse("{U}"))
        opposing_sorcery = Sorcery(name="Opposing Flame", mana_cost=ManaCost.parse("{R}"))

        set_board_state(
            game,
            0,
            hand=[archaic],
            mana={ManaType.COLORLESS: 8},
        )
        set_board_state(
            game,
            1,
            graveyard=[opposing_instant, opposing_sorcery],
        )

        with pytest.raises(SetupError):
            cast_spell(game, 0, "The Dawning Archaic")


class TestTheDawningArchaicAttackTrigger:
    """The attack trigger should free-cast a spell from your graveyard."""

    def test_registers_one_attacks_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent
        assert triggers[0].controller is p1

    def test_attack_trigger_does_not_fire_for_other_attacker(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        other = Creature(name="Other Attacker", owner=p1, controller=p1, base_power=2, base_toughness=2)
        other.card_types = {CardType.CREATURE}
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=other, attacker=other))

        assert game.stack.is_empty()

    def test_attack_trigger_may_be_declined(self, monkeypatch) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        spell = GraveyardBolt(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], graveyard=[spell])
        card.register_triggers(game)

        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: False)
        monkeypatch.setattr(p1, "choose_card", lambda cards, description: None)
        monkeypatch.setattr(p1, "choose_target", lambda options, requirement: None)

        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=card, attacker=card))
        assert len(game.stack) == 1
        _resolve_top_of_stack(game)

        assert game.players[0].zones[Zone.GRAVEYARD].contains(spell)
        assert game.stack.is_empty()

    def test_attack_trigger_with_no_eligible_graveyard_spell_is_a_noop(self, monkeypatch) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TheDawningArchaic(owner=p1, controller=p1)
        own_creature = Creature(name="Test Bear", base_power=2, base_toughness=2)
        opposing_spell = GraveyardBolt(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[card], graveyard=[own_creature])
        set_board_state(game, 1, graveyard=[opposing_spell])
        card.register_triggers(game)

        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: True)
        monkeypatch.setattr(p1, "choose_card", lambda cards, description: cards[0] if cards else None)
        monkeypatch.setattr(p1, "choose_target", lambda options, requirement: None)

        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=card, attacker=card))
        assert len(game.stack) == 1
        _resolve_top_of_stack(game)

        assert game.players[0].zones[Zone.GRAVEYARD].contains(own_creature)
        assert game.players[1].zones[Zone.GRAVEYARD].contains(opposing_spell)
        assert game.stack.is_empty()

    def test_attack_trigger_casts_chosen_graveyard_sorcery_for_free_and_exiles_it(self, monkeypatch) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        spell = GraveyardBolt(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], graveyard=[spell])
        card.register_triggers(game)

        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: True)
        monkeypatch.setattr(p1, "choose_card", lambda cards, description: spell)
        monkeypatch.setattr(p1, "choose_target", lambda options, requirement: spell)

        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=card, attacker=card))
        assert len(game.stack) == 1
        _resolve_top_of_stack(game)

        assert game.stack.peek() is not None
        assert game.stack.peek().source is spell
        assert not game.players[0].zones[Zone.GRAVEYARD].contains(spell)

        _resolve_top_of_stack(game)

        assert spell.was_resolved is True
        assert p1.life == 23
        assert game.players[0].zones[Zone.EXILE].contains(spell)
        assert not game.players[0].zones[Zone.GRAVEYARD].contains(spell)
