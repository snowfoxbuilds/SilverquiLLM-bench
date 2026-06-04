"""Tests for SOS 57 — Mana Sculpt.

Mana Sculpt — {1}{U}{U} — Instant:

    "Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase."

The card has three distinct behavioural clauses:

1. **Counter target spell** — any spell on the stack is a legal target
   (creature spells *and* noncreature spells, unlike "counter target
   noncreature spell"). On resolution the targeted spell is removed from
   the stack and put into its owner's graveyard; it never resolves.
2. **Wizard gate** — the deferred mana benefit only happens *if its
   controller controls a Wizard* (a creature with the ``Wizard`` subtype).
3. **Deferred {C}** — at the beginning of the controller's next main phase,
   they add an amount of {C} equal to the amount of mana spent to cast the
   countered spell.

These tests follow the FDN reference-test style: static-property checks plus
behavioural checks that set up explicit board / stack states and drive the
card's public hooks (``get_targets`` / ``can_cast`` / ``on_resolve``).
"""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell as engine_cast_spell
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wizard(power: int = 1, toughness: int = 1) -> Creature:
    """A creature with the Wizard subtype."""
    return Creature(
        name="Test Wizard",
        base_power=power,
        base_toughness=toughness,
        subtypes={"Wizard"},
    )


def _non_wizard(power: int = 2, toughness: int = 2) -> Creature:
    """A creature with no relevant subtype."""
    return Creature(
        name="Grizzly Bears",
        base_power=power,
        base_toughness=toughness,
        subtypes={"Bear"},
    )


def _put_spell_on_stack(game, caster, card, mana=None):
    """Cast *card* from *caster*'s hand through the real engine pipeline so it
    sits on the stack (un-resolved). Returns the StackObject for that spell.

    Sets up sorcery-speed timing for the caster and grants the supplied mana.
    """
    if mana is None:
        mana = {ManaType.COLORLESS: 10}
    caster_index = game.players.index(caster)
    set_board_state(game, caster_index, hand=[card], mana=mana)
    game.active_player_index = caster_index
    game.priority_player_index = caster_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    engine_cast_spell(game, caster, card)
    return game.stack.peek()


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_is_instant(self) -> None:
        card = ManaSculpt(owner=None)
        assert isinstance(card, Instant)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_is_not_a_permanent_type(self) -> None:
        """An instant is not a creature/permanent."""
        card = ManaSculpt(owner=None)
        assert CardType.CREATURE not in card.card_types
        assert CardType.LAND not in card.card_types


# ---------------------------------------------------------------------------
# Targeting: "Counter target spell"
# ---------------------------------------------------------------------------

