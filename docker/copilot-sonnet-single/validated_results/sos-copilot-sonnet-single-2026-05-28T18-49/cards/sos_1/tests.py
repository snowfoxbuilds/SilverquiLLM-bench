"""Tests for SOS 1 — The Dawning Archaic.

Requirements under test:
1. 7/7 Legendary Creature — Avatar with Reach.
2. Base mana cost is {10} but costs {1} less for each instant/sorcery card
   in the controller's graveyard.
3. When The Dawning Archaic attacks, the controller may cast a target
   instant or sorcery card from their graveyard without paying its mana cost.
4. If that spell would be put into the graveyard, exile it instead.
"""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(TheDawningArchaic(owner=None), Creature)

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost_is_ten_generic(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.mana_cost == ManaCost.parse("{10}")

    def test_base_power_is_seven(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7

    def test_base_toughness_is_seven(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_toughness == 7

    def test_has_reach(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Keyword.REACH in card.keywords

    def test_is_legendary(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_avatar_subtype(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert "Avatar" in card.subtypes

    def test_has_creature_card_type(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert CardType.CREATURE in card.card_types


# ---------------------------------------------------------------------------
# Cost reduction mechanic
# ---------------------------------------------------------------------------

class TestTheDawningArchaicCostReduction:
    """cost_reduction() returns the number of instant/sorcery cards in
    the controller's graveyard, reducing the generic {10} base cost."""

    def test_no_reduction_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_instant_in_graveyard_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant])
        assert card.cost_reduction(game) == 1

    def test_one_sorcery_in_graveyard_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[sorcery])
        assert card.cost_reduction(game) == 1

    def test_multiple_instants_and_sorceries_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        cards_in_gy = [
            Instant(name="Bolt", owner=p1, controller=p1),
            Instant(name="Bolt2", owner=p1, controller=p1),
            Sorcery(name="Divination", owner=p1, controller=p1),
        ]
        set_board_state(game, 0, graveyard=cards_in_gy)
        assert card.cost_reduction(game) == 3

    def test_non_instant_sorcery_cards_do_not_contribute(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        creature = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, graveyard=[creature])
        assert card.cost_reduction(game) == 0

    def test_only_controllers_graveyard_counts(self) -> None:
        """Opponent's instants/sorceries in the graveyard don't reduce cost."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TheDawningArchaic(owner=p1, controller=p1)
        opp_instant = Instant(name="Counterspell", owner=p2, controller=p2)
        set_board_state(game, 1, graveyard=[opp_instant])
        assert card.cost_reduction(game) == 0

    def test_mixed_graveyard_counts_only_instant_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        cards_in_gy = [
            Instant(name="Bolt", owner=p1, controller=p1),
            Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2),
            Sorcery(name="Divination", owner=p1, controller=p1),
        ]
        set_board_state(game, 0, graveyard=cards_in_gy)
        assert card.cost_reduction(game) == 2

    def test_cost_reduction_with_five_instants_and_sorceries(self) -> None:
        """Cost reduction should scale linearly with graveyard count."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        cards_in_gy = [
            Instant(name=f"Instant{i}", owner=p1, controller=p1)
            for i in range(5)
        ]
        set_board_state(game, 0, graveyard=cards_in_gy)
        assert card.cost_reduction(game) == 5


# ---------------------------------------------------------------------------
# Attack trigger registration
# ---------------------------------------------------------------------------

class TestTheDawningArchaicAttackTriggerRegistration:
    """register_triggers must wire a trigger for AttacksTriggeredEvent."""

    def test_register_triggers_adds_at_least_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_attack_trigger_watches_attacks_triggered_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert any(
            t.event_type is AttacksTriggeredEvent for t in triggers
        )

    def test_attack_trigger_is_trigger_registration_instance(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        attacks_triggers = [
            t for t in triggers if t.event_type is AttacksTriggeredEvent
        ]
        assert len(attacks_triggers) >= 1
        assert all(isinstance(t, TriggerRegistration) for t in attacks_triggers)

    def test_attack_trigger_condition_matches_this_creature(self) -> None:
        """The trigger condition should be True when the attacker is this creature."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = [
            t for t in game.trigger_manager.get_triggers_for_source(card)
            if t.event_type is AttacksTriggeredEvent
        ]
        assert len(triggers) >= 1
        trigger = triggers[0]
        if trigger.condition is not None:
            event = AttacksTriggeredEvent(creature=card, attacker=card)
            assert trigger.condition(game, event) is True

    def test_attack_trigger_condition_does_not_match_other_creature(self) -> None:
        """The trigger condition should be False for a different attacker."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = [
            t for t in game.trigger_manager.get_triggers_for_source(card)
            if t.event_type is AttacksTriggeredEvent
        ]
        assert len(triggers) >= 1
        trigger = triggers[0]
        if trigger.condition is not None:
            other = Creature(name="Other", owner=p1, controller=p1, base_power=2, base_toughness=2)
            event = AttacksTriggeredEvent(creature=other, attacker=other)
            assert trigger.condition(game, event) is False

    def test_attack_trigger_pushed_to_stack_on_attacks_event(self) -> None:
        """Firing AttacksTriggeredEvent with the Archaic as attacker should
        push a stack object corresponding to the trigger."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        before = len(game.stack)
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        game.trigger_manager.fire_event(game, event)
        assert len(game.stack) > before


# ---------------------------------------------------------------------------
# Attack trigger effect: cast from graveyard + exile replacement
# ---------------------------------------------------------------------------

class TestTheDawningArchaicTriggerEffect:
    """The trigger effect should cast an instant/sorcery from the graveyard
    and ensure the cast spell ends up in exile (not the graveyard)."""

    def _get_attack_trigger(self, game, archaic):
        """Helper to retrieve the registered attack trigger."""
        return next(
            t for t in game.trigger_manager.get_triggers_for_source(archaic)
            if t.event_type is AttacksTriggeredEvent
        )

    def test_trigger_effect_removes_instant_from_graveyard(self) -> None:
        """After the trigger resolves, the chosen instant is no longer in
        the graveyard — it was cast."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant])

        trigger = self._get_attack_trigger(game, archaic)
        # Script: yes, cast; choose this instant
        p1._script.append(True)
        p1._script.append(instant)
        trigger.effect(game)

        assert instant not in p1.zones[Zone.GRAVEYARD].get_all()

    def test_trigger_effect_removes_sorcery_from_graveyard(self) -> None:
        """After the trigger resolves, the chosen sorcery is no longer in the graveyard."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[sorcery])

        trigger = self._get_attack_trigger(game, archaic)
        p1._script.append(True)
        p1._script.append(sorcery)
        trigger.effect(game)

        assert sorcery not in p1.zones[Zone.GRAVEYARD].get_all()

    def test_trigger_effect_no_op_when_graveyard_has_no_valid_spells(self) -> None:
        """With no instants or sorceries in the graveyard, the trigger
        should complete without raising."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        creature = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[creature])

        trigger = self._get_attack_trigger(game, archaic)
        trigger.effect(game)  # must not raise

        # Creature in graveyard remains untouched
        assert creature in p1.zones[Zone.GRAVEYARD].get_all()

    def test_trigger_effect_no_op_when_player_declines(self) -> None:
        """If the player chooses not to cast (says no / may), the graveyard
        is unchanged and the trigger completes without error."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        instant = Instant(name="Shock", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant])

        trigger = self._get_attack_trigger(game, archaic)
        p1._script.append(False)  # player says no
        trigger.effect(game)

        # Spell must remain in graveyard since player declined
        assert instant in p1.zones[Zone.GRAVEYARD].get_all()

    def test_cast_spell_goes_to_exile_not_graveyard(self) -> None:
        """After the trigger resolves, the spell that was cast from the
        graveyard must end up in exile, not the graveyard."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant])

        trigger = self._get_attack_trigger(game, archaic)
        p1._script.append(True)
        p1._script.append(instant)
        trigger.effect(game)

        exile = p1.zones[Zone.EXILE].get_all()
        graveyard = p1.zones[Zone.GRAVEYARD].get_all()
        assert instant in exile
        assert instant not in graveyard

    def test_cast_sorcery_goes_to_exile_not_graveyard(self) -> None:
        """Sorcery cast via trigger should also end up in exile."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[sorcery])

        trigger = self._get_attack_trigger(game, archaic)
        p1._script.append(True)
        p1._script.append(sorcery)
        trigger.effect(game)

        exile = p1.zones[Zone.EXILE].get_all()
        graveyard = p1.zones[Zone.GRAVEYARD].get_all()
        assert sorcery in exile
        assert sorcery not in graveyard
