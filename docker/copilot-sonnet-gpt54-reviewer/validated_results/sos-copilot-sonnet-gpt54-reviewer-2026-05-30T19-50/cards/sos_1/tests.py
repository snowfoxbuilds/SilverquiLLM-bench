"""Tests for The Dawning Archaic (sos_1).

Covers:
- Static card properties (name, mana cost, type, P/T, keyword, supertype, subtype)
- Mana cost reduction (1 less per instant/sorcery in controller's graveyard)
- Reach keyword
- Attack trigger (register_triggers registers on AttacksTriggeredEvent)
- Trigger fires only when this creature attacks, not other creatures
- Trigger causes graveyard instant/sorcery to leave the graveyard (cast)
- Exile replacement: cast spell ends in exile, not graveyard
"""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestTheDawningArchaicProperties:
    """Static card data must match the sos_1 spec."""

    def test_name(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.mana_cost == ManaCost.parse("{10}")

    def test_base_power(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7

    def test_base_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_toughness == 7

    def test_is_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_has_legendary_supertype(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtype_is_avatar(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert "Avatar" in card.subtypes

    def test_has_reach_keyword(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.keywords & Keyword.REACH


# ---------------------------------------------------------------------------
# Mana cost reduction
# ---------------------------------------------------------------------------

class TestTheDawningArchaicCostReduction:
    """cost_reduction() returns 1 per instant/sorcery in controller's graveyard."""

    def test_no_reduction_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_instant_gives_one_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant])
        assert card.cost_reduction(game) == 1

    def test_one_sorcery_gives_one_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[sorcery])
        assert card.cost_reduction(game) == 1

    def test_three_instants_give_three_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_cards = [
            Instant(name=f"Instant {i}", owner=p1, controller=p1)
            for i in range(3)
        ]
        set_board_state(game, 0, graveyard=graveyard_cards)
        assert card.cost_reduction(game) == 3

    def test_mixed_instants_and_sorceries_counted(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Shock", owner=p1, controller=p1)
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant, sorcery])
        assert card.cost_reduction(game) == 2

    def test_creatures_in_graveyard_do_not_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        creature = Creature(
            name="Grizzly Bears", base_power=2, base_toughness=2,
            owner=p1, controller=p1,
        )
        set_board_state(game, 0, graveyard=[creature])
        assert card.cost_reduction(game) == 0

    def test_only_controllers_graveyard_counts(self) -> None:
        """Instants/sorceries in the opponent's graveyard must NOT reduce cost."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Lightning Bolt", owner=p2, controller=p2)
        set_board_state(game, 1, graveyard=[instant])
        assert card.cost_reduction(game) == 0

    def test_ten_instants_give_ten_reduction(self) -> None:
        """Raw cost_reduction returns count; engine clamps to generic mana floor."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_cards = [
            Instant(name=f"Instant {i}", owner=p1, controller=p1)
            for i in range(10)
        ]
        set_board_state(game, 0, graveyard=graveyard_cards)
        assert card.cost_reduction(game) == 10


# ---------------------------------------------------------------------------
# Attack trigger registration
# ---------------------------------------------------------------------------

class TestTheDawningArchaicAttackTrigger:
    """register_triggers() registers an AttacksTriggeredEvent trigger."""

    def test_register_triggers_adds_trigger_for_source(self) -> None:
        """After register_triggers, this card has at least one registered trigger."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) >= 1

    def test_registered_trigger_watches_attacks_event(self) -> None:
        """The trigger registered for this card must watch AttacksTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert any(t.event_type is AttacksTriggeredEvent for t in triggers)

    def test_trigger_pushes_stack_object_when_archaic_attacks(self) -> None:
        """Firing AttacksTriggeredEvent with The Dawning Archaic pushes onto stack."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        stack_before = len(game.stack)
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=card, attacker=card)
        )
        assert len(game.stack) > stack_before

    def test_trigger_does_not_fire_for_other_creatures(self) -> None:
        """The trigger must NOT fire when a different creature is the attacker."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        other = Creature(
            name="Grizzly Bears", base_power=2, base_toughness=2,
            owner=p1, controller=p1,
        )
        stack_before = len(game.stack)
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=other, attacker=other)
        )
        assert len(game.stack) == stack_before


