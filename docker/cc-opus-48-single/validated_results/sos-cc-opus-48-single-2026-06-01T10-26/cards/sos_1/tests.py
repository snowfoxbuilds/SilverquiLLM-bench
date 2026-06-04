"""Tests for SOS 1 — The Dawning Archaic.

The Dawning Archaic ({10} Legendary Creature — Avatar, 7/7) has three
distinct pieces of behaviour, each covered by its own test class:

1. **Static card data** — name, mana cost, P/T, legendary supertype,
   Avatar subtype, Reach keyword, and creature type.

2. **Cost reduction** — "This spell costs {1} less to cast for each
   instant and sorcery card in your graveyard."  Modelled via
   ``cost_reduction(game)`` (see ``engine.card.CardImpl.cost_reduction``
   and ``engine.casting.get_cost_reduction``): the engine only reduces
   generic mana and clamps at the printed generic value.

3. **Attack trigger** — "Whenever The Dawning Archaic attacks, you may
   cast target instant or sorcery card from your graveyard without
   paying its mana cost..."  Modelled via ``register_triggers`` wiring an
   ``AttacksTriggeredEvent`` trigger whose condition is keyed to this
   creature.

These are TDD red-phase tests: the stub at ``card_impl.py`` is empty, so
everything here is expected to fail until the card is implemented.
"""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


def _instant(name: str = "Test Bolt") -> Instant:
    """A vanilla instant card for graveyard setup."""
    return Instant(name=name, mana_cost=ManaCost.parse("{R}"))


def _sorcery(name: str = "Test Divination") -> Sorcery:
    """A vanilla sorcery card for graveyard setup."""
    return Sorcery(name=name, mana_cost=ManaCost.parse("{2}{U}"))


def _vanilla_creature(name: str = "Grizzly Bears") -> Creature:
    """A vanilla creature card for graveyard setup (not instant/sorcery)."""
    return Creature(name=name, base_power=2, base_toughness=2)


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost_is_ten_generic(self) -> None:
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

    def test_no_flying(self) -> None:
        # Reach is not Flying — guard against an over-broad keyword set.
        assert Keyword.FLYING not in TheDawningArchaic(owner=None).keywords


class TestTheDawningArchaicCostReduction:
    """cost_reduction() reflects instant/sorcery cards in the controller's
    graveyard. Only generic mana is reduced; the printed cost is {10}."""

    def test_no_reduction_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[])
        assert card.cost_reduction(game) == 0

    def test_one_instant_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[_instant()])
        assert card.cost_reduction(game) == 1

    def test_counts_both_instants_and_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            graveyard=[_instant("A"), _instant("B"), _sorcery("C")],
        )
        assert card.cost_reduction(game) == 3

    def test_ignores_non_instant_sorcery_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        # Two creatures + one instant: only the instant should count.
        set_board_state(
            game,
            0,
            graveyard=[_vanilla_creature("X"), _vanilla_creature("Y"), _instant("Z")],
        )
        assert card.cost_reduction(game) == 1

    def test_ignores_opponent_graveyard(self) -> None:
        """'in your graveyard' — opponent's instants must not reduce cost."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[])
        set_board_state(game, 1, graveyard=[_instant("Opp1"), _sorcery("Opp2")])
        assert card.cost_reduction(game) == 0

    def test_reduction_never_negative(self) -> None:
        """cost_reduction returns a non-negative integer regardless of count."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[])
        assert card.cost_reduction(game) >= 0

    def test_large_graveyard_can_exceed_printed_generic(self) -> None:
        """cost_reduction reports the raw per-card count; the engine clamps
        it to the printed generic at payment time (get_cost_reduction).

        With 12 instants the raw reduction is at least the printed generic
        of 10, so the spell becomes free after clamping.
        """
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        gy = [_instant(f"I{i}") for i in range(12)]
        set_board_state(game, 0, graveyard=gy)
        assert card.cost_reduction(game) >= 10


