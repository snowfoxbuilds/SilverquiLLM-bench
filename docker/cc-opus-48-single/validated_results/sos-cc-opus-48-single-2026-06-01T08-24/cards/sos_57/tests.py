"""Tests for SOS 57 — Mana Sculpt.

Mana Sculpt is a ``{1}{U}{U}`` Instant:

    "Counter target spell. If you control a Wizard, add an amount of {C} equal
    to the amount of mana spent to cast that spell at the beginning of your
    next main phase."

These tests define the TDD contract; ``card_impl.py`` is a stub, so they are
expected to fail until the card is implemented.

Coverage notes
--------------
* **Static data** — instant type, name, mana cost, blue color.
* **Targeting** — ``get_targets()`` advertises a single spell target that lives
  in the STACK zone; the filter accepts spells (instants/sorceries) and rejects
  non-spell objects.
* **Counter** — when Mana Sculpt resolves with a chosen target spell on the
  stack, that spell is countered: removed from the stack and placed into its
  owner's graveyard. No-target resolution is a no-op.

The delayed ``{C}`` clause ("If you control a Wizard … at the beginning of your
next main phase") depends on engine surface that does not exist (no
beginning-of-main-phase trigger event, and the engine does not record the
amount of mana spent to cast a given stack spell). Those sub-clauses are
recorded in ``untestable.json``. The Wizard *gate* is still exercised here at
the level the card can express it: countering itself must work identically
whether or not a Wizard is controlled, and the presence/absence of a Wizard
must not change the counter outcome.
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Phase, TargetRequirement, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _spell_on_stack(game: Any, player: Any, card: Any) -> StackObject:
    """Place *card* into *player*'s STACK zone and push a matching StackObject.

    Returns the pushed StackObject so tests can assert it leaves the stack.
    """
    card.owner = player
    card.controller = player
    player.zones[Zone.STACK].add(card)
    obj = StackObject(source=card, controller=player)
    game.stack.push(obj)
    return obj


def _vanilla_sorcery(name: str = "Lava Spike") -> Sorcery:
    c = Sorcery(name=name, mana_cost=ManaCost.parse("{R}"))
    return c


def _vanilla_instant(name: str = "Opt") -> Instant:
    c = Instant(name=name, mana_cost=ManaCost.parse("{U}"))
    return c


def _wizard(name: str = "Merfolk Wizard") -> Creature:
    c = Creature(name=name, base_power=1, base_toughness=1, subtypes={"Merfolk", "Wizard"})
    c.card_types = {CardType.CREATURE}
    return c


def _non_wizard(name: str = "Grizzly Bears") -> Creature:
    c = Creature(name=name, base_power=2, base_toughness=2, subtypes={"Bear"})
    c.card_types = {CardType.CREATURE}
    return c


def _costly_spell(name: str = "Big Spell", cost: str = "{3}{R}", mana_spent: int = 4) -> Sorcery:
    """A spell on the opponent's stack with a recorded ``mana_spent`` value.

    Real casting records ``card.mana_spent`` in ``engine.casting.cast_spell``;
    these tests stage the stack directly, so we set it explicitly to model the
    "amount of mana spent to cast that spell".
    """
    c = Sorcery(name=name, mana_cost=ManaCost.parse(cost))
    c.mana_spent = mana_spent
    return c


def _resolve_stack(game: Any) -> None:
    """Resolve every object currently on the stack (triggers included)."""
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)


def _advance_one_phase_resolving(game: Any) -> None:
    """Advance a single phase/step and resolve anything the transition queues.

    ``GameState.advance_phase`` fires ``BeginningOfMainPhaseTriggeredEvent`` and
    pushes the delayed Mana Sculpt trigger as a StackObject; resolving the stack
    afterward runs that trigger's effect (adding {C}).  Mana pools are emptied
    by ``advance_phase`` itself *before* the trigger resolves, so the {C} added
    by the resolving trigger survives into the new main phase.
    """
    game.advance_phase()
    _resolve_stack(game)


def _advance_to_next_main_phase(game: Any, player: Any, max_steps: int = 40) -> None:
    """Advance until *player* is the active player at a main phase, resolving
    queued triggers at every step.  Stops at the first such main phase."""
    for _ in range(max_steps):
        _advance_one_phase_resolving(game)
        if (
            game.active_player is player
            and game.phase in (Phase.PRECOMBAT_MAIN, Phase.POSTCOMBAT_MAIN)
        ):
            return
    raise AssertionError("did not reach the controller's main phase in time")


def _counter_with_wizard_gate(game: Any, *, wizard: bool) -> tuple[Any, Any, Any, Any]:
    """Stage caster (controlling a Wizard or not) countering a costly opp spell.

    Returns ``(caster, opponent, countered_spell, sculpt)``.  The caster is
    player 0, which is the active player by default so the delayed {C} lands on
    its own next main phase.
    """
    caster = game.players[0]
    opponent = game.players[1]
    blocker = _wizard() if wizard else _non_wizard()
    set_board_state(game, 0, battlefield=[blocker])

    target_spell = _costly_spell()
    _spell_on_stack(game, opponent, target_spell)

    sculpt = ManaSculpt(owner=caster, controller=caster)
    sculpt.chosen_targets = [target_spell]
    sculpt.on_resolve(game)
    return caster, opponent, target_spell, sculpt


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_card_type_includes_instant(self) -> None:
        assert CardType.INSTANT in ManaSculpt(owner=None).card_types

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_is_blue(self) -> None:
        """Cost has two blue pips and one generic."""
        from engine.types import ManaType

        cost = ManaSculpt(owner=None).mana_cost
        assert cost.pips.get(ManaType.BLUE, 0) == 2
        assert cost.generic == 1


# ---------------------------------------------------------------------------
# Targeting — "Counter target spell"
# ---------------------------------------------------------------------------


class TestManaSculptTargeting:
    """get_targets() advertises a single spell target in the STACK zone."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = ManaSculpt(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_stack(self) -> None:
        game = create_game()
        req = ManaSculpt(owner=None).get_targets(game)[0]
        assert req.zone == Zone.STACK

    def test_filter_accepts_sorcery_spell(self) -> None:
        game = create_game()
        req = ManaSculpt(owner=None).get_targets(game)[0]
        assert req.filter_fn(_vanilla_sorcery()) is True

    def test_filter_accepts_instant_spell(self) -> None:
        game = create_game()
        req = ManaSculpt(owner=None).get_targets(game)[0]
        assert req.filter_fn(_vanilla_instant()) is True

    def test_filter_rejects_non_spell(self) -> None:
        """A permanent / non-spell object is not a legal 'target spell'."""
        game = create_game()
        req = ManaSculpt(owner=None).get_targets(game)[0]

        class _NotASpell:
            card_types: set = set()

        assert req.filter_fn(_NotASpell()) is False


