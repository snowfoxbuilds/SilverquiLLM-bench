"""Audited tests for The Dawning Archaic (sos_1).

Oracle: {10} Legendary Creature — Avatar 7/7.
  This spell costs {1} less to cast for each instant and sorcery card in
  your graveyard.
  Reach
  Whenever The Dawning Archaic attacks, you may cast target instant or
  sorcery card from your graveyard without paying its mana cost.  If that
  spell would be put into your graveyard, exile it instead.

Simulation-only shape (AUDITED-TEST-API.md):
* Cost reduction is asserted by mana-minimality — the pool holds exactly the
  reduced cost (cast succeeds) or one less (``perform_illegal_action``).
* Attacking is a choice-script answer (the attacker list), reached via
  ``advance_to_phase(COMBAT, ...)``; the attack trigger's may-choice and card
  pick come from the same choice script.
* The granted cast goes through the real pipeline, so the spell-to-exile
  redirect is asserted as the recast object landing in EXILE
  (test_spell_to_exile_after_resolution shape).

Tests:
  1. test_card_identity
  2. test_cost_reduced_by_instants_and_sorceries_in_graveyard
  3. test_cost_reduction_is_not_one_more
  4. test_creatures_in_graveyard_do_not_reduce
  5. test_attack_trigger_casts_instant_from_graveyard_to_exile
  6. test_attack_trigger_may_be_declined
  7. test_attack_trigger_targets_only_chosen_card
  8. test_attack_trigger_sorcery_also_exiled
  9. test_no_trigger_without_instant_or_sorcery_in_graveyard
  10. test_other_spells_still_go_to_graveyard
"""

from __future__ import annotations

from card_impl import TheDawningArchaic

