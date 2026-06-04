"""Tests for SOS 1 — The Dawning Archaic.

Oracle text (from card_spec.json):

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost. If that
    spell would be put into your graveyard, exile it instead.

The behaviour contract derived from that text:

* It is a Legendary Creature — Avatar, 7/7, {10}, colorless, with Reach.
* Cost reduction: the generic portion of {10} is reduced by {1} for each
  instant **or sorcery** card currently in the controller's graveyard
  (creatures / lands / other types do not count). The reduction is clamped
  by the engine so generic mana never goes below 0.
* Attack trigger: an ``AttacksTriggeredEvent`` whose source is this card
  registers a trigger. Its effect is *optional* ("you may"): the controller
  is offered the choice to cast a target instant or sorcery from their
  graveyard for free. A "no" choice (or an empty graveyard) is a no-op.
* When the chosen spell would be put into the graveyard, it is exiled
  instead — so after the cast resolves the spell card is in exile, not in
  the graveyard.

These tests are written for the TDD red phase: they must FAIL against the
empty stub and PASS once the card is implemented correctly.
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Test helper spells placed in the graveyard
# ---------------------------------------------------------------------------


class _ResolveMarkerInstant(Instant):
    """A simple instant whose resolution gains its controller 5 life.

    Used as the target spell cast from the graveyard so that tests can
    observe (a) that the spell actually resolved, and (b) where the card
    ends up afterwards (exile vs graveyard).
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Marker Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)
        self.resolved_count = 0

    def on_resolve(self, game: Any) -> None:
        self.resolved_count += 1
        controller = self.controller
        if controller is not None:
            controller.life += 5


def _vanilla_instant(name: str = "Test Instant") -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{1}{R}"))


def _vanilla_sorcery(name: str = "Test Sorcery") -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse("{2}{B}"))


def _vanilla_creature(name: str = "Test Bear") -> Creature:
    return Creature(name=name, mana_cost=ManaCost.parse("{1}{G}"),
                    base_power=2, base_toughness=2)


def _resolve_full_stack(game: Any) -> None:
    """Resolve every object currently on the stack, top-down.

    Mirrors ``test_utils._resolve_top_of_stack`` but is local so it can be
    reused after firing the attack trigger (whose resolution may itself push
    the free-cast spell onto the stack).
    """
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------


class TestTheDawningArchaicProperties:
    """Static characteristics must match the SOS 1 spec."""

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

    def test_is_colorless_all_generic(self) -> None:
        """{10} is purely generic mana — mana value 10 with no colored pips,
        so the card is colorless."""
        cost = TheDawningArchaic(owner=None).mana_cost
        assert cost.cmc == 10
        assert cost.generic == 10
        assert all(v == 0 for v in cost.pips.values())


# ---------------------------------------------------------------------------
# Cost reduction
# ---------------------------------------------------------------------------


class TestTheDawningArchaicCostReduction:
    """{1} less for each instant and sorcery card in your graveyard."""

    def test_no_reduction_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_instant_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[_vanilla_instant()])
        assert card.cost_reduction(game) == 1

    def test_one_sorcery_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[_vanilla_sorcery()])
        assert card.cost_reduction(game) == 1

    def test_instants_and_sorceries_both_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            graveyard=[
                _vanilla_instant("I1"),
                _vanilla_instant("I2"),
                _vanilla_sorcery("S1"),
            ],
        )
        assert card.cost_reduction(game) == 3

    def test_non_instant_sorcery_cards_do_not_count(self) -> None:
        """Creatures (and other non-spell cards) in the graveyard do not
        reduce the cost."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            graveyard=[_vanilla_creature("Bear A"), _vanilla_creature("Bear B")],
        )
        assert card.cost_reduction(game) == 0

    def test_only_controllers_graveyard_counts(self) -> None:
        """Instants/sorceries in the *opponent's* graveyard must not reduce
        the cost — only "your graveyard" matters."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        # Opponent has three instants; controller's graveyard is empty.
        set_board_state(
            game,
            1,
            graveyard=[
                _vanilla_instant("O1"),
                _vanilla_instant("O2"),
                _vanilla_sorcery("O3"),
            ],
        )
        assert card.cost_reduction(game) == 0

    def test_effective_reduction_clamped_to_generic(self) -> None:
        """The engine clamps the reduction to the generic portion (10), so a
        graveyard with more than 10 spells cannot push generic below 0."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        gy = [_vanilla_instant(f"I{i}") for i in range(13)]
        set_board_state(game, 0, graveyard=gy)
        # Raw hook may report 13, but the clamped effective reduction is 10.
        assert get_cost_reduction(game, card, p1) == 10

    def test_partial_reduction_value_through_engine(self) -> None:
        """A graveyard with four spells reduces the {10} generic by exactly 4
        through the engine's clamp helper."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            graveyard=[
                _vanilla_instant("A"),
                _vanilla_instant("B"),
                _vanilla_sorcery("C"),
                _vanilla_sorcery("D"),
            ],
        )
        assert get_cost_reduction(game, card, p1) == 4


