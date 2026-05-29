"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.events import AttacksTriggeredEvent
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import cast_spell, create_game, set_board_state


class TestTheDawningArchaicProperties:
    """Static card data should match the card spec."""

    def test_is_a_creature(self) -> None:
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
    """Casting cost should shrink with instant/sorcery cards in your graveyard."""

    @staticmethod
    def _instant_card(name: str) -> Instant:
        return Instant(name=name, mana_cost=ManaCost.parse("{U}"))

    @staticmethod
    def _sorcery_card(name: str) -> Sorcery:
        return Sorcery(name=name, mana_cost=ManaCost.parse("{2}{U}"))

    def test_counts_only_instants_and_sorceries_in_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        grizzly_bears = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)

        set_board_state(
            game,
            0,
            graveyard=[
                self._instant_card("Opt"),
                self._instant_card("Negate"),
                self._sorcery_card("Divination"),
                grizzly_bears,
            ],
        )

        assert get_cost_reduction(game, card, p1) == 3

    def test_can_be_cast_for_seven_when_three_eligible_cards_are_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            graveyard=[
                self._instant_card("Opt"),
                self._instant_card("Negate"),
                self._sorcery_card("Divination"),
            ],
            mana={ManaType.COLORLESS: 7},
        )

        cast_spell(game, 0, "The Dawning Archaic")

        assert game.get_battlefield(p1).contains(card)

    def test_can_be_cast_for_zero_when_ten_eligible_cards_are_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        graveyard = [self._instant_card(f"Cantrip {i}") for i in range(10)]

        set_board_state(
            game,
            0,
            hand=[card],
            graveyard=graveyard,
            mana={},
        )

        cast_spell(game, 0, "The Dawning Archaic")

        assert game.get_battlefield(p1).contains(card)


class TestTheDawningArchaicAttackTrigger:
    """Attack trigger should free-cast a graveyard instant/sorcery and exile it later."""

    def test_registers_an_attacks_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent

    def test_attack_trigger_is_a_noop_when_graveyard_has_no_instant_or_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        fallen_bear = Creature(name="Runeclaw Bear", base_power=2, base_toughness=2)

        set_board_state(game, 0, battlefield=[card], graveyard=[fallen_bear])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.get_graveyard(p1).contains(fallen_bear)
        assert game.stack.is_empty()

    def test_attack_trigger_may_be_declined(self, monkeypatch) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        spell = Instant(name="Think Twice", mana_cost=ManaCost.parse("{1}{U}"))

        set_board_state(game, 0, battlefield=[card], graveyard=[spell], mana={})
        card.register_triggers(game)

        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: False)
        monkeypatch.setattr(p1, "choose_card", lambda cards, description: spell)
        monkeypatch.setattr(p1, "choose_target", lambda options, requirement: spell)
        monkeypatch.setattr(p1, "choose", lambda options, description: spell)

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.get_graveyard(p1).contains(spell)
        assert p1.zones[Zone.EXILE].contains(spell) is False
        assert game.stack.is_empty()

    def test_attack_trigger_casts_spell_for_free_from_graveyard_and_exiles_it(self, monkeypatch) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        spell = Sorcery(name="Overflowing Insight", mana_cost=ManaCost.parse("{4}{U}{U}{U}"))

        set_board_state(game, 0, battlefield=[card], graveyard=[spell], mana={})
        card.register_triggers(game)

        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: True)
        monkeypatch.setattr(p1, "choose_card", lambda cards, description: spell)
        monkeypatch.setattr(p1, "choose_target", lambda options, requirement: spell)
        monkeypatch.setattr(p1, "choose", lambda options, description: spell)

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert p1.mana_pool.total() == 0
        assert game.stack.peek().source is spell
        assert game.get_graveyard(p1).contains(spell) is False

        game.stack.pop().on_resolve(game)

        assert p1.zones[Zone.EXILE].contains(spell)
        assert game.get_graveyard(p1).contains(spell) is False