class TestTheDawningArchaicCostReductionPayment:
    """The engine's get_cost_reduction clamps the reduction to the printed
    generic, so the effective payable cost never goes below zero."""

    def test_engine_clamps_reduction_to_generic(self) -> None:
        from engine.casting import get_cost_reduction

        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        gy = [_instant(f"I{i}") for i in range(15)]
        set_board_state(game, 0, graveyard=gy)
        # Printed generic is 10; reduction is clamped to at most 10.
        assert get_cost_reduction(game, card, p1) == 10

    def test_engine_reduction_matches_count_when_below_generic(self) -> None:
        from engine.casting import get_cost_reduction

        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[_instant("A"), _sorcery("B")])
        assert get_cost_reduction(game, card, p1) == 2


class TestTheDawningArchaicAttackTrigger:
    """register_triggers wires an AttacksTriggeredEvent trigger keyed to
    this creature for the 'whenever ~ attacks' ability."""

    def test_registers_attack_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers_for_source(card))
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers_for_source(card))
        assert after - before == 1

    def test_trigger_watches_attacks_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        regs = game.trigger_manager.get_triggers_for_source(card)
        assert len(regs) == 1
        assert regs[0].event_type is AttacksTriggeredEvent

    def test_trigger_controller_is_card_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        reg = game.trigger_manager.get_triggers_for_source(card)[0]
        assert reg.controller is p1

    def test_trigger_condition_fires_for_self(self) -> None:
        """The trigger should fire when *this* creature attacks."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        reg = game.trigger_manager.get_triggers_for_source(card)[0]
        # A trigger with no condition always fires; otherwise it must accept
        # an AttacksTriggeredEvent naming this creature as the attacker.
        if reg.condition is None:
            return
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        assert reg.condition(game, event) is True

    def test_trigger_condition_ignores_other_attacker(self) -> None:
        """The trigger must not fire when a different creature attacks."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        reg = game.trigger_manager.get_triggers_for_source(card)[0]
        if reg.condition is None:
            # A condition-less trigger would fire for every attacker, which
            # contradicts "Whenever The Dawning Archaic attacks".
            raise AssertionError(
                "Attack trigger must be conditioned on this creature attacking"
            )
        other = _vanilla_creature("Other Attacker")
        other.owner = p1
        other.controller = p1
        event = AttacksTriggeredEvent(creature=other, attacker=other)
        assert reg.condition(game, event) is False


class TestTheDawningArchaicAttackTriggerEffect:
    """Firing the attack event pushes the triggered ability onto the stack."""

    def test_attack_event_pushes_trigger_onto_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], graveyard=[_instant("Bolt")])
        card.register_triggers(game)
        assert game.stack.is_empty()
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=card, attacker=card)
        )
        assert not game.stack.is_empty()

    def test_unrelated_attack_event_does_not_push_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        card = TheDawningArchaic(owner=p1, controller=p1)
        other = _vanilla_creature("Other Attacker")
        set_board_state(game, 0, battlefield=[card, other])
        card.register_triggers(game)
        assert game.stack.is_empty()
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=other, attacker=other)
        )
        # The Dawning Archaic's trigger is keyed to itself, so nothing fires.
        assert game.stack.is_empty()


