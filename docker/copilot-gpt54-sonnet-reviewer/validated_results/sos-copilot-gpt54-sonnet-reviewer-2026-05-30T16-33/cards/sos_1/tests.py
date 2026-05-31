"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype
from test_utils import cast_spell, create_game, set_board_state


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_name_and_mana_cost(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")

    def test_is_legendary_avatar_with_reach_and_seven_seven(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert CardType.CREATURE in card.card_types
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes
        assert Keyword.REACH in card.keywords
        assert card.base_power == 7
        assert card.base_toughness == 7


class TestTheDawningArchaicCostReduction:
    """Casting cost should shrink with instants and sorceries in your graveyard."""

    def test_cost_reduction_counts_only_your_instants_and_sorceries(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = TheDawningArchaic(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            graveyard=[
                Instant(name="Shock"),
                Sorcery(name="Divination"),
                Creature(name="Grizzly Bears", base_power=2, base_toughness=2),
            ],
        )
        set_board_state(game, 1, graveyard=[Instant(name="Opt")])

        assert card.cost_reduction(game) == 2

    def test_casting_reduction_can_reduce_total_cost_to_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        graveyard_spells = [
            Instant(name=f"Instant {idx}") for idx in range(5)
        ] + [
            Sorcery(name=f"Sorcery {idx}") for idx in range(5)
        ]
        set_board_state(game, 0, hand=[card], graveyard=graveyard_spells, mana={})

        cast_spell(game, 0, "The Dawning Archaic")

        assert game.get_battlefield(p1).contains(card)
        assert not game.get_hand(p1).contains(card)


class TestTheDawningArchaicAttackTrigger:
    """Attack trigger should cast one of your graveyard instants/sorceries for free."""

    @staticmethod
    def _register_and_trigger(game, archaic: TheDawningArchaic) -> None:
        archaic.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

    def test_registers_one_attacks_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent

    def test_other_creature_attacking_does_not_fire_the_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        other = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=other, attacker=other),
        )

        assert game.stack.is_empty()

    def test_attack_trigger_can_cast_sorcery_from_your_graveyard_for_free(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        spell = Sorcery(name="Deep Recall", mana_cost=ManaCost.parse("{9}{U}"))

        set_board_state(game, 0, battlefield=[card], graveyard=[spell], mana={})
        p1.choose_card = lambda cards, description: spell
        p1.choose_yes_no = lambda prompt: True

        self._register_and_trigger(game, card)
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert not game.get_graveyard(p1).contains(spell)
        assert not game.stack.is_empty()
        assert game.stack.peek().source is spell

    def test_attack_trigger_may_decline_to_cast_the_targeted_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        spell = Instant(name="Lightning Bolt", mana_cost=ManaCost.parse("{R}"))

        set_board_state(game, 0, battlefield=[card], graveyard=[spell], mana={})
        p1.choose_card = lambda cards, description: spell
        p1.choose_yes_no = lambda prompt: False

        self._register_and_trigger(game, card)
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.get_graveyard(p1).contains(spell)
        assert game.stack.is_empty()

    def test_attack_trigger_does_not_cast_a_creature_card_from_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        creature_card = Creature(name="Hill Giant", base_power=3, base_toughness=3)

        set_board_state(game, 0, battlefield=[card], graveyard=[creature_card], mana={})

        self._register_and_trigger(game, card)
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.get_graveyard(p1).contains(creature_card)
        assert game.stack.is_empty()

    def test_attack_trigger_cannot_cast_spell_from_opponents_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = TheDawningArchaic(owner=p1, controller=p1)
        opposing_spell = Instant(name="Opt", owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[card], graveyard=[], mana={})
        set_board_state(game, 1, graveyard=[opposing_spell])

        self._register_and_trigger(game, card)
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.get_graveyard(p2).contains(opposing_spell)
        assert game.stack.is_empty()

    def test_spell_cast_by_the_attack_trigger_is_exiled_instead_of_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        spell = Instant(name="Flame Burst", mana_cost=ManaCost.parse("{1}{R}"))

        set_board_state(game, 0, battlefield=[card], graveyard=[spell], mana={})
        p1.choose_card = lambda cards, description: spell
        p1.choose_yes_no = lambda prompt: True

        self._register_and_trigger(game, card)
        trigger = game.stack.pop()
        trigger.on_resolve(game)
        spell_on_stack = game.stack.pop()
        spell_on_stack.on_resolve(game)

        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)
