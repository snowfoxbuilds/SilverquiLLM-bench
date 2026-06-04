"""Tests for SOS 1 — The Dawning Archaic.

The Dawning Archaic is a {10} Legendary Creature — Avatar, 7/7, with:

1. **Cost reduction** — "This spell costs {1} less to cast for each instant and
   sorcery card in your graveyard." Modeled via the ``cost_reduction(game)``
   hook (only generic mana is reduced).
2. **Reach** keyword.
3. **Attack trigger** — "Whenever The Dawning Archaic attacks, you may cast
   target instant or sorcery card from your graveyard without paying its mana
   cost. If that spell would be put into your graveyard, exile it instead."
   Modeled via ``register_triggers`` watching ``AttacksTriggeredEvent``.

These tests define the TDD contract; ``card_impl.py`` is a stub, so they are
expected to fail until the card is implemented.
"""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _instant(name: str = "Test Instant") -> Instant:
    """A vanilla instant card with a nonzero mana cost."""
    return Instant(name=name, mana_cost=ManaCost.parse("{1}{U}"))


def _sorcery(name: str = "Test Sorcery") -> Sorcery:
    """A vanilla sorcery card with a nonzero mana cost."""
    return Sorcery(name=name, mana_cost=ManaCost.parse("{2}{R}"))


def _vanilla_creature(name: str = "Grizzly Bears") -> Creature:
    c = Creature(name=name, base_power=2, base_toughness=2)
    c.card_types = {CardType.CREATURE}
    return c


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(TheDawningArchaic(owner=None), Creature)

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_power_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in TheDawningArchaic(owner=None).supertypes

    def test_is_avatar(self) -> None:
        assert "Avatar" in TheDawningArchaic(owner=None).subtypes

    def test_has_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords

    def test_is_colorless(self) -> None:
        """Cost is {10} generic only — the creature has no colored pips."""
        card = TheDawningArchaic(owner=None)
        assert card.mana_cost.pips == {}


# ---------------------------------------------------------------------------
# Cost reduction
# ---------------------------------------------------------------------------


class TestTheDawningArchaicCostReduction:
    """Costs {1} less for each instant and sorcery card in your graveyard."""

    def test_no_reduction_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_instant_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, graveyard=[_instant()])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 1

    def test_one_sorcery_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, graveyard=[_sorcery()])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 1

    def test_mixed_instants_and_sorceries_sum(self) -> None:
        game = create_game()
        p1 = game.players[0]
        set_board_state(
            game,
            0,
            graveyard=[_instant("I1"), _instant("I2"), _sorcery("S1")],
        )
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 3

    def test_noninstant_nonsorcery_cards_do_not_reduce(self) -> None:
        """Creatures and other cards in the graveyard do not reduce the cost."""
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, graveyard=[_vanilla_creature(), _vanilla_creature("Ogre")])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_only_your_graveyard_counts(self) -> None:
        """Instants/sorceries in the opponent's graveyard must not reduce cost."""
        game = create_game()
        p1 = game.players[0]
        # Opponent's graveyard full of spells.
        set_board_state(game, 1, graveyard=[_instant(), _sorcery(), _instant("X")])
        # Your graveyard has just one spell.
        set_board_state(game, 0, graveyard=[_sorcery("Mine")])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 1


# ---------------------------------------------------------------------------
# Attack trigger registration
# ---------------------------------------------------------------------------


class TestTheDawningArchaicTriggerRegistration:
    """register_triggers wires an AttacksTriggeredEvent trigger."""

    def test_registers_one_attack_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after - before == 1

    def test_registered_trigger_watches_attacks_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        regs = game.trigger_manager.get_triggers_for_source(card)
        assert len(regs) == 1
        reg = regs[0]
        assert isinstance(reg, TriggerRegistration)
        assert reg.event_type is AttacksTriggeredEvent

    def test_trigger_condition_matches_self_attacking(self) -> None:
        """The trigger's condition should fire only when this card attacks."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        reg = game.trigger_manager.get_triggers_for_source(card)[0]
        if reg.condition is None:
            # An always-fire trigger is acceptable; the effect must self-guard.
            return
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        assert reg.condition(game, event) is True

    def test_trigger_condition_ignores_other_attacker(self) -> None:
        """A different creature attacking must not satisfy the condition."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        reg = game.trigger_manager.get_triggers_for_source(card)[0]
        if reg.condition is None:
            return
        other = _vanilla_creature()
        event = AttacksTriggeredEvent(creature=other, attacker=other)
        assert reg.condition(game, event) is False


