"""Audited tests for Improvisation Capstone (sos_120).

Oracle: {5}{R}{R} Sorcery — Lesson.
  Exile cards from the top of your library until you exile cards with total
  mana value 4 or greater.  You may cast any number of spells from among them
  without paying their mana costs.
  Paradigm (Then exile this spell.  After you first resolve a spell with this
  name, you may cast a copy of it from exile without paying its mana cost at
  the beginning of each of your first main phases.)

Simulation-only shape (AUDITED-TEST-API.md): the spell is cast for real via a
``CastSpell`` directive; its resolution self-drains (the free casts happen
inside ``on_resolve``), so the tests assert only end-state — never a
mid-cascade stack.  The Paradigm self-exile is the
test_spell_to_exile_after_resolution shape: the cast object lands in EXILE
instead of the graveyard.  Recurrence is reached by placing the card in exile
via setup and fast-forwarding into the controller's first main phase; the
may-cast is answered from the choice script.

Tests:
  1. test_card_identity
  2. test_cast_exiles_until_mv_threshold_and_self_exiles
  3. test_exiled_card_may_be_cast_for_free
  4. test_exiled_card_cast_may_be_declined
  5. test_paradigm_recurrence_casts_copy_from_exile
  6. test_paradigm_recurrence_may_be_declined
"""

from __future__ import annotations

from card_impl import ImprovisationCapstone

from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import (
    CastSpell,
    DeterministicPlayer,
    advance_to_phase,
    assert_in_zone,
    assert_library_order,
    assert_mana_pool,
    assert_stack_empty,
    assert_zone_count,
    create_game,
    no_op,
    perform_action,
    priority_loop,
    set_board_state,
    set_player,
)

_NAME = "Improvisation Capstone"
_CAST_MANA = {ManaType.COLORLESS: 5, ManaType.RED: 2}


def _cast_capstone(game, library, choices) -> None:
    """Cast Improvisation Capstone for real with the given library/choices."""
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    set_board_state(
        game, 0,
        hand=[ImprovisationCapstone()],
        library=library,
        mana=_CAST_MANA,
    )
    set_player(game, 0, DeterministicPlayer("P0", script=[
        perform_action(CastSpell(_NAME)),
        no_op(),
    ], choices=choices))
    set_player(game, 1, DeterministicPlayer("P1", script=[no_op()]))
    priority_loop(game)


class TestIdentity:
    def test_card_identity(self) -> None:
        card = ImprovisationCapstone()
        assert card.name == _NAME
        assert isinstance(card, Sorcery)
        assert CardType.SORCERY in card.card_types
        assert card.mana_cost.generic == 5
        assert card.mana_cost.pips.get(ManaType.RED) == 2
        assert card.mana_cost.cmc == 7
        assert "Lesson" in card.subtypes


class TestCastBehaviour:
    def test_cast_exiles_until_mv_threshold_and_self_exiles(self) -> None:
        """Cards come off the top until their total mana value reaches 4
        (cards below stay put), and the resolved spell itself is exiled
        instead of going to the graveyard (Paradigm)."""
        game = create_game()
        c1 = Instant(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        c2 = Creature(
            name="Bear",
            mana_cost=ManaCost(generic=1, pips={ManaType.GREEN: 1}),
            base_power=2, base_toughness=2,
        )
        c3 = Instant(name="Shock", mana_cost=ManaCost(generic=1, pips={ManaType.RED: 1}))
        filler = Creature(
            name="Filler", mana_cost=ManaCost(generic=5),
            base_power=5, base_toughness=5,
        )

        # MV 1 + 2 = 3 < 4, so a third card (MV 2) is exiled as well; the
        # player declines to cast each of the three exiled cards.
        _cast_capstone(game, [c1, c2, c3, filler], choices=[False, False, False])

        assert_in_zone(game, 0, Zone.EXILE, "Bolt")
        assert_in_zone(game, 0, Zone.EXILE, "Bear")
        assert_in_zone(game, 0, Zone.EXILE, "Shock")
        assert_library_order(game, 0, ["Filler"])

        # Paradigm: the spell ends in exile, not the graveyard.
        assert_in_zone(game, 0, Zone.EXILE, _NAME)
        assert_zone_count(game, 0, Zone.GRAVEYARD, 0)
        assert_stack_empty(game)
        assert_mana_pool(game, 0, {})

    def test_exiled_card_may_be_cast_for_free(self) -> None:
        """Accepting the offer casts the exiled creature without paying its
        cost — it resolves onto the battlefield."""
        game = create_game()
        bigguy = Creature(
            name="BigGuy", mana_cost=ManaCost(generic=4),
            base_power=4, base_toughness=4,
        )

        _cast_capstone(game, [bigguy], choices=[True])

        assert_in_zone(game, 0, Zone.BATTLEFIELD, "BigGuy")
        assert_in_zone(game, 0, Zone.EXILE, _NAME)
        # The free cast consumed no mana (the pool was already exactly spent
        # on Improvisation Capstone itself).
        assert_mana_pool(game, 0, {})

    def test_exiled_card_cast_may_be_declined(self) -> None:
        """Declining the offer leaves the exiled card in exile."""
        game = create_game()
        bigguy = Creature(
            name="BigGuy", mana_cost=ManaCost(generic=4),
            base_power=4, base_toughness=4,
        )

        _cast_capstone(game, [bigguy], choices=[False])

        assert_in_zone(game, 0, Zone.EXILE, "BigGuy")
        assert_zone_count(game, 0, Zone.BATTLEFIELD, 0)


class TestParadigmRecurrence:
    """The recurring may-cast from exile at the beginning of the controller's
    first main phase.  The copy self-drains inside the trigger's resolution,
    so only end-state is asserted."""

    def test_paradigm_recurrence_casts_copy_from_exile(self) -> None:
        game = create_game()
        capstone = ImprovisationCapstone()
        set_board_state(game, 0, exile=[capstone])
        set_player(game, 0, DeterministicPlayer("P0", choices=[True]))
        set_player(game, 1, DeterministicPlayer("P1"))

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        # A copy was cast and resolved (empty library → no exiling); the copy
        # ceases by going to the graveyard while the original stays in exile.
        assert_in_zone(game, 0, Zone.EXILE, _NAME, count=1)
        assert_in_zone(game, 0, Zone.GRAVEYARD, _NAME, count=1)
        assert_stack_empty(game)

    def test_paradigm_recurrence_may_be_declined(self) -> None:
        game = create_game()
        capstone = ImprovisationCapstone()
        set_board_state(game, 0, exile=[capstone])
        set_player(game, 0, DeterministicPlayer("P0", choices=[False]))
        set_player(game, 1, DeterministicPlayer("P1"))

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        assert_in_zone(game, 0, Zone.EXILE, _NAME, count=1)
        assert_zone_count(game, 0, Zone.GRAVEYARD, 0)
        assert_zone_count(game, 0, Zone.BATTLEFIELD, 0)
