"""Tests for SOS 120 — Improvisation Capstone.

Improvisation Capstone is a {5}{R}{R} Sorcery — Lesson with the Paradigm keyword.
It:
  1. Exiles cards from the top of the library until the total mana value
     of exiled cards is 4 or greater.
  2. Allows casting any number of spells from among those exiled cards
     for free (without paying their mana costs).
  3. Paradigm: After resolution, the card itself is exiled (not graveyard).
  4. After the first resolution, at the beginning of each of the
     controller's precombat main phases, the controller may cast a free
     copy from exile.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import CardImpl, Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _spell(name: str = "Test Spell", mana_value: int = 2, is_sorcery: bool = False, owner=None, controller=None) -> CardImpl:
    """A minimal instant or sorcery with the given mana cost."""
    card_type = CardType.SORCERY if is_sorcery else CardType.INSTANT
    c = CardImpl(
        name=name,
        mana_cost=ManaCost(generic=mana_value),
        card_types={card_type},
        owner=owner,
        controller=controller,
    )
    return c


def _creature_card(name: str = "Test Bear", mana_value: int = 2, owner=None, controller=None) -> Creature:
    """A minimal creature card."""
    return Creature(
        name=name,
        owner=owner,
        controller=controller,
        base_power=2,
        base_toughness=2,
        mana_cost=ManaCost(generic=mana_value),
    )


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneProperties:
    """Static card data must match the SOS 120 spec."""

    def test_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        assert ImprovisationCapstone(owner=None).name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        assert ImprovisationCapstone(owner=None).mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_cmc_is_seven(self) -> None:
        assert ImprovisationCapstone(owner=None).mana_cost.cmc == 7

    def test_card_type_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert CardType.SORCERY in card.card_types

    def test_is_lesson_subtype(self) -> None:
        card = ImprovisationCapstone(owner=None)
        subtypes = getattr(card, "subtypes", set())
        assert "Lesson" in subtypes


# ---------------------------------------------------------------------------
# Library exile — stop condition
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneExile:
    """on_resolve exiles library cards until total mana value >= 4."""

    def test_exiles_cards_until_mv_4_or_greater(self) -> None:
        """With MV-2 + MV-2 at the top, stops after 2 cards (total=4)."""
        game = create_game()
        p1 = game.players[0]

        spell_a = _spell("Spell A", mana_value=2, owner=p1, controller=p1)
        spell_b = _spell("Spell B", mana_value=2, owner=p1, controller=p1)
        spell_c = _spell("Spell C", mana_value=3, owner=p1, controller=p1)

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)
        # Top = spell_a, then spell_b, then spell_c
        library.add(spell_c)
        library.add(spell_b)
        library.add(spell_a)

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        exile = game.get_exile(p1)
        exiled_names = {getattr(c, "name", None) for c in exile.get_all()
                        if getattr(c, "name", None) != "Improvisation Capstone"}
        assert "Spell A" in exiled_names
        assert "Spell B" in exiled_names
        # The total after 2 cards is already 4, so Spell C must NOT be exiled
        assert "Spell C" not in exiled_names

    def test_exiles_multiple_low_mv_cards_until_threshold(self) -> None:
        """With MV-1 cards, exiles until cumulative >= 4 (i.e., 4 cards)."""
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)

        cards = [_spell(f"Low Spell {i}", mana_value=1, owner=p1, controller=p1) for i in range(6)]
        # Add in reverse so first card is on top
        for c in reversed(cards):
            library.add(c)

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        exile = game.get_exile(p1)
        exiled = [c for c in exile.get_all()
                  if getattr(c, "name", None) != "Improvisation Capstone"]
        # 4 cards of MV 1 each = total 4
        assert len(exiled) == 4

    def test_single_high_mv_card_stops_immediately(self) -> None:
        """A single card with MV >= 4 exiles only that one card."""
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)

        big_card = _spell("Big Spell", mana_value=5, owner=p1, controller=p1)
        small_card = _spell("Small Spell", mana_value=1, owner=p1, controller=p1)
        library.add(small_card)
        library.add(big_card)  # top of library

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        exile = game.get_exile(p1)
        exiled_names = {getattr(c, "name", None) for c in exile.get_all()
                        if getattr(c, "name", None) != "Improvisation Capstone"}
        assert "Big Spell" in exiled_names
        assert "Small Spell" not in exiled_names

    def test_empty_library_stops_gracefully(self) -> None:
        """If library runs out before threshold, no crash."""
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)

        # Just 2 MV-1 cards — total will be 2, never reaching 4
        for i in range(2):
            c = _spell(f"Tiny {i}", mana_value=1, owner=p1, controller=p1)
            library.add(c)

        card = ImprovisationCapstone(owner=p1, controller=p1)
        # Must not raise even though library is depleted before threshold
        card.on_resolve(game)

    def test_zero_mv_cards_are_exiled_but_do_not_count(self) -> None:
        """Cards with MV 0 are exiled but contribute 0 to the threshold count."""
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)

        zero_mv = CardImpl(
            name="Zero Cost",
            mana_cost=ManaCost(),
            card_types={CardType.INSTANT},
            owner=p1, controller=p1,
        )
        four_mv = _spell("Four MV", mana_value=4, owner=p1, controller=p1)
        library.add(four_mv)   # second from top
        library.add(zero_mv)   # top of library

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        exile = game.get_exile(p1)
        exiled_names = {getattr(c, "name", None) for c in exile.get_all()
                        if getattr(c, "name", None) != "Improvisation Capstone"}
        # Zero Cost: exiled (MV 0), then Four MV: exiled (cumulative now 4)
        assert "Zero Cost" in exiled_names
        assert "Four MV" in exiled_names


# ---------------------------------------------------------------------------
# Paradigm — exile instead of graveyard
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneParadigmExile:
    """Paradigm: after resolution the card itself goes to exile, not graveyard."""

    def test_card_is_in_exile_after_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)
        # Add enough cards for the effect to have something to work with
        for i in range(3):
            library.add(_spell(f"S{i}", mana_value=2, owner=p1, controller=p1))

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        exile = game.get_exile(p1)
        exile_names = [getattr(c, "name", None) for c in exile.get_all()]
        assert "Improvisation Capstone" in exile_names

    def test_card_is_not_in_graveyard_after_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)
        for i in range(3):
            library.add(_spell(f"S{i}", mana_value=2, owner=p1, controller=p1))

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        graveyard = game.get_graveyard(p1)
        gy_names = [getattr(c, "name", None) for c in graveyard.get_all()]
        assert "Improvisation Capstone" not in gy_names


# ---------------------------------------------------------------------------
# Paradigm — tracks first resolution
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneParadigmFirstResolved:
    """After first resolution, the card marks itself as first-resolved."""

    def test_first_resolved_flag_is_false_before_resolve(self) -> None:
        card = ImprovisationCapstone(owner=None)
        # Before any resolution, the first_resolved flag should be falsy
        assert not getattr(card, "paradigm_first_resolved", False)

    def test_first_resolved_flag_is_set_after_resolve(self) -> None:
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)
        for i in range(3):
            library.add(_spell(f"S{i}", mana_value=2, owner=p1, controller=p1))

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        assert getattr(card, "paradigm_first_resolved", False)


# ---------------------------------------------------------------------------
# Paradigm — triggers at beginning of main phase
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneParadigmTrigger:
    """After first resolution, a delayed trigger fires at the start of
    controller's precombat main phases to offer a free copy cast."""

    def test_trigger_registered_after_first_resolution(self) -> None:
        """After resolving, a trigger is registered with the trigger manager."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)
        for i in range(3):
            library.add(_spell(f"S{i}", mana_value=2, owner=p1, controller=p1))

        card = ImprovisationCapstone(owner=p1, controller=p1)
        triggers_before = len(game.trigger_manager._registrations)
        card.on_resolve(game)
        triggers_after = len(game.trigger_manager._registrations)

        assert triggers_after > triggers_before

    def test_trigger_does_not_fire_for_opponent_main_phase(self) -> None:
        """The trigger must not fire during the opponent's main phase."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)
        for i in range(3):
            library.add(_spell(f"S{i}", mana_value=2, owner=p1, controller=p1))

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        # Fire the event for p2's main phase — should not add anything to stack
        stack_size_before = len(list(game.stack.objects()))
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent(player=p2))
        stack_size_after = len(list(game.stack.objects()))

        assert stack_size_after == stack_size_before

    def test_trigger_fires_for_controller_main_phase(self) -> None:
        """The trigger fires during controller's main phase after first resolution.
        When the player accepts the offer (True), a copy is placed on the stack."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.player import DeterministicPlayer

        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)
        for i in range(3):
            library.add(_spell(f"S{i}", mana_value=2, owner=p1, controller=p1))

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        # Script p1 to accept the offer (True = cast the copy)
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(True)

        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent(player=p1))

        # After accepting, a copy of Improvisation Capstone must be on the stack
        # (cast for free via Paradigm)
        stack_objects = list(game.stack.objects())
        stack_names = [getattr(getattr(obj, "source", None), "name", None) for obj in stack_objects]
        assert "Improvisation Capstone" in stack_names, (
            "Accepting the Paradigm offer must place a copy on the stack"
        )

    def test_trigger_persists_across_multiple_main_phases(self) -> None:
        """Paradigm fires each turn, not just the first. The trigger should
        remain registered after multiple firings."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)
        for i in range(3):
            library.add(_spell(f"S{i}", mana_value=2, owner=p1, controller=p1))

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        from engine.player import DeterministicPlayer

        # Fire first main phase — script p1 to decline (False = don't cast)
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(False)
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent(player=p1))

        # Trigger should still be registered for the next turn
        trigger_count_after_first = len(game.trigger_manager._registrations)
        assert trigger_count_after_first > 0

        # Fire second main phase — trigger should fire again
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(False)
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent(player=p1))
        # Still registered (perpetual)
        assert len(game.trigger_manager._registrations) > 0