class TestTheDawningArchaicFreeCastFromGraveyard:
    """End-to-end coverage for the two previously-untestable requirements:

    1. "Whenever ~ attacks, you may cast target instant or sorcery card from
       your graveyard without paying its mana cost." — resolving the attack
       trigger (with the controller scripted to say "yes" and pick a target)
       moves the chosen spell from the graveyard to the stack with no mana
       paid.
    2. "If that spell would be put into your graveyard, exile it instead." —
       once that free-cast spell resolves, it ends up in exile, not the
       graveyard.

    The contract (see ``_cast_from_graveyard`` in card_impl):
      * ``controller.choose_yes_no`` is asked first (the "you may" clause).
      * ``controller.choose_card`` selects the graveyard instant/sorcery.
    Both are scripted through the DeterministicPlayer's ``script`` queue.
    """

    def _setup(self, scripts):
        """Build a game with The Dawning Archaic on the battlefield and a
        single instant in player 1's graveyard. *scripts* is the (s1, s2)
        DeterministicPlayer script tuple driving player 1's choices."""
        game = create_game(scripts=scripts)
        game.active_player_index = 0
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        bolt = _instant("Free Bolt")
        set_board_state(game, 0, battlefield=[card], graveyard=[bolt])
        card.register_triggers(game)
        return game, p1, card, bolt

    def _fire_and_resolve_trigger(self, game, card):
        """Fire the attack event, then resolve the single trigger StackObject
        it pushes (which runs the free-cast effect)."""
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=card, attacker=card)
        )
        assert not game.stack.is_empty(), "attack trigger should be on the stack"
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

    def test_free_cast_moves_spell_from_graveyard_to_stack(self) -> None:
        """Requirement 1: resolving the trigger with 'yes' + a chosen target
        casts the graveyard spell — it leaves the graveyard and goes to the
        stack."""
        # Script: choose_yes_no -> True, then choose_card -> the bolt.
        game, p1, card, bolt = self._setup(scripts=([True, None], []))
        # Patch the second scripted answer to the actual bolt object now that
        # it exists (script built before bolt instantiation).
        p1._script[1] = bolt

        self._fire_and_resolve_trigger(game, card)

        graveyard = game.get_graveyard(p1)
        assert not graveyard.contains(bolt), "spell should have left the graveyard"
        assert p1.zones[Zone.STACK].contains(bolt), (
            "free-cast spell should now be on the stack"
        )

    def test_free_cast_pays_no_mana(self) -> None:
        """Requirement 1: the spell is cast *without paying its mana cost* —
        the controller's mana pool is untouched by the free cast."""
        game, p1, card, bolt = self._setup(scripts=([True, None], []))
        p1._script[1] = bolt
        # Start with an empty mana pool; if any mana were spent the cast would
        # fail, and if any were produced the pool would be non-empty.
        p1.mana_pool.empty()
        assert p1.mana_pool.total() == 0

        self._fire_and_resolve_trigger(game, card)

        assert p1.mana_pool.total() == 0, "free cast must not pay or add mana"
        assert p1.zones[Zone.STACK].contains(bolt)

    def test_declining_the_may_leaves_spell_in_graveyard(self) -> None:
        """Requirement 1 ("you may"): scripting 'no' to the optional cast
        leaves the spell in the graveyard and nothing on the stack."""
        game, p1, card, bolt = self._setup(scripts=([False], []))

        self._fire_and_resolve_trigger(game, card)

        graveyard = game.get_graveyard(p1)
        assert graveyard.contains(bolt), "declined cast should keep spell in graveyard"
        assert game.stack.is_empty(), "declining should leave the stack empty"

    def test_resolved_free_cast_spell_is_exiled_not_in_graveyard(self) -> None:
        """Requirement 2: after the free-cast spell resolves, it is put into
        exile instead of the graveyard."""
        game, p1, card, bolt = self._setup(scripts=([True, None], []))
        p1._script[1] = bolt

        # Resolve the trigger -> bolt is now on the stack.
        self._fire_and_resolve_trigger(game, card)
        assert p1.zones[Zone.STACK].contains(bolt)

        # Resolve the spell itself.
        spell_obj = game.stack.pop()
        assert spell_obj.source is bolt
        spell_obj.on_resolve(game)

        exile = game.get_exile(p1)
        graveyard = game.get_graveyard(p1)
        assert exile.contains(bolt), "resolved free-cast spell should be exiled"
        assert not graveyard.contains(bolt), (
            "resolved free-cast spell must NOT be in the graveyard"
        )

    def test_no_op_when_graveyard_has_no_instant_or_sorcery(self) -> None:
        """Edge case: with no instant/sorcery in the graveyard the trigger
        does nothing — no choice is requested and nothing is cast."""
        # Script is empty: if the effect tried to ask choose_yes_no it would
        # raise ScriptExhaustedError, so an empty script proves no prompt.
        game = create_game(scripts=([], []))
        game.active_player_index = 0
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        bear = _vanilla_creature("Just A Bear")
        set_board_state(game, 0, battlefield=[card], graveyard=[bear])
        card.register_triggers(game)

        self._fire_and_resolve_trigger(game, card)

        # The creature in the graveyard is not a legal target; it stays put
        # and the stack is empty (no spell cast).
        assert game.get_graveyard(p1).contains(bear)
        assert game.stack.is_empty()
