"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import BeginningOfPrecombatMainTriggeredEvent
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells from
    among them without paying their mana costs.
    Paradigm (Then exile this spell. After you first resolve a spell with
    this name, you may cast a copy of it from exile without paying its
    mana cost at the beginning of each of your first main phases.)

    SOS collector number 120.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards "
            "with total mana value 4 or greater. You may cast any number of "
            "spells from among them without paying their mana costs.\n"
            "Paradigm (Then exile this spell. After you first resolve a "
            "spell with this name, you may cast a copy of it from exile "
            "without paying its mana cost at the beginning of each of your "
            "first main phases.)",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Main effect
    # ------------------------------------------------------------------

    def _exile_and_freecast(self, game: GameState) -> None:
        """Exile from the library top until total MV >= 4; offer free casts."""
        from engine.casting import CastingError, cast_spell_free
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        library = game.get_library(controller)
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            card = library.top(1)[0]
            move_to_zone(game, card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(card)
            total_mv += getattr(card, "mana_cost", ManaCost()).cmc

        # You may cast any number of spells from among them (lands are not
        # spells and stay exiled).
        castable = [
            c for c in exiled
            if CardType.LAND not in getattr(c, "card_types", set())
        ]
        while castable:
            try:
                chosen = controller.choose_card(
                    castable,
                    "Cast a spell from among the exiled cards without paying "
                    "its mana cost (None to stop)",
                )
            except Exception:
                break
            if chosen is None or chosen not in castable:
                break
            castable.remove(chosen)
            try:
                cast_spell_free(game, controller, chosen, Zone.EXILE)
            except CastingError:
                pass  # not currently castable — it simply stays exiled

    def on_resolve(self, game: GameState) -> None:
        from engine.game import exile

        self._exile_and_freecast(game)

        # Paradigm copies resolve without re-exiling or re-registering —
        # only the first resolution of the real card sets up the recurrence.
        if getattr(self, "_is_paradigm_copy", False):
            return

        controller = self.controller
        if controller is None:
            return

        # Then exile this spell (pre-empts the normal stack->graveyard move).
        exile(game, self)
        self._register_paradigm_trigger(game, controller)

    # ------------------------------------------------------------------
    # Paradigm recurrence
    # ------------------------------------------------------------------

    def _register_paradigm_trigger(self, game: GameState, controller: Any) -> None:
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: Any, event: Any) -> bool:
            # Each of *your* first (precombat) main phases, while the
            # exiled card is still in exile.
            if g.active_player is not controller:
                return False
            return g.get_exile(controller).contains(source)

        def _effect(g: GameState) -> None:
            from engine.stack import StackObject, copy_spell

            try:
                wants = controller.choose_yes_no(
                    f"Cast a copy of {source.name} from exile without paying "
                    "its mana cost?"
                )
            except Exception:
                wants = False
            if not wants:
                return
            # Copy the exiled card onto the stack (the original stays in
            # exile for future turns).
            original = StackObject(source=source, controller=controller)
            copy_obj = copy_spell(g, original, controller)
            copy_obj.source._is_paradigm_copy = True
            g.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