# ---------------------------------------------------------------------------
# Free cast from exiled pool
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneFreeCast:
    """Spells from the exiled pool may be cast without paying mana costs."""

    def test_exiled_spells_are_available_for_free_cast(self) -> None:
        """After resolution, the card knows which spells were exiled."""
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)

        spell_a = _spell("Cast Me", mana_value=3, owner=p1, controller=p1)
        spell_b = _spell("Also Me", mana_value=2, owner=p1, controller=p1)
        library.add(spell_b)
        library.add(spell_a)  # top

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        # The card must track the pool of castable exiled spells.
        castable = getattr(card, "exiled_castable_pool", None)
        assert castable is not None, "card must track exiled_castable_pool"

    def test_exiled_castable_pool_includes_spells_up_to_threshold(self) -> None:
        """The exiled castable pool must contain exactly the cards exiled."""
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)

        spell_a = _spell("A", mana_value=3, owner=p1, controller=p1)
        spell_b = _spell("B", mana_value=2, owner=p1, controller=p1)
        # After exiling A (MV 3) and B (MV 2), total = 5 >= 4 — stops after both
        library.add(spell_b)
        library.add(spell_a)  # top

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        castable = getattr(card, "exiled_castable_pool", [])
        names = {getattr(c, "name", None) for c in castable}
        assert "A" in names
        assert "B" in names


