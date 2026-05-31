"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from collections import deque

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_instant(name: str = "Lightning Bolt") -> Instant:
    card = Instant(name=name, mana_cost=ManaCost.parse("{R}"))
    return card


def _make_sorcery(name: str = "Divination") -> Sorcery:
    card = Sorcery(name=name, mana_cost=ManaCost.parse("{2}{U}"))
    return card


def _make_creature_card(name: str = "Grizzly Bears") -> Creature:
    return Creature(name=name, mana_cost=ManaCost.parse("{1}{G}"), base_power=2, base_toughness=2)


def _resolve_stack(game):
    """Drain the stack completely."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


# ---------------------------------------------------------------------------
# 1. Card Identity
# ---------------------------------------------------------------------------

class TestTheDawningArchaicIdentity:
    """Static card properties must match the card spec."""

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_base_power(self) -> None:
        assert TheDawningArchaic(owner=None).base_power == 7

    def test_base_toughness(self) -> None:
        assert TheDawningArchaic(owner=None).base_toughness == 7

    def test_has_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords

    def test_is_creature(self) -> None:
        assert isinstance(TheDawningArchaic(owner=None), Creature)

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in TheDawningArchaic(owner=None).supertypes

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_avatar_subtype(self) -> None:
        assert "Avatar" in TheDawningArchaic(owner=None).subtypes


# ---------------------------------------------------------------------------
# 2. Cost Reduction
# ---------------------------------------------------------------------------

class TestCostReduction:
    """cost_reduction() returns 1 per instant/sorcery in controller's graveyard."""

    def test_empty_graveyard_gives_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[])
        assert card.cost_reduction(game) == 0

    def test_creature_only_in_graveyard_gives_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[_make_creature_card()])
        assert card.cost_reduction(game) == 0

    def test_one_instant_gives_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[_make_instant()])
        assert card.cost_reduction(game) == 1

    def test_one_sorcery_gives_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[_make_sorcery()])
        assert card.cost_reduction(game) == 1

    def test_mixed_spells_count_correctly(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[
            _make_instant("I1"), _make_sorcery("S1"), _make_creature_card("C1"), _make_instant("I2"),
        ])
        assert card.cost_reduction(game) == 3  # 2 instants + 1 sorcery

    def test_opponent_graveyard_does_not_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[])
        set_board_state(game, 1, graveyard=[_make_instant(), _make_sorcery()])
        assert card.cost_reduction(game) == 0

    def test_ten_spells_reduces_by_ten(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        spells = [_make_instant(f"I{i}") for i in range(10)]
        set_board_state(game, 0, graveyard=spells)
        assert card.cost_reduction(game) == 10

    def test_no_controller_returns_zero(self) -> None:
        game = create_game()
        card = TheDawningArchaic()
        assert card.cost_reduction(game) == 0


# ---------------------------------------------------------------------------
# 3. Attack Trigger Registration
# ---------------------------------------------------------------------------

class TestAttackTriggerRegistration:

    def test_register_triggers_adds_attack_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        event_types = [t.event_type for t in triggers]
        assert AttacksTriggeredEvent in event_types

    def test_trigger_condition_true_for_self(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = [t for t in game.trigger_manager.get_triggers_for_source(card)
                    if t.event_type is AttacksTriggeredEvent]
        assert triggers
        condition = triggers[0].condition
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        assert condition is None or condition(game, event) is True

    def test_trigger_condition_false_for_other_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = [t for t in game.trigger_manager.get_triggers_for_source(card)
                    if t.event_type is AttacksTriggeredEvent]
        assert triggers
        condition = triggers[0].condition
        other = Creature(name="Other", owner=p1, controller=p1)
        event = AttacksTriggeredEvent(creature=other, attacker=other)
        if condition is not None:
            assert condition(game, event) is False

    def test_trigger_fires_pushes_to_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        assert game.stack.is_empty()
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=card, attacker=card))
        assert not game.stack.is_empty()

    def test_trigger_does_not_fire_for_other_attacker(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        other = Creature(name="Other", owner=p1, controller=p1)
        assert game.stack.is_empty()
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=other, attacker=other))
        assert game.stack.is_empty()