from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaType, Phase, Step, Supertype, Zone
from test_utils import (
    CastSpell,
    DeterministicPlayer,
    advance_to_phase,
    assert_in_zone,
    assert_life_total,
    assert_mana_pool,
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

_NAME = "The Dawning Archaic"


class TestIdentity:
    def test_card_identity(self) -> None:
        card = TheDawningArchaic()
        assert card.name == _NAME
        assert card.mana_cost.generic == 10
        assert card.mana_cost.pips == {}
        assert card.mana_cost.cmc == 10
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes
        assert card.base_power == 7
        assert card.base_toughness == 7


class TestCostReduction:
    """Cost reduction asserted through mana-minimality, never by probing
    ``cost_reduction()`` directly."""

    def _try_cast(self, game, gy_cards, mana_amount, directive) -> None:
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        set_board_state(
            game, 0,
            hand=[TheDawningArchaic()],
            graveyard=gy_cards,
            mana={ManaType.COLORLESS: mana_amount},
        )
        set_player(game, 0, DeterministicPlayer("P0", script=[
            directive(CastSpell(_NAME)),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[no_op()]))
        priority_loop(game)

    def test_cost_reduced_by_instants_and_sorceries_in_graveyard(self) -> None:
        """Two instants in the graveyard → {10} casts for exactly 8."""
        game = create_game()
        self._try_cast(
            game,
            [Instant(name="Lightning Bolt"), Instant(name="Shock")],
            8,
            perform_action,
        )
        assert_in_zone(game, 0, Zone.BATTLEFIELD, _NAME)
        assert_mana_pool(game, 0, {})

    def test_cost_reduction_is_not_one_more(self) -> None:
        """With two instants in the graveyard, 7 mana is NOT enough."""
        game = create_game()
        self._try_cast(
            game,
            [Instant(name="Lightning Bolt"), Instant(name="Shock")],
            7,
            perform_illegal_action,
        )
        assert_in_zone(game, 0, Zone.HAND, _NAME)

    def test_creatures_in_graveyard_do_not_reduce(self) -> None:
        """A creature plus one instant reduce by exactly 1 — 8 mana (which
        would suffice if the creature wrongly counted) is rejected."""
        game = create_game()
        self._try_cast(
            game,
            [
                Creature(name="Bear", base_power=2, base_toughness=2),
                Instant(name="Lightning Bolt"),
            ],
            8,
            perform_illegal_action,
        )
        assert_in_zone(game, 0, Zone.HAND, _NAME)


class TestAttackTrigger:
    """The attack trigger fires off the declared attacker; its may-choice and
    card pick come from the choice script (Channel 2)."""

    def _attack(self, game, gy_cards, choices) -> None:
        archaic = TheDawningArchaic()
        set_board_state(game, 0, battlefield=[archaic], graveyard=gy_cards)
        set_player(game, 0, DeterministicPlayer(
            "P0", choices=[[archaic], *choices],
        ))
        set_player(game, 1, DeterministicPlayer("P1"))
        advance_to_phase(game, Phase.COMBAT, Step.DECLARE_ATTACKERS)

    def test_attack_trigger_casts_instant_from_graveyard_to_exile(self) -> None:
        """Accepting the may-cast recasts the instant; on resolution it is
        exiled instead of returning to the graveyard."""
        game = create_game()
        bolt = Instant(name="Lightning Bolt")
        self._attack(game, [bolt], choices=[True])

        assert_in_zone(game, 0, Zone.EXILE, "Lightning Bolt")
        assert_zone_count(game, 0, Zone.GRAVEYARD, 0)
        assert_stack_empty(game)

    def test_attack_trigger_may_be_declined(self) -> None:
        """Declining the 'may' leaves the graveyard untouched."""
        game = create_game()
        bolt = Instant(name="Lightning Bolt")
        self._attack(game, [bolt], choices=[False])

        assert_in_zone(game, 0, Zone.GRAVEYARD, "Lightning Bolt")
        assert_zone_count(game, 0, Zone.EXILE, 0)
        assert_stack_empty(game)

    def test_attack_trigger_targets_only_chosen_card(self) -> None:
        """With several instants in the graveyard, only the chosen one is
        cast and exiled."""
        game = create_game()
        bolt = Instant(name="Lightning Bolt")
        shock = Instant(name="Shock")
        self._attack(game, [bolt, shock], choices=[True, bolt])

        assert_in_zone(game, 0, Zone.EXILE, "Lightning Bolt")
        assert_in_zone(game, 0, Zone.GRAVEYARD, "Shock")
        assert_zone_count(game, 0, Zone.EXILE, 1)

    def test_attack_trigger_sorcery_also_exiled(self) -> None:
        game = create_game()
        divination = Sorcery(name="Divination")
        self._attack(game, [divination], choices=[True])

        assert_in_zone(game, 0, Zone.EXILE, "Divination")
        assert_zone_count(game, 0, Zone.GRAVEYARD, 0)

    def test_no_trigger_without_instant_or_sorcery_in_graveyard(self) -> None:
        """With no instant/sorcery in the graveyard the trigger does not fire
        (a dry choice script would fail the test if it did), and the 7/7
        unblocked attacker connects for 7."""
        game = create_game()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        archaic = TheDawningArchaic()
        set_board_state(game, 0, battlefield=[archaic], graveyard=[bear])
        set_player(game, 0, DeterministicPlayer("P0", choices=[[archaic]]))
        set_player(game, 1, DeterministicPlayer("P1"))

        advance_to_phase(game, Phase.COMBAT, Step.COMBAT_DAMAGE)

        assert_life_total(game, 1, 13)
        assert_in_zone(game, 0, Zone.GRAVEYARD, "Bear")

    def test_other_spells_still_go_to_graveyard(self) -> None:
        """The exile redirect is scoped to the trigger-cast spell — a spell
        cast normally afterwards still goes to the graveyard."""
        game = create_game()
        bolt = Instant(name="Lightning Bolt")
        self._attack(game, [bolt], choices=[True])
        assert_in_zone(game, 0, Zone.EXILE, "Lightning Bolt")

        shock = Instant(name="Shock", mana_cost=None)
        set_board_state(game, 0, hand=[shock], mana={})
        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_action(CastSpell("Shock")),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[no_op()]))
        priority_loop(game)

        assert_in_zone(game, 0, Zone.GRAVEYARD, "Shock")
        assert_zone_count(game, 0, Zone.EXILE, 1)