# ---------------------------------------------------------------------------
# Attack trigger effect: cast instant/sorcery from graveyard
# ---------------------------------------------------------------------------

class TestTheDawningArchaicAttackEffect:
    """Resolving the attack trigger removes an instant/sorcery from the graveyard."""

    def _resolve_trigger(self, game):
        """Helper: resolve the top stack object's effect."""
        top = game.stack.peek()
        if top is not None:
            top.on_resolve(game)

    def test_attack_trigger_removes_instant_from_graveyard(self) -> None:
        """After trigger resolves, the instant is no longer in the graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Shock", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=card, attacker=card)
        )
        self._resolve_trigger(game)

        assert instant not in game.get_graveyard(p1).get_all()

    def test_attack_trigger_removes_sorcery_from_graveyard(self) -> None:
        """After trigger resolves, the sorcery is no longer in the graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[sorcery])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=card, attacker=card)
        )
        self._resolve_trigger(game)

        assert sorcery not in game.get_graveyard(p1).get_all()

    def test_attack_trigger_with_empty_graveyard_does_not_raise(self) -> None:
        """If there are no instants/sorceries in graveyard, trigger is a no-op."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=card, attacker=card)
        )
        # Must not raise; trigger resolves gracefully
        self._resolve_trigger(game)

    def test_attack_trigger_ignores_creature_in_graveyard(self) -> None:
        """A creature in the graveyard is not a valid target; it stays there."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        creature = Creature(
            name="Bear", base_power=2, base_toughness=2,
            owner=p1, controller=p1,
        )
        set_board_state(game, 0, graveyard=[creature])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=card, attacker=card)
        )
        self._resolve_trigger(game)

        # Creature was not cast — it must remain in the graveyard
        assert creature in game.get_graveyard(p1).get_all()

    def test_attack_trigger_only_targets_own_graveyard(self) -> None:
        """Cards in the OPPONENT's graveyard must not be cast by the trigger."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TheDawningArchaic(owner=p1, controller=p1)

        # Opponent has instants in graveyard; p1's graveyard is empty
        opp_instant = Instant(name="Counterspell", owner=p2, controller=p2)
        set_board_state(game, 1, graveyard=[opp_instant])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=card, attacker=card)
        )
        self._resolve_trigger(game)

        # Opponent's card should remain in their graveyard
        assert opp_instant in game.get_graveyard(p2).get_all()
        # And should NOT have moved to exile or anywhere on p1's side
        assert opp_instant not in game.get_exile(p1).get_all()
        assert opp_instant not in game.get_graveyard(p1).get_all()

# ---------------------------------------------------------------------------
# Exile replacement: spell cast via trigger goes to exile, not graveyard
# ---------------------------------------------------------------------------

class TestTheDawningArchaicExileReplacement:
    """The spell cast via the attack trigger must end in exile after it resolves."""

    def _fire_and_resolve_all(self, game, card):
        """Helper: fire the attack trigger then drain the stack (LIFO).

        The trigger effect itself fires, which may push a new spell StackObject.
        We resolve all stack objects until empty so the complete sequence runs.
        """
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=card, attacker=card)
        )
        # Resolve everything on the stack (LIFO) until empty.
        while not game.stack.is_empty():
            top = game.stack.pop()
            top.on_resolve(game)

    def test_cast_spell_ends_in_exile_not_graveyard(self) -> None:
        """Instant cast by the trigger ends in exile, not graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Shock", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant])
        card.register_triggers(game)

        self._fire_and_resolve_all(game, card)

        # Spell must be in exile
        assert instant in game.get_exile(p1).get_all(), (
            "Spell cast via Dawning Archaic trigger must end in exile"
        )
        # Spell must NOT be in graveyard
        assert instant not in game.get_graveyard(p1).get_all(), (
            "Spell cast via Dawning Archaic trigger must not stay in graveyard"
        )

    def test_sorcery_cast_via_trigger_ends_in_exile(self) -> None:
        """Sorcery cast by the trigger also ends in exile."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[sorcery])
        card.register_triggers(game)

        self._fire_and_resolve_all(game, card)

        assert sorcery in game.get_exile(p1).get_all(), (
            "Sorcery cast via Dawning Archaic trigger must end in exile"
        )
        assert sorcery not in game.get_graveyard(p1).get_all()
