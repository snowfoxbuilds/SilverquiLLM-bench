"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater.  You may cast any number of spells from
    among them without paying their mana costs.
    Paradigm (Then exile this spell.  After you first resolve a spell with
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

    def _exile_and_cast(self, game: GameState) -> None:
        """Main effect: exile until total MV >= 4, offer free casts."""
        from engine.casting import CastingError, cast_spell_free
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        library = controller.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top = library.top(1)[0]
            move_to_zone(game, top, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top)
            cost = getattr(top, "mana_cost", None)
            total_mv += cost.cmc if cost is not None else 0

        for card in exiled:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue  # non-castable; stays exiled
            try:
                if controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} without paying "
                    "its mana cost?"
                ):
                    cast_spell_free(game, controller, card, Zone.EXILE)
            except CastingError:
                pass

    def on_resolve(self, game: GameState) -> None:
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # A spell copy is never in a zone; the original card resolves while
        # sitting in its controller's stack zone.
        is_original = controller.zones[Zone.STACK].contains(self)

        self._exile_and_cast(game)

        if not is_original:
            return  # copies just perform the effect

        # Paradigm: exile this spell instead of letting it hit the
        # graveyard, then set up the recurring first-main-phase copy.
        move_to_zone(game, self, Zone.STACK, Zone.EXILE)
        self._register_paradigm_trigger(game)

    def _register_paradigm_trigger(self, game: GameState) -> None:
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.stack import StackObject, copy_spell
        from engine.triggers import TriggerRegistration

        source = self
        controller = self.controller

        def _condition(g: Any, event: Any) -> bool:
            return (
                g.active_player is controller
                and controller.zones[Zone.EXILE].contains(source)
            )

        def _effect(g: GameState) -> None:
            if not controller.zones[Zone.EXILE].contains(source):
                return
            if not controller.choose_yes_no(
                "Cast a copy of Improvisation Capstone from exile without "
                "paying its mana cost?"
            ):
                return
            # The card itself stays in exile; a fresh copy goes on the stack.
            original_so = StackObject(source=source, controller=controller)
            g.stack.push(copy_spell(g, original_so, controller))

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
