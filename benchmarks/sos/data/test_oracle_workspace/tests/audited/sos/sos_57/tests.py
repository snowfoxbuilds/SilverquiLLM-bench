"""Audited tests for Mana Sculpt (sos_57) — FLAGSHIP.

Oracle: {1}{U}{U} Instant.
  Counter target spell. If you control a Wizard, add an amount of {C}
  equal to the amount of mana spent to cast that spell at the beginning
  of your next main phase.

Simulation-only shape (AUDITED-TEST-API.md): the target spell reaches the
stack through a scripted opponent cast, Mana Sculpt is cast as a response
directive, and everything resolves inside ``priority_loop``.  The {C} refund
is measured purely through observable mana-pool state: the opponent's spell
cost is pinned by the test, and the pool is asserted before and after the
refund's main-phase trigger fires (no ``assert_mana_spent`` — the canonical
engine has no ``mana_spent`` accessor).

Tests:
  1. test_card_identity
  2. test_counters_target_spell
  3. test_insufficient_mana_cast_rejected
  4. test_refund_with_wizard_at_next_main_phase
  5. test_refund_amount_tracks_opponents_spell_cost
  6. test_no_refund_without_wizard
  7. test_no_refund_when_countered_spell_was_cast_for_free
  8. test_non_wizard_creature_does_not_enable_refund
  9. test_fizzle_when_target_already_countered
"""

from __future__ import annotations

from card_impl import ManaSculpt

from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import (
    CastSpell,
    CastSpellFree,
    DeterministicPlayer,
    advance_to_phase,
    assert_in_zone,
    assert_life_total,
    assert_mana_pool,
    assert_on_stack,
    assert_stack_empty,
    assert_zone_count,
    create_game,
    no_op,
    perform_action,
    perform_illegal_action,
    priority_loop,
    set_board_state,
    set_player,
)


# ---------------------------------------------------------------------------
# Fixture cards
# ---------------------------------------------------------------------------


def _make_wizard(name: str = "Sage of Fables") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2, subtypes={"Wizard"})


def _make_enemy_spell(cost: ManaCost | None = None) -> Instant:
    """A simple opponent spell with no targets, so casting doesn't ask for one."""
    if cost is None:
        cost = ManaCost(generic=2, pips={ManaType.RED: 1})  # CMC 3
    return Instant(name="Enemy Spell", mana_cost=cost)


def _mana_for(cost: ManaCost) -> dict[ManaType, int]:
    """Exactly enough mana to pay *cost* (mana-minimality)."""
    mana: dict[ManaType, int] = {}
    if cost.generic:
        mana[ManaType.COLORLESS] = cost.generic
    for mana_type, amount in cost.pips.items():
        mana[mana_type] = mana.get(mana_type, 0) + amount
    return mana


_SCULPT_MANA = {ManaType.COLORLESS: 1, ManaType.BLUE: 2}


def _counter_enemy_spell(game, enemy_cost: ManaCost) -> None:
    """Opponent casts Enemy Spell; player 0 counters it with Mana Sculpt."""
    enemy = _make_enemy_spell(cost=enemy_cost)
    set_board_state(game, 0, hand=[ManaSculpt()], mana=_SCULPT_MANA)
    set_board_state(game, 1, hand=[enemy], mana=_mana_for(enemy_cost))

    set_player(game, 0, DeterministicPlayer("P0", script=[
        no_op(),
        perform_action(CastSpell("Mana Sculpt", targets=["Enemy Spell"])),
        no_op(),
    ]))
    set_player(game, 1, DeterministicPlayer("P1", script=[
        perform_action(CastSpell("Enemy Spell")),
        no_op(),
    ]))

    priority_loop(game)

    # The countered spell left the stack into its owner's graveyard;
    # Mana Sculpt resolved.
    assert_on_stack(game, "Enemy Spell", count=0)
    assert_in_zone(game, 1, Zone.GRAVEYARD, "Enemy Spell")
    assert_in_zone(game, 0, Zone.GRAVEYARD, "Mana Sculpt")
    assert_stack_empty(game)


# ---------------------------------------------------------------------------
# 1. Identity
# ---------------------------------------------------------------------------


class TestIdentity:
    def test_card_identity(self) -> None:
        card = ManaSculpt()
        assert card.name == "Mana Sculpt"
        assert card.mana_cost.generic == 1
        assert card.mana_cost.pips.get(ManaType.BLUE) == 2
        assert card.mana_cost.cmc == 3
        assert CardType.INSTANT in card.card_types
        assert isinstance(card, Instant)


# ---------------------------------------------------------------------------
# 2–3. Counter behaviour
# ---------------------------------------------------------------------------


