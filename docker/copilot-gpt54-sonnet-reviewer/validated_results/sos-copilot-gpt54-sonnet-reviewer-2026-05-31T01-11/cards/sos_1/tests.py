"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import cast_spell, create_game, set_board_state


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(TheDawningArchaic(owner=None), Creature)

    def test_name_and_mana_cost(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")

    def test_is_legendary_avatar(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes

    def test_power_and_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_has_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords


class TestTheDawningArchaicCostReduction:
    """Casting cost reduction should track spell cards in your graveyard."""

    def test_counts_only_your_instants_and_sorceries_in_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = TheDawningArchaic(owner=p1, controller=p1)

        your_instant = Instant(name="Shock")
        your_sorcery = Sorcery(name="Divination")
        your_creature = Creature(name="Bear", base_power=2, base_toughness=2)
        opposing_instant = Instant(name="Opt")

        set_board_state(
            game,
            0,
            graveyard=[your_instant, your_sorcery, your_creature],
        )
        set_board_state(game, 1, graveyard=[opposing_instant])

        assert card.cost_reduction(game) == 2

    def test_casts_for_two_less_with_two_spell_cards_in_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            graveyard=[
                Instant(name="Opt", mana_cost=ManaCost.parse("{U}")),
                Sorcery(name="Tormenting Voice", mana_cost=ManaCost.parse("{1}{R}")),
            ],
            mana={ManaType.COLORLESS: 8},
        )

        cast_spell(game, 0, "The Dawning Archaic")

        assert game.get_battlefield(p1).contains(card)


class TestTheDawningArchaicAttackTrigger:
    """Attack trigger should free-cast a graveyard spell and exile it later."""

    def test_attacking_with_legal_graveyard_spell_pushes_targeted_trigger_on_stack(
        self,
    ) -> None:
        game = create_game()
        p1, p2 = game.players
        card = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_spell = Instant(
            name="Memory Burst",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{4}{U}"),
        )
        corpse = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opposing_spell = Sorcery(
            name="Mind Rot",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{B}"),
        )
        set_board_state(
            game,
            0,
            battlefield=[card],
            graveyard=[graveyard_spell, corpse],
        )
        set_board_state(game, 1, graveyard=[opposing_spell])

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )

        assert not game.stack.is_empty()
        trigger_obj = game.stack.pop()
        assert trigger_obj.source is card
        assert trigger_obj.controller is p1
        assert trigger_obj.targets == [graveyard_spell]

    def test_attack_does_not_create_trigger_without_legal_graveyard_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        corpse = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card], graveyard=[corpse])

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )

        assert game.stack.is_empty()

    def test_other_creature_attacking_does_not_trigger_archaic(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_spell = Instant(
            name="Memory Burst",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{4}{U}"),
        )
        other = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card, other], graveyard=[graveyard_spell])

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=other, attacker=other),
        )

        assert game.stack.is_empty()

    def test_trigger_can_cast_chosen_graveyard_spell_without_paying_mana_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_spell = Instant(
            name="Memory Burst",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{4}{U}"),
        )
        set_board_state(game, 0, battlefield=[card], graveyard=[graveyard_spell])
        p1.choose_yes_no = lambda prompt: True

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )

        trigger_obj = game.stack.pop()
        assert trigger_obj.targets == [graveyard_spell]
        trigger_obj.on_resolve(game)

        assert p1.zones[Zone.STACK].contains(graveyard_spell)
        assert not game.get_graveyard(p1).contains(graveyard_spell)
        assert not game.stack.is_empty()
        assert game.stack.peek().source is graveyard_spell

    def test_trigger_is_optional(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_spell = Instant(
            name="Memory Burst",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{4}{U}"),
        )
        set_board_state(game, 0, battlefield=[card], graveyard=[graveyard_spell])
        p1.choose_yes_no = lambda prompt: False

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(graveyard_spell)

    def test_triggered_spell_is_exiled_instead_of_returning_to_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_spell = Instant(
            name="Memory Burst",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{4}{U}"),
        )
        set_board_state(game, 0, battlefield=[card], graveyard=[graveyard_spell])
        p1.choose_yes_no = lambda prompt: True

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)
        spell_obj = game.stack.pop()
        spell_obj.on_resolve(game)

        assert game.get_exile(p1).contains(graveyard_spell)
        assert not game.get_graveyard(p1).contains(graveyard_spell)

    def test_trigger_does_not_retarget_if_locked_spell_leaves_graveyard_before_resolution(
        self,
    ) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        locked_spell = Instant(
            name="Memory Burst",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{4}{U}"),
        )
        later_spell = Sorcery(
            name="Mind Rot",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{2}{B}"),
        )
        set_board_state(game, 0, battlefield=[card], graveyard=[locked_spell])
        p1.choose_yes_no = lambda prompt: True

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=card, attacker=card),
        )

        trigger_obj = game.stack.pop()
        assert trigger_obj.targets == [locked_spell]
        game.get_graveyard(p1).remove(locked_spell)
        p1.zones[Zone.HAND].add(locked_spell)
        game.get_graveyard(p1).add(later_spell)
        trigger_obj.on_resolve(game)

        assert game.stack.is_empty()
        assert p1.zones[Zone.HAND].contains(locked_spell)
        assert game.get_graveyard(p1).contains(later_spell)
