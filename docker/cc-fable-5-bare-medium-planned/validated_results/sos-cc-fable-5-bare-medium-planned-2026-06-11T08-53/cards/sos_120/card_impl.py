"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


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

    def on_resolve(self, game: GameState) -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # 1. Exile from the top of the library until total MV >= 4
        #    (or the library runs out).
        library = game.get_library(controller)
        exiled: list[Any] = []
        total = 0
        while total < 4 and len(library) > 0:
            top_card = library.top(1)[0]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top_card)
            total += getattr(top_card.mana_cost, "cmc", 0)

        # 2. May cast any number of spells from among them for free.
        #    Lands are not spells and stay exiled.
        exile_zone = game.get_exile(controller)
        for card in exiled:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            if not exile_zone.contains(card):
                continue
            try:
                wants = controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} without paying "
                    "its mana cost?"
                )
            except Exception:
                wants = False
            if not wants:
                continue
            try:
                cast_spell_free(game, controller, card, Zone.EXILE)
            except CastingError:
                pass

        # 3. Paradigm.
        self._apply_paradigm(game, controller)

    # ------------------------------------------------------------------
    # Paradigm (card-local)
    # ------------------------------------------------------------------

    def _apply_paradigm(self, game: GameState, controller: Player) -> None:
        from engine.events import SpellGoesToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        source = self

        # "Then exile this spell" — redirect this spell's own move to the
        # graveyard after resolution (one-shot).
        def _replace(g: Any, event: Any) -> Any:
            event.destination = "exile"
            g.replacement_manager.unregister(source)
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=SpellGoesToGraveyardReplacementEvent,
                source=source,
                condition=lambda g, ev: ev.card is source,
                replacement=_replace,
                controller=controller,
            )
        )

        # Only the *first* resolution of a spell with this name (per
        # player) sets up the recurring first-main-phase copy trigger.
        resolved_names = getattr(controller, "_paradigm_resolved_names", None)
        if resolved_names is None:
            resolved_names = set()
            controller._paradigm_resolved_names = resolved_names
        if self.name in resolved_names:
            return
        resolved_names.add(self.name)

        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.triggers import TriggerRegistration

        def _condition(g: Any, event: Any) -> bool:
            return g.active_player is controller

        def _effect(g: GameState) -> None:
            from engine.casting import CastingError, cast_spell_free

            # Create a copy of this card in exile, then offer to cast it.
            copy_card = type(source)(owner=controller, controller=controller)
            g.get_exile(controller).add(copy_card)
            try:
                wants = controller.choose_yes_no(
                    f"Cast the Paradigm copy of {source.name} without "
                    "paying its mana cost?"
                )
            except Exception:
                wants = False
            if not wants:
                return
            try:
                cast_spell_free(g, controller, copy_card, Zone.EXILE)
            except CastingError:
                pass

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