class TestCounter:
    def test_counters_target_spell(self) -> None:
        """The opponent's spell is countered: it never resolves and lands in
        its owner's graveyard; the stack ends empty."""
        game = create_game()
        _counter_enemy_spell(game, ManaCost(generic=2, pips={ManaType.RED: 1}))
        # Mana-minimality: both pools were fully spent on the casts.
        assert_mana_pool(game, 0, {})
        assert_mana_pool(game, 1, {})
        assert_life_total(game, 0, 20)
        assert_life_total(game, 1, 20)

    def test_insufficient_mana_cast_rejected(self) -> None:
        """{1}{U}{U} cannot be paid from {U}{U} — the cast is illegal."""
        game = create_game()
        enemy = _make_enemy_spell()
        set_board_state(game, 0, hand=[ManaSculpt()], mana={ManaType.BLUE: 2})
        set_board_state(game, 1, hand=[enemy], mana=_mana_for(enemy.mana_cost))

        set_player(game, 0, DeterministicPlayer("P0", script=[
            no_op(),
            perform_illegal_action(CastSpell("Mana Sculpt", targets=["Enemy Spell"])),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[
            perform_action(CastSpell("Enemy Spell")),
            no_op(),
        ]))

        priority_loop(game)

        # Mana Sculpt stayed in hand; the enemy spell resolved normally.
        assert_in_zone(game, 0, Zone.HAND, "Mana Sculpt")
        assert_in_zone(game, 1, Zone.GRAVEYARD, "Enemy Spell")


# ---------------------------------------------------------------------------
# 4–7. Wizard-conditional delayed refund (pool-delta pattern)
# ---------------------------------------------------------------------------


class TestRefund:
    def test_refund_with_wizard_at_next_main_phase(self) -> None:
        """With a Wizard, {C} equal to the countered spell's cost arrives at
        the beginning of the controller's next main phase — not earlier."""
        game = create_game()
        set_board_state(game, 0, battlefield=[_make_wizard()])
        _counter_enemy_spell(game, ManaCost(generic=2, pips={ManaType.RED: 1}))

        # Delayed trigger: nothing has arrived yet.
        assert_mana_pool(game, 0, {})

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert_mana_pool(game, 0, {ManaType.COLORLESS: 3})

    def test_refund_amount_tracks_opponents_spell_cost(self) -> None:
        """Refund equals the mana spent on the countered spell (CMC 5 here)."""
        game = create_game()
        set_board_state(game, 0, battlefield=[_make_wizard()])
        _counter_enemy_spell(game, ManaCost(generic=3, pips={ManaType.RED: 2}))

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert_mana_pool(game, 0, {ManaType.COLORLESS: 5})

    def test_no_refund_without_wizard(self) -> None:
        game = create_game()
        _counter_enemy_spell(game, ManaCost(generic=2, pips={ManaType.RED: 1}))

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert_mana_pool(game, 0, {})

    def test_no_refund_when_countered_spell_was_cast_for_free(self) -> None:
        """The refund tracks the mana *spent* on the countered spell — a
        spell cast without paying its cost (CastSpellFree) refunds nothing,
        Wizard or not."""
        game = create_game()
        set_board_state(game, 0, battlefield=[_make_wizard()])
        enemy = _make_enemy_spell()
        set_board_state(game, 0, hand=[ManaSculpt()], mana=_SCULPT_MANA)
        set_board_state(game, 1, hand=[enemy])

        set_player(game, 0, DeterministicPlayer("P0", script=[
            no_op(),
            perform_action(CastSpell("Mana Sculpt", targets=["Enemy Spell"])),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[
            perform_action(CastSpellFree("Enemy Spell")),
            no_op(),
        ]))

        priority_loop(game)
        assert_in_zone(game, 1, Zone.GRAVEYARD, "Enemy Spell")

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert_mana_pool(game, 0, {})

    def test_non_wizard_creature_does_not_enable_refund(self) -> None:
        """The condition is 'you control a Wizard' — a Beast does not count."""
        game = create_game()
        bear = Creature(
            name="Bear", base_power=2, base_toughness=2, subtypes={"Beast"},
        )
        set_board_state(game, 0, battlefield=[bear])
        _counter_enemy_spell(game, ManaCost(generic=2, pips={ManaType.RED: 1}))

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert_mana_pool(game, 0, {})


# ---------------------------------------------------------------------------
# 8. Fizzle — target already removed from the stack
# ---------------------------------------------------------------------------


class TestFizzle:
    def test_fizzle_when_target_already_countered(self) -> None:
        """Two Mana Sculpts aimed at the same spell: the second to be cast
        resolves first and counters it; the first then fizzles — no second
        refund, and the countered spell is in the graveyard exactly once."""
        game = create_game()
        enemy_cost = ManaCost(generic=2, pips={ManaType.RED: 1})
        enemy = _make_enemy_spell(cost=enemy_cost)
        set_board_state(game, 0, battlefield=[_make_wizard()])
        set_board_state(
            game, 0,
            hand=[ManaSculpt(), ManaSculpt()],
            mana={ManaType.COLORLESS: 2, ManaType.BLUE: 4},
        )
        set_board_state(game, 1, hand=[enemy], mana=_mana_for(enemy_cost))

        set_player(game, 0, DeterministicPlayer("P0", script=[
            no_op(),
            perform_action(CastSpell("Mana Sculpt", targets=["Enemy Spell"])),
            # ORACLE-ENGINE QUIRK, not the spec: the oracle impl's
            # get_targets() returns the target *pool* (every spell on the
            # stack), and the canonical cast pipeline prompts once per
            # returned entry — so with two spells on the stack this cast
            # answers two prompts even though a counterspell takes a single
            # target.  Both answers name the enemy spell; the impl uses
            # chosen_targets[0].  Do not treat this shape as normative.
            perform_action(CastSpell(
                "Mana Sculpt", targets=["Enemy Spell", "Enemy Spell"],
            )),
            no_op(),
            no_op(),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[
            perform_action(CastSpell("Enemy Spell")),
            no_op(),
            no_op(),
            no_op(),
        ]))

        priority_loop(game)

        # The enemy spell was countered exactly once; both Sculpts resolved.
        assert_in_zone(game, 1, Zone.GRAVEYARD, "Enemy Spell", count=1)
        assert_in_zone(game, 0, Zone.GRAVEYARD, "Mana Sculpt", count=2)
        assert_zone_count(game, 1, Zone.GRAVEYARD, 1)
        assert_stack_empty(game)

        # Exactly one refund (the fizzled copy registered none).
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert_mana_pool(game, 0, {ManaType.COLORLESS: 3})
