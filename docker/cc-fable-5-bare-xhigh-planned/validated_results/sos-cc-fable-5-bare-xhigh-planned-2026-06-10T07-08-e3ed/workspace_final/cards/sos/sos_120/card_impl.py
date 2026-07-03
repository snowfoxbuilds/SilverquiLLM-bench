"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy as _copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
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

    def on_resolve(self, game: "GameState") -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # --- Main effect: exile from the top of the library until total
        # mana value >= 4 (or the library runs out). ---
        library = controller.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top_card = library.get_all()[-1]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            cost = getattr(top_card, "mana_cost", None)
            total_mv += cost.cmc if cost is not None else 0
            exiled.append(top_card)

        # May cast any number of them for free (lands are not castable
        # and stay exiled).
        castable = [
            c
            for c in exiled
            if CardType.LAND not in getattr(c, "card_types", set())
        ]
        for card in castable:
            try:
                if controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} without paying "
                    "its mana cost?"
                ):
                    cast_spell_free(game, controller, card, Zone.EXILE)
            except CastingError:
                pass
            except Exception:
                pass

        # --- Paradigm ---
        if getattr(self, "_is_paradigm_copy", False):
            # A resolved spell copy ceases to exist (rule 707.10a): pull it
            # out of the stack zone instead of letting it hit a graveyard.
            self._register_copy_disposal(game, controller)
            return

        # "Exile this spell" — redirect the post-resolution graveyard move.
        self._register_self_exile(game, controller)

        # "After you FIRST resolve a spell with this name": register the
        # recurring beginning-of-your-precombat-main trigger only once per
        # player per name.
        resolved_names = getattr(controller, "_paradigm_resolved_names", None)
        if resolved_names is None:
            resolved_names = set()
            controller._paradigm_resolved_names = resolved_names
        if self.name in resolved_names:
            return
        resolved_names.add(self.name)
        self._register_paradigm_trigger(game, controller)

    # ------------------------------------------------------------------
    # Paradigm helpers (card-local)
    # ------------------------------------------------------------------

    def _register_self_exile(self, game: "GameState", controller: Any) -> None:
        """One-shot replacement: this spell goes to exile, not the graveyard."""
        from engine.events import MoveToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        source = self
        marker = object()

        def _condition(g: Any, event: Any) -> bool:
            return event.card is source

        def _replacement(g: Any, event: Any) -> Any:
            event.destination = "exile"
            g.replacement_manager.unregister(marker)
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=marker,
                condition=_condition,
                replacement=_replacement,
                controller=controller,
            )
        )

    def _register_copy_disposal(self, game: "GameState", controller: Any) -> None:
        """One-shot replacement: a resolved copy ceases to exist."""
        from engine.events import MoveToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        source = self
        marker = object()

        def _condition(g: Any, event: Any) -> bool:
            return event.card is source

        def _replacement(g: Any, event: Any) -> Any:
            for player in g.players:
                stack_zone = player.zones[Zone.STACK]
                if stack_zone.contains(source):
                    stack_zone.remove(source)
                    break
            event.prevented = True
            g.replacement_manager.unregister(marker)
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=marker,
                condition=_condition,
                replacement=_replacement,
                controller=controller,
            )
        )

    def _register_paradigm_trigger(self, game: "GameState", controller: Any) -> None:
        """Recurring: at each of your precombat mains, may cast a copy free."""
        from engine.casting import CastingError, cast_spell_free
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: Any, event: Any) -> bool:
            return g.active_player is controller

        def _effect(g: "GameState") -> None:
            try:
                wants = controller.choose_yes_no(
                    f"Cast a copy of {source.name} from exile without "
                    "paying its mana cost?"
                )
            except Exception:
                wants = False
            if not wants:
                return
            # Create the copy in exile, then cast it from there
            # (rule 707.12); the copy is disposed of after it resolves.
            spell_copy = _copy.copy(source)
            spell_copy._is_paradigm_copy = True
            spell_copy.owner = controller
            spell_copy.controller = controller
            controller.zones[Zone.EXILE].add(spell_copy)
            try:
                cast_spell_free(g, controller, spell_copy, Zone.EXILE)
            except CastingError:
                controller.zones[Zone.EXILE].remove(spell_copy)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