class TestManaSculptTargeting:
    """get_targets / can_cast should accept any spell on the stack."""

    def test_get_targets_returns_one_requirement(self) -> None:
        """The spell targets exactly one thing (target spell)."""
        game = create_game()
        p1 = game.players[0]
        # Put an instant on the stack to provide a legal target.
        p2 = game.players[1]
        _put_spell_on_stack(
            game, p2, Instant(name="Doomed Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1})),
            mana={ManaType.RED: 1},
        )
        sculpt = ManaSculpt(owner=p1, controller=p1)
        reqs = sculpt.get_targets(game)
        assert len(reqs) == 1

    def test_target_requirement_zone_is_stack(self) -> None:
        """The legal targets live on the stack, not the battlefield."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _put_spell_on_stack(
            game, p2, Instant(name="Doomed Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1})),
            mana={ManaType.RED: 1},
        )
        sculpt = ManaSculpt(owner=p1, controller=p1)
        req = sculpt.get_targets(game)[0]
        assert getattr(req, "zone", None) == Zone.STACK

    def test_target_filter_accepts_creature_spell(self) -> None:
        """Unlike 'counter target noncreature spell', a creature spell is legal."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bear_obj = _put_spell_on_stack(
            game, p2,
            Creature(
                name="Big Bear",
                mana_cost=ManaCost(generic=1, pips={ManaType.GREEN: 1}),
                base_power=3, base_toughness=3,
            ),
            mana={ManaType.GREEN: 2},
        )
        sculpt = ManaSculpt(owner=p1, controller=p1)
        req = sculpt.get_targets(game)[0]
        assert req.filter_fn(bear_obj) is True

    def test_target_filter_accepts_noncreature_spell(self) -> None:
        """A noncreature spell (instant) is also a legal target."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bolt_obj = _put_spell_on_stack(
            game, p2, Instant(name="Doomed Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1})),
            mana={ManaType.RED: 1},
        )
        sculpt = ManaSculpt(owner=p1, controller=p1)
        req = sculpt.get_targets(game)[0]
        assert req.filter_fn(bolt_obj) is True

    def test_target_filter_rejects_self(self) -> None:
        """Mana Sculpt cannot target itself on the stack."""
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt(owner=p1, controller=p1)
        # Provide another spell so get_targets does not early-return empty.
        p2 = game.players[1]
        _put_spell_on_stack(
            game, p2, Instant(name="Doomed Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1})),
            mana={ManaType.RED: 1},
        )
        req = sculpt.get_targets(game)[0]
        # A spell can never counter itself. The targeting layer works over the
        # STACK zone, so the filter must reject a StackObject whose source is
        # this very Mana Sculpt. (Accept either representation the filter may
        # be handed: the raw card or the wrapping StackObject.)
        from engine.stack import StackObject
        own_obj = StackObject(source=sculpt, controller=p1)
        assert req.filter_fn(own_obj) is False
        assert req.filter_fn(sculpt) is False

    def test_cannot_cast_with_empty_stack(self) -> None:
        """With no spell on the stack there is no legal target → can_cast False."""
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt(owner=p1, controller=p1)
        assert sculpt.can_cast(game) is False

    def test_can_cast_with_spell_on_stack(self) -> None:
        """A spell on the stack provides a legal target → can_cast True."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _put_spell_on_stack(
            game, p2, Instant(name="Doomed Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1})),
            mana={ManaType.RED: 1},
        )
        sculpt = ManaSculpt(owner=p1, controller=p1)
        assert sculpt.can_cast(game) is True


# ---------------------------------------------------------------------------
# Counter behaviour: "Counter target spell"
# ---------------------------------------------------------------------------