# ---------------------------------------------------------------------------
# Counter target spell
# ---------------------------------------------------------------------------


class TestManaSculptCounter:
    """On resolution, the targeted spell is countered (stack → graveyard)."""

    def test_countered_spell_leaves_the_stack(self) -> None:
        game = create_game()
        caster = game.players[0]
        opponent = game.players[1]
        target_spell = _vanilla_sorcery("Lava Spike")
        obj = _spell_on_stack(game, opponent, target_spell)

        sculpt = ManaSculpt(owner=caster, controller=caster)
        sculpt.chosen_targets = [target_spell]
        sculpt.on_resolve(game)

        # The countered spell's StackObject must no longer be on the stack.
        assert obj not in game.stack.objects()
        assert not opponent.zones[Zone.STACK].contains(target_spell)

    def test_countered_spell_goes_to_owner_graveyard(self) -> None:
        game = create_game()
        caster = game.players[0]
        opponent = game.players[1]
        target_spell = _vanilla_sorcery("Lava Spike")
        _spell_on_stack(game, opponent, target_spell)

        sculpt = ManaSculpt(owner=caster, controller=caster)
        sculpt.chosen_targets = [target_spell]
        sculpt.on_resolve(game)

        # A countered spell goes to its owner's graveyard.
        assert game.get_graveyard(opponent).contains(target_spell)

    def test_countered_spell_does_not_resolve_its_effect(self) -> None:
        """The countered spell's on_resolve must not run."""
        game = create_game()
        caster = game.players[0]
        opponent = game.players[1]

        resolved = {"ran": False}

        class _Marker(Sorcery):
            def on_resolve(self, g: Any) -> None:
                resolved["ran"] = True

        target_spell = _Marker(name="Marker", mana_cost=ManaCost.parse("{R}"))
        _spell_on_stack(game, opponent, target_spell)

        sculpt = ManaSculpt(owner=caster, controller=caster)
        sculpt.chosen_targets = [target_spell]
        sculpt.on_resolve(game)

        assert resolved["ran"] is False

    def test_no_target_is_a_noop(self) -> None:
        """With no chosen target, resolution must not raise and must not
        remove anything from the stack."""
        game = create_game()
        caster = game.players[0]
        opponent = game.players[1]
        target_spell = _vanilla_sorcery("Lava Spike")
        _spell_on_stack(game, opponent, target_spell)

        sculpt = ManaSculpt(owner=caster, controller=caster)
        # chosen_targets left unset.
        sculpt.on_resolve(game)

        # Untouched: the spell stays on the stack.
        assert opponent.zones[Zone.STACK].contains(target_spell)
        assert not game.get_graveyard(opponent).contains(target_spell)

    def test_none_target_is_a_noop(self) -> None:
        """An explicit ``[None]`` target list (no legal target chosen) is a
        no-op rather than a crash."""
        game = create_game()
        caster = game.players[0]
        opponent = game.players[1]
        target_spell = _vanilla_sorcery("Lava Spike")
        _spell_on_stack(game, opponent, target_spell)

        sculpt = ManaSculpt(owner=caster, controller=caster)
        sculpt.chosen_targets = [None]
        sculpt.on_resolve(game)

        assert opponent.zones[Zone.STACK].contains(target_spell)