# ---------------------------------------------------------------------------
# Attack trigger
# ---------------------------------------------------------------------------


class TestTheDawningArchaicAttackTriggerRegistration:
    """register_triggers wires an AttacksTriggeredEvent trigger."""

    def test_registers_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after - before == 1

    def test_trigger_watches_attacks_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        regs = game.trigger_manager.get_triggers_for_source(card)
        assert len(regs) == 1
        reg = regs[0]
        assert isinstance(reg, TriggerRegistration)
        assert reg.event_type is AttacksTriggeredEvent

    def test_trigger_only_fires_when_this_card_attacks(self) -> None:
        """A different creature attacking must not fire this card's trigger."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], graveyard=[_vanilla_instant()])
        card.register_triggers(game)

        other = _vanilla_creature("Some Other Bear")
        other.owner = p1
        other.controller = p1
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=other, attacker=other)
        )
        assert game.stack.is_empty()

    def test_trigger_fires_when_this_card_attacks(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], graveyard=[_vanilla_instant()])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=card, attacker=card)
        )
        assert not game.stack.is_empty()
        assert game.stack.peek().source is card


class TestTheDawningArchaicRecast:
    """Resolving the attack trigger casts a chosen graveyard spell for free."""

    def _setup_attack(self, target_spell: Any, *, yes: bool = True):
        """Create a game where The Dawning Archaic is on the battlefield with
        *target_spell* in its controller's graveyard, fire the attack
        trigger, and return ``(game, p1, card)``.

        The controller is scripted to answer the optional "you may" choice
        with *yes* and to select *target_spell* as the target.
        """
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], graveyard=[target_spell])
        # Make p1 the active player so APNAP ordering and "your" references
        # resolve to p1.
        game.active_player_index = 0
        card.register_triggers(game)

        # Script the controller's decisions. The implementation may ask for a
        # yes/no ("may cast") and/or a target/card choice; we feed both a
        # boolean and the target spell so whichever methods it calls are
        # satisfied (DeterministicPlayer pops answers in order).
        p1._script.extend([yes, target_spell, target_spell])

        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=card, attacker=card)
        )
        return game, p1, card

    def test_chosen_spell_resolves_for_free(self) -> None:
        """Saying yes casts the chosen instant; its effect (gain 5 life)
        happens even though no mana is paid."""
        spell = _ResolveMarkerInstant()
        game, p1, card = self._setup_attack(spell, yes=True)
        # Drain p1's mana pool to prove the recast is free.
        p1.mana_pool.empty()
        life_before = p1.life
        _resolve_full_stack(game)
        assert spell.resolved_count == 1
        assert p1.life == life_before + 5

    def test_recast_spell_is_exiled_not_in_graveyard(self) -> None:
        """"If that spell would be put into your graveyard, exile it instead."
        After the free cast resolves, the spell card is in exile and NOT back
        in the graveyard."""
        spell = _ResolveMarkerInstant()
        game, p1, card = self._setup_attack(spell, yes=True)
        _resolve_full_stack(game)
        graveyard_cards = game.get_graveyard(p1).get_all()
        exile_cards = p1.zones[Zone.EXILE].get_all()
        assert spell not in graveyard_cards
        assert spell in exile_cards

    def test_spell_leaves_graveyard_when_cast(self) -> None:
        """While on the stack / after resolving, the spell is no longer in
        the graveyard zone it was cast from."""
        spell = _ResolveMarkerInstant()
        game, p1, card = self._setup_attack(spell, yes=True)
        _resolve_full_stack(game)
        assert not game.get_graveyard(p1).contains(spell)

    def test_optional_decline_leaves_spell_in_graveyard(self) -> None:
        """Saying no to the optional "you may" leaves the spell untouched in
        the graveyard and does not resolve its effect."""
        spell = _ResolveMarkerInstant()
        game, p1, card = self._setup_attack(spell, yes=False)
        life_before = p1.life
        _resolve_full_stack(game)
        assert spell.resolved_count == 0
        assert game.get_graveyard(p1).contains(spell)
        assert p1.life == life_before

    def test_empty_graveyard_is_noop(self) -> None:
        """With no instant/sorcery in the graveyard, resolving the attack
        trigger does nothing and does not raise."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], graveyard=[])
        game.active_player_index = 0
        card.register_triggers(game)
        # Provide a permissive script in case the effect still asks anything.
        p1._script.extend([True, None, None])

        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=card, attacker=card)
        )
        # Resolving must not raise even though there is nothing to cast.
        _resolve_full_stack(game)
        assert p1.life == 20

    def test_can_target_a_sorcery(self) -> None:
        """The trigger can cast a sorcery (not just an instant) from the
        graveyard; the sorcery leaves the graveyard and is exiled on
        resolution."""
        sorcery = Sorcery(name="Free Sorcery", mana_cost=ManaCost.parse("{2}{B}"))
        game, p1, card = self._setup_attack(sorcery, yes=True)
        _resolve_full_stack(game)
        assert not game.get_graveyard(p1).contains(sorcery)
        assert p1.zones[Zone.EXILE].contains(sorcery)