class TestManaSculptCounter:
    """On resolution the targeted spell is countered (removed from stack →
    graveyard) and never resolves."""

    def test_counters_instant_to_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bolt = Instant(name="Doomed Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        bolt_obj = _put_spell_on_stack(game, p2, bolt, mana={ManaType.RED: 1})

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [bolt_obj]
        sculpt.on_resolve(game)

        # The targeted instant is now in its owner's graveyard, not on the stack.
        assert game.get_graveyard(p2).contains(bolt)
        assert not game.players[1].zones[Zone.STACK].contains(bolt)

    def test_countered_spell_removed_from_stack(self) -> None:
        """The countered spell's StackObject is gone from the stack."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bolt = Instant(name="Doomed Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        bolt_obj = _put_spell_on_stack(game, p2, bolt, mana={ManaType.RED: 1})

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [bolt_obj]
        sculpt.on_resolve(game)

        assert bolt_obj not in game.stack.objects()

    def test_countered_creature_does_not_enter_battlefield(self) -> None:
        """A countered creature spell never reaches the battlefield."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bear = Creature(
            name="Doomed Bear",
            mana_cost=ManaCost(generic=1, pips={ManaType.GREEN: 1}),
            base_power=2, base_toughness=2,
        )
        bear_obj = _put_spell_on_stack(game, p2, bear, mana={ManaType.GREEN: 2})

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [bear_obj]
        sculpt.on_resolve(game)

        assert not game.get_battlefield(p2).contains(bear)
        assert game.get_graveyard(p2).contains(bear)

    def test_counters_sorcery(self) -> None:
        """A sorcery on the stack is also countered to its owner's graveyard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        sorc = Sorcery(name="Doomed Divination",
                       mana_cost=ManaCost(generic=2, pips={ManaType.BLUE: 1}))
        sorc_obj = _put_spell_on_stack(game, p2, sorc, mana={ManaType.BLUE: 3})

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [sorc_obj]
        sculpt.on_resolve(game)

        assert game.get_graveyard(p2).contains(sorc)

    def test_no_target_is_noop(self) -> None:
        """With no chosen target the resolve does nothing and does not raise."""
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt(owner=p1, controller=p1)
        # No chosen_targets attribute set at all.
        sculpt.on_resolve(game)  # must not raise


# ---------------------------------------------------------------------------
# Wizard gate + deferred {C} mana
# ---------------------------------------------------------------------------

class TestManaSculptWizardManaGate:
    """The {C} reimbursement only triggers when its controller controls a
    Wizard; the amount equals the mana spent on the countered spell.

    The engine has no native 'beginning of your next main phase' delayed
    trigger, so these tests verify the *gating decision* made at resolution
    time (whether the deferred benefit is set up at all) and — where the
    implementation exposes it — the recorded amount of {C}. We avoid
    asserting on a specific private delivery mechanism by checking the
    controller's {C} pool after the implementation's own delayed-effect
    delivery hook is invoked, when such a hook exists.
    """

    def test_no_wizard_no_mana_added_immediately(self) -> None:
        """Without a Wizard, resolving Mana Sculpt must not immediately add
        {C} to the controller's mana pool (the benefit is gated off)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        set_board_state(game, 0, battlefield=[_non_wizard()],
                        mana={ManaType.COLORLESS: 0})
        bolt = Instant(name="Doomed Bolt",
                       mana_cost=ManaCost(generic=1, pips={ManaType.RED: 1}))
        bolt_obj = _put_spell_on_stack(game, p2, bolt, mana={ManaType.RED: 3})

        before = p1.mana_pool.get(ManaType.COLORLESS)
        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [bolt_obj]
        sculpt.on_resolve(game)

        # The spell is still countered ...
        assert game.get_graveyard(p2).contains(bolt)
        # ... but no {C} reimbursement is set up without a Wizard.
        assert p1.mana_pool.get(ManaType.COLORLESS) == before

    def test_counter_happens_even_without_wizard(self) -> None:
        """The counter is unconditional — only the {C} benefit is gated."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        set_board_state(game, 0, battlefield=[_non_wizard()])
        bolt = Instant(name="Doomed Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        bolt_obj = _put_spell_on_stack(game, p2, bolt, mana={ManaType.RED: 1})

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [bolt_obj]
        sculpt.on_resolve(game)

        assert game.get_graveyard(p2).contains(bolt)

    def test_wizard_sets_up_deferred_mana(self) -> None:
        """With a Wizard in play the spell records a pending {C} reimbursement
        whose amount equals the mana spent to cast the countered spell.

        The bolt below costs {1}{R} (2 mana). Paying it from a pool of 3 red
        deducts exactly 2 mana, so the amount of mana spent — and therefore the
        deferred {C} — must be 2. We read the recorded pending amount via a
        plausible attribute on the resolving spell or its controller. If none
        is present this test fails (red phase).
        """
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        set_board_state(game, 0, battlefield=[_wizard()])
        bolt = Instant(name="Doomed Bolt",
                       mana_cost=ManaCost(generic=1, pips={ManaType.RED: 1}))
        bolt_obj = _put_spell_on_stack(game, p2, bolt, mana={ManaType.RED: 3})

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [bolt_obj]
        sculpt.on_resolve(game)

        pending = _read_pending_colorless(sculpt, p1)
        assert pending == 2

    def test_deferred_amount_tracks_larger_spend(self) -> None:
        """The reimbursement scales with the mana actually spent (5 here)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        set_board_state(game, 0, battlefield=[_wizard()])
        big = Creature(
            name="Doomed Behemoth",
            mana_cost=ManaCost(generic=3, pips={ManaType.GREEN: 2}),
            base_power=5, base_toughness=5,
        )
        big_obj = _put_spell_on_stack(game, p2, big, mana={ManaType.GREEN: 5})

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [big_obj]
        sculpt.on_resolve(game)

        pending = _read_pending_colorless(sculpt, p1)
        assert pending == 5

    def test_mana_not_added_immediately_even_with_wizard(self) -> None:
        """The {C} is added 'at the beginning of your next main phase', so it
        must NOT be in the pool the instant Mana Sculpt resolves."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        set_board_state(game, 0, battlefield=[_wizard()],
                        mana={ManaType.COLORLESS: 0})
        bolt = Instant(name="Doomed Bolt",
                       mana_cost=ManaCost(generic=1, pips={ManaType.RED: 1}))
        bolt_obj = _put_spell_on_stack(game, p2, bolt, mana={ManaType.RED: 3})

        before = p1.mana_pool.get(ManaType.COLORLESS)
        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [bolt_obj]
        sculpt.on_resolve(game)

        # Deferred — pool unchanged at resolution time.
        assert p1.mana_pool.get(ManaType.COLORLESS) == before


# ---------------------------------------------------------------------------
# Deterministic delivery of the deferred {C}
# ---------------------------------------------------------------------------

class TestManaSculptDeferredDelivery:
    """End-to-end delivery of the deferred {C} reimbursement.

    The engine now exposes a stable surface for "at the beginning of your next
    main phase": resolving Mana Sculpt with a Wizard in play schedules a
    one-shot deferred effect, and firing
    :class:`BeginningOfMainPhaseTriggeredEvent` for the controller (precombat)
    runs that effect synchronously — adding the recorded amount of {C} to the
    controller's mana pool exactly once.

    The amount equals the mana spent to cast the countered spell, which the
    casting pipeline records on ``card.mana_spent`` (the converted cost actually
    paid). A ``{1}{R}`` bolt therefore reimburses 2 {C}.
    """

    @staticmethod
    def _fire_next_main_phase(game, controller) -> None:
        """Fire the precombat BeginningOfMainPhase event for *controller*.

        This drives the scheduled deferred effect synchronously without
        advancing the stack — the same way the engine delivers it on the
        controller's next main phase.
        """
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(
                player=controller, controller=controller, precombat=True
            ),
        )

    def test_deferred_colorless_not_in_pool_at_resolution(self) -> None:
        """With a Wizard, the {C} is deferred — the pool is still empty the
        instant Mana Sculpt resolves (delivery happens later)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        set_board_state(game, 0, battlefield=[_wizard()],
                        mana={ManaType.COLORLESS: 0})
        # {1}{R} bolt → mana_spent == 2.
        bolt = Instant(name="Doomed Bolt",
                       mana_cost=ManaCost(generic=1, pips={ManaType.RED: 1}))
        bolt_obj = _put_spell_on_stack(game, p2, bolt, mana={ManaType.RED: 3})
        assert getattr(bolt, "mana_spent", 0) == 2

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [bolt_obj]
        sculpt.on_resolve(game)

        # Spell countered, but no {C} yet — it is deferred to the next main phase.
        assert game.get_graveyard(p2).contains(bolt)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_deferred_colorless_added_at_next_main_phase(self) -> None:
        """Firing the controller's precombat BeginningOfMainPhase event adds
        exactly the countered spell's mana_spent worth of {C}."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        set_board_state(game, 0, battlefield=[_wizard()],
                        mana={ManaType.COLORLESS: 0})
        bolt = Instant(name="Doomed Bolt",
                       mana_cost=ManaCost(generic=1, pips={ManaType.RED: 1}))
        bolt_obj = _put_spell_on_stack(game, p2, bolt, mana={ManaType.RED: 3})
        spent = getattr(bolt, "mana_spent", 0)
        assert spent == 2

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [bolt_obj]
        sculpt.on_resolve(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

        self._fire_next_main_phase(game, p1)

        # The deferred {C} is now in the controller's pool, equal to mana spent.
        assert p1.mana_pool.get(ManaType.COLORLESS) == spent

    def test_deferred_delivery_scales_with_larger_spend(self) -> None:
        """A pricier countered spell (5 mana) delivers 5 {C} at the next main
        phase — the amount tracks the mana actually spent."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        set_board_state(game, 0, battlefield=[_wizard()],
                        mana={ManaType.COLORLESS: 0})
        big = Creature(
            name="Doomed Behemoth",
            mana_cost=ManaCost(generic=3, pips={ManaType.GREEN: 2}),
            base_power=5, base_toughness=5,
        )
        big_obj = _put_spell_on_stack(game, p2, big, mana={ManaType.GREEN: 5})
        spent = getattr(big, "mana_spent", 0)
        assert spent == 5

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [big_obj]
        sculpt.on_resolve(game)

        self._fire_next_main_phase(game, p1)

        assert p1.mana_pool.get(ManaType.COLORLESS) == spent

    def test_deferred_delivery_is_one_shot(self) -> None:
        """Firing the BeginningOfMainPhase event a SECOND time must not add
        any more {C} — the reimbursement is one-shot."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        set_board_state(game, 0, battlefield=[_wizard()],
                        mana={ManaType.COLORLESS: 0})
        bolt = Instant(name="Doomed Bolt",
                       mana_cost=ManaCost(generic=1, pips={ManaType.RED: 1}))
        bolt_obj = _put_spell_on_stack(game, p2, bolt, mana={ManaType.RED: 3})
        spent = getattr(bolt, "mana_spent", 0)
        assert spent == 2

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [bolt_obj]
        sculpt.on_resolve(game)

        self._fire_next_main_phase(game, p1)
        after_first = p1.mana_pool.get(ManaType.COLORLESS)
        assert after_first == spent

        # Fire again — the deferred effect has already been consumed.
        self._fire_next_main_phase(game, p1)
        assert p1.mana_pool.get(ManaType.COLORLESS) == after_first

    def test_no_wizard_nothing_delivered_at_next_main_phase(self) -> None:
        """Without a Wizard nothing is scheduled, so firing the next main-phase
        event adds no {C} at all."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        set_board_state(game, 0, battlefield=[_non_wizard()],
                        mana={ManaType.COLORLESS: 0})
        bolt = Instant(name="Doomed Bolt",
                       mana_cost=ManaCost(generic=1, pips={ManaType.RED: 1}))
        bolt_obj = _put_spell_on_stack(game, p2, bolt, mana={ManaType.RED: 3})

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [bolt_obj]
        sculpt.on_resolve(game)

        self._fire_next_main_phase(game, p1)

        # Spell still countered, but no Wizard → no deferred {C} ever delivered.
        assert game.get_graveyard(p2).contains(bolt)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0


# ---------------------------------------------------------------------------
# Shared accessor for the deferred-{C} amount
# ---------------------------------------------------------------------------

def _read_pending_colorless(sculpt, controller):
    """Read the pending deferred-{C} amount the implementation recorded.

    The card may stash this on the spell instance or on its controller; we
    accept a small set of plausible attribute names so the test asserts on
    *behaviour* (amount recorded) rather than a single private field name.
    """
    for obj in (sculpt, controller):
        for attr in (
            "pending_colorless",
            "deferred_colorless",
            "pending_mana",
            "deferred_mana",
            "mana_to_add",
        ):
            val = getattr(obj, attr, None)
            if isinstance(val, bool):
                continue
            if isinstance(val, int):
                return val
    return None