# ---------------------------------------------------------------------------
# Paradigm — precombat vs postcombat discrimination (is_precombat field)
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneParadigmPrecombatOnly:
    """After first resolution, the Paradigm trigger fires ONLY for precombat
    main phases (is_precombat=True), not postcombat (is_precombat=False)."""

    def test_paradigm_fires_for_precombat_main_phase(self) -> None:
        """Trigger fires when BeginningOfMainPhaseTriggeredEvent has is_precombat=True."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.player import DeterministicPlayer

        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)
        for i in range(3):
            library.add(_spell(f"S{i}", mana_value=2, owner=p1, controller=p1))

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        # Script p1 to accept the offer (True = cast the copy)
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(True)

        stack_size_before = len(list(game.stack.objects()))
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_precombat=True)
        )
        stack_size_after = len(list(game.stack.objects()))

        # Accepting the precombat-phase offer must put something on the stack
        assert stack_size_after > stack_size_before, (
            "Paradigm trigger must fire during precombat main phase (is_precombat=True)"
        )

    def test_paradigm_does_not_fire_for_postcombat_main_phase(self) -> None:
        """Trigger must NOT fire when BeginningOfMainPhaseTriggeredEvent has
        is_precombat=False (postcombat main phase)."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)
        for i in range(3):
            library.add(_spell(f"S{i}", mana_value=2, owner=p1, controller=p1))

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        stack_size_before = len(list(game.stack.objects()))
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_precombat=False)
        )
        stack_size_after = len(list(game.stack.objects()))

        assert stack_size_after == stack_size_before, (
            "Paradigm trigger must NOT fire during postcombat main phase (is_precombat=False)"
        )


# ---------------------------------------------------------------------------
# cast_exiled_card — free-cast API
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneFreeCastMethod:
    """The card exposes cast_exiled_card(game, player, card) that casts the
    given exiled card for free (without paying its mana cost)."""

    def test_cast_exiled_card_places_spell_on_stack(self) -> None:
        """cast_exiled_card must place the target card onto the stack."""
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)

        target = _spell("Free Spell", mana_value=4, owner=p1, controller=p1)
        library.add(target)

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)  # exiles target (MV 4 >= 4)

        assert hasattr(card, "cast_exiled_card"), (
            "ImprovisationCapstone must expose cast_exiled_card(game, player, card)"
        )

        stack_size_before = len(list(game.stack.objects()))
        card.cast_exiled_card(game, p1, target)
        stack_size_after = len(list(game.stack.objects()))

        assert stack_size_after > stack_size_before, (
            "cast_exiled_card must place the spell on the stack"
        )

    def test_cast_exiled_card_removes_card_from_castable_pool(self) -> None:
        """After casting, the card should no longer be in the castable pool."""
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for obj in list(library.get_all()):
            library.remove(obj)

        target = _spell("Once Only", mana_value=4, owner=p1, controller=p1)
        library.add(target)

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        pool_before = list(getattr(card, "exiled_castable_pool", []))
        assert any(getattr(c, "name", None) == "Once Only" for c in pool_before), (
            "Once Only must be in the castable pool before casting"
        )

        card.cast_exiled_card(game, p1, target)

        pool_after = list(getattr(card, "exiled_castable_pool", []))
        assert not any(getattr(c, "name", None) == "Once Only" for c in pool_after), (
            "Once Only must be removed from the castable pool after casting"
        )


# ---------------------------------------------------------------------------
# Lesson subtype / Learn synergy
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneLesson:
    """Improvisation Capstone is a Lesson — accessible via Learn."""

    def test_lesson_subtype_present(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert "Lesson" in getattr(card, "subtypes", set())