# ---------------------------------------------------------------------------
# Wizard gate — counter behavior is independent of the bonus clause
# ---------------------------------------------------------------------------


class TestManaSculptWizardGateDoesNotAffectCounter:
    """The 'If you control a Wizard' clause governs only the bonus {C}; the
    counter itself happens regardless of whether a Wizard is controlled."""

    def test_counters_even_without_a_wizard(self) -> None:
        game = create_game()
        caster = game.players[0]
        opponent = game.players[1]
        # Caster controls a non-Wizard creature only.
        set_board_state(game, 0, battlefield=[_non_wizard()])
        target_spell = _vanilla_sorcery("Lava Spike")
        _spell_on_stack(game, opponent, target_spell)

        sculpt = ManaSculpt(owner=caster, controller=caster)
        sculpt.chosen_targets = [target_spell]
        sculpt.on_resolve(game)

        assert game.get_graveyard(opponent).contains(target_spell)

    def test_counters_when_controlling_a_wizard(self) -> None:
        game = create_game()
        caster = game.players[0]
        opponent = game.players[1]
        set_board_state(game, 0, battlefield=[_wizard()])
        target_spell = _vanilla_sorcery("Lava Spike")
        _spell_on_stack(game, opponent, target_spell)

        sculpt = ManaSculpt(owner=caster, controller=caster)
        sculpt.chosen_targets = [target_spell]
        sculpt.on_resolve(game)

        assert game.get_graveyard(opponent).contains(target_spell)


# ---------------------------------------------------------------------------
# Wizard {C} bonus — "add an amount of {C} equal to the amount of mana spent
# to cast that spell at the beginning of your next main phase"
# ---------------------------------------------------------------------------