# ---------------------------------------------------------------------------
# 4 & 5. Attack Effect + Exile Replacement
# ---------------------------------------------------------------------------

class TestAttackTriggerEffect:

    def _setup(self, game, graveyard_spells=None, battlefield_extras=None):
        """Helper to set up p1 with archaic and graveyard spells."""
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        bf = [archaic] + (battlefield_extras or [])
        gy = []
        for s in (graveyard_spells or []):
            s.owner = p1
            s.controller = p1
            gy.append(s)
        set_board_state(game, 0, battlefield=bf, graveyard=gy)
        archaic.register_triggers(game)
        return p1, archaic

    def test_no_instants_or_sorceries_resolves_cleanly(self) -> None:
        game = create_game()
        p1, archaic = self._setup(game, graveyard_spells=[_make_creature_card()])
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=archaic))
        _resolve_stack(game)  # must not raise

    def test_empty_graveyard_resolves_cleanly(self) -> None:
        game = create_game()
        p1, archaic = self._setup(game)
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=archaic))
        _resolve_stack(game)  # must not raise

    def test_player_declines_spell_stays_in_graveyard(self) -> None:
        game = create_game()
        instant = _make_instant("Bolt")
        p1, archaic = self._setup(game, graveyard_spells=[instant])
        # Script: player says NO
        p1._script = deque([False])
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=archaic))
        _resolve_stack(game)
        gy = p1.zones[Zone.GRAVEYARD].get_all()
        assert instant in gy, "Spell should remain in graveyard when player declines"

    def test_instant_cast_from_graveyard_goes_to_exile(self) -> None:
        """After casting via trigger, instant ends in exile not graveyard."""
        game = create_game()
        instant = _make_instant("Bolt")
        p1, archaic = self._setup(game, graveyard_spells=[instant])
        # Script: yes + pick the instant
        p1._script = deque([True, instant])
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=archaic))
        _resolve_stack(game)
        exile = p1.zones[Zone.EXILE].get_all()
        gy = p1.zones[Zone.GRAVEYARD].get_all()
        assert instant in exile, f"Instant should be in exile. Exile={[c.name for c in exile]}, GY={[c.name for c in gy]}"
        assert instant not in gy, "Instant should NOT be in graveyard after exile replacement"

    def test_sorcery_cast_from_graveyard_goes_to_exile(self) -> None:
        """After casting via trigger, sorcery ends in exile not graveyard."""
        game = create_game()
        sorcery = _make_sorcery("Divination")
        p1, archaic = self._setup(game, graveyard_spells=[sorcery])
        p1._script = deque([True, sorcery])
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=archaic))
        _resolve_stack(game)
        exile = p1.zones[Zone.EXILE].get_all()
        gy = p1.zones[Zone.GRAVEYARD].get_all()
        assert sorcery in exile, f"Sorcery should be in exile. Exile={[c.name for c in exile]}"
        assert sorcery not in gy, "Sorcery should NOT be in graveyard"

    def test_other_graveyard_cards_unaffected(self) -> None:
        """Other cards in graveyard should remain in graveyard after casting one spell."""
        game = create_game()
        instant1 = _make_instant("Bolt")
        instant2 = _make_instant("Shock")
        creature_gy = _make_creature_card("Bear")
        p1, archaic = self._setup(game, graveyard_spells=[instant1, instant2, creature_gy])
        # Cast only the first instant
        p1._script = deque([True, instant1])
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=archaic))
        _resolve_stack(game)
        gy = p1.zones[Zone.GRAVEYARD].get_all()
        exile = p1.zones[Zone.EXILE].get_all()
        assert instant1 in exile
        assert instant2 in gy, "Unchosen instant should stay in graveyard"
        assert creature_gy in gy, "Creature should stay in graveyard"

    def test_exile_flag_is_cleaned_up_after_resolution(self) -> None:
        """_exile_on_resolve should not linger on the card after resolution."""
        game = create_game()
        instant = _make_instant("Bolt")
        p1, archaic = self._setup(game, graveyard_spells=[instant])
        p1._script = deque([True, instant])
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=archaic))
        _resolve_stack(game)
        assert not hasattr(instant, "_exile_on_resolve"), "Flag should be cleaned up after use"