# ---------------------------------------------------------------------------
# Attack-trigger targeting
# ---------------------------------------------------------------------------


class TestTheDawningArchaicTargeting:
    """The attack trigger targets an instant or sorcery in your graveyard."""

    def test_get_targets_advertises_graveyard_zone(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert reqs[0].zone == Zone.GRAVEYARD

    def test_target_filter_accepts_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        req = card.get_targets(game)[0]
        assert req.filter_fn(_instant()) is True

    def test_target_filter_accepts_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        req = card.get_targets(game)[0]
        assert req.filter_fn(_sorcery()) is True

    def test_target_filter_rejects_creature(self) -> None:
        """A creature card in the graveyard is not a legal target."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        req = card.get_targets(game)[0]
        assert req.filter_fn(_vanilla_creature()) is False


# ---------------------------------------------------------------------------
# Attack-trigger effect: free cast from graveyard
# ---------------------------------------------------------------------------


def _fire_attack_trigger(game, card) -> None:
    """Register the card's triggers and fire an attack event for it."""
    card.register_triggers(game)
    game.trigger_manager.fire_event(
        game, AttacksTriggeredEvent(creature=card, attacker=card)
    )


class TestTheDawningArchaicFreeCast:
    """The attack trigger casts a targeted instant/sorcery from the graveyard
    without paying its mana cost."""

    def test_targeted_spell_leaves_graveyard_when_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = _sorcery("Lava Spike")
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])
        # Direct the chosen target to the spell.
        archaic.chosen_targets = [spell]

        _fire_attack_trigger(game, archaic)
        # Resolve the trigger on the stack.
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        # The spell should no longer be sitting in the graveyard — it was put
        # on the stack (free-cast) and resolved out of the graveyard.
        assert not game.get_graveyard(p1).contains(spell)

    def test_no_mana_required_for_free_cast(self) -> None:
        """The controller pays nothing — an empty mana pool still casts."""
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = _sorcery("Lava Spike")
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell], mana={})
        archaic.chosen_targets = [spell]

        _fire_attack_trigger(game, archaic)
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        # With no mana available, the spell still left the graveyard,
        # proving the cast did not require mana payment.
        assert not game.get_graveyard(p1).contains(spell)


# ---------------------------------------------------------------------------
# Replacement: exile instead of graveyard
# ---------------------------------------------------------------------------


class TestTheDawningArchaicExileReplacement:
    """"If that spell would be put into your graveyard, exile it instead."

    After a free-cast instant/sorcery resolves, it should end up in exile,
    not back in the graveyard.
    """

    def test_free_cast_spell_is_exiled_after_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = _sorcery("Lava Spike")
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])
        archaic.chosen_targets = [spell]

        _fire_attack_trigger(game, archaic)
        # Resolve the trigger (free-cast) and then the spell itself.
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        # The replacement redirects the post-resolution move to exile.
        assert game.players[0].zones[Zone.EXILE].contains(spell)
        assert not game.get_graveyard(p1).contains(spell)


# ---------------------------------------------------------------------------
# No-op / edge cases
# ---------------------------------------------------------------------------


class TestTheDawningArchaicNoOp:
    """Defensive cases: no legal target, no chosen target."""

    def test_no_target_chosen_is_a_noop(self) -> None:
        """Firing the trigger without a chosen target must not raise and must
        not move any card out of the graveyard."""
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = _sorcery("Lava Spike")
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])
        # No chosen_targets set.

        _fire_attack_trigger(game, archaic)
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        # Nothing chosen → the spell stays in the graveyard.
        assert game.get_graveyard(p1).contains(spell)

    def test_empty_graveyard_no_targets_available(self) -> None:
        """With no instants/sorceries in the graveyard, no legal targets."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[])
        req = archaic.get_targets(game)[0]
        # The filter still describes instant-or-sorcery, but no card in the
        # (empty) graveyard satisfies it.
        gy = game.get_graveyard(p1).get_all()
        legal = [c for c in gy if req.filter_fn(c)]
        assert legal == []