class TestManaSculptWizardManaBonus:
    """The delayed {C} bonus is gated on controlling a Wizard, equals the
    countered spell's mana spent, and is delivered at the controller's next
    main phase (not before).

    These exercise the additive engine support: the
    ``BeginningOfMainPhaseTriggeredEvent`` fired from ``advance_phase`` and the
    ``card.mana_spent`` value recorded during casting.
    """

    def test_wizard_grants_colorless_at_next_main_phase(self) -> None:
        """With a Wizard, the controller's pool gains {C} once its next main
        phase begins."""
        game = create_game()
        caster, _opp, spell, _sculpt = _counter_with_wizard_gate(game, wizard=True)

        # Nothing in the pool yet — the bonus is delayed.
        assert caster.mana_pool.get(ManaType.COLORLESS) == 0

        _advance_to_next_main_phase(game, caster)

        assert caster.mana_pool.get(ManaType.COLORLESS) == spell.mana_spent

    def test_bonus_amount_equals_mana_spent_on_countered_spell(self) -> None:
        """The {C} added equals the mana spent to cast the countered spell,
        whatever that value is."""
        game = create_game()
        caster = game.players[0]
        opponent = game.players[1]
        set_board_state(game, 0, battlefield=[_wizard()])

        # A different, larger mana-spent value than the default helper.
        spell = _costly_spell(name="Huge Spell", cost="{6}{U}{U}", mana_spent=8)
        _spell_on_stack(game, opponent, spell)

        sculpt = ManaSculpt(owner=caster, controller=caster)
        sculpt.chosen_targets = [spell]
        sculpt.on_resolve(game)

        _advance_to_next_main_phase(game, caster)

        assert caster.mana_pool.get(ManaType.COLORLESS) == 8

    def test_no_wizard_grants_no_colorless(self) -> None:
        """Without a Wizard, no {C} is ever added — the bonus clause does not
        apply."""
        game = create_game()
        caster, _opp, _spell, sculpt = _counter_with_wizard_gate(game, wizard=False)

        # No delayed trigger should have been registered at all.
        assert len(game.trigger_manager.get_triggers_for_source(sculpt)) == 0

        _advance_to_next_main_phase(game, caster)

        assert caster.mana_pool.get(ManaType.COLORLESS) == 0

    def test_bonus_not_delivered_before_main_phase(self) -> None:
        """The {C} arrives at the beginning of the next main phase, not during
        the upkeep/draw steps that precede it."""
        game = create_game()
        caster, _opp, spell, _sculpt = _counter_with_wizard_gate(game, wizard=True)

        # Walk forward one phase/step at a time.  Every step BEFORE the main
        # phase must leave the pool empty; the main phase itself delivers the
        # {C} (and then we stop, since the next transition would empty it).
        for _ in range(40):
            _advance_one_phase_resolving(game)
            if (
                game.active_player is caster
                and game.phase in (Phase.PRECOMBAT_MAIN, Phase.POSTCOMBAT_MAIN)
            ):
                # Delivered exactly at the beginning of the main phase.
                assert caster.mana_pool.get(ManaType.COLORLESS) == spell.mana_spent
                break
            # Not yet a main phase for the controller — no {C} yet.
            assert caster.mana_pool.get(ManaType.COLORLESS) == 0
        else:
            raise AssertionError("never reached the controller's main phase")

    def test_bonus_is_independent_of_the_counter(self) -> None:
        """The counter half still happens regardless of the bonus: the spell is
        countered immediately, and the {C} arrives later."""
        game = create_game()
        caster, opponent, spell, _sculpt = _counter_with_wizard_gate(game, wizard=True)

        # Counter resolved immediately.
        assert game.get_graveyard(opponent).contains(spell)
        # Bonus is still pending (delayed), not yet in the pool.
        assert caster.mana_pool.get(ManaType.COLORLESS) == 0

        _advance_to_next_main_phase(game, caster)

        # Counter remains done and the {C} has now been delivered.
        assert game.get_graveyard(opponent).contains(spell)
        assert caster.mana_pool.get(ManaType.COLORLESS) == spell.mana_spent

    def test_zero_mana_spent_grants_no_colorless(self) -> None:
        """A countered spell that recorded zero mana spent yields no {C} even
        with a Wizard (nothing to add)."""
        game = create_game()
        caster = game.players[0]
        opponent = game.players[1]
        set_board_state(game, 0, battlefield=[_wizard()])

        spell = _costly_spell(name="Free Spell", cost="{0}", mana_spent=0)
        _spell_on_stack(game, opponent, spell)

        sculpt = ManaSculpt(owner=caster, controller=caster)
        sculpt.chosen_targets = [spell]
        sculpt.on_resolve(game)

        _advance_to_next_main_phase(game, caster)

        assert caster.mana_pool.get(ManaType.COLORLESS) == 0
