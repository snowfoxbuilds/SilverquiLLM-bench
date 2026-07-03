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

        # 1. Exile from the top of the library until total MV >= 4.
        library = controller.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top_card = library.top(1)[0]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top_card)
            cost = getattr(top_card, "mana_cost", None)
            total_mv += cost.cmc if cost is not None else 0

        # 2. May cast any number of them for free (lands are not spells
        #    and stay exiled without a prompt).
        for card in exiled:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            if not controller.choose_yes_no(
                f"Cast {card.name} without paying its mana cost?"
            ):
                continue
            try:
                cast_spell_free(game, controller, card, Zone.EXILE)
            except CastingError:
                pass  # not castable right now — stays exiled

        # 3. Paradigm — only for the real card (a spell copy resolving via
        #    copy_spell is never in a stack zone and is skipped).
        on_stack = any(
            p.zones[Zone.STACK].contains(self) for p in game.players
        )
        if not on_stack:
            return
        # "Then exile this spell." (the engine's stack→graveyard move
        # later becomes a no-op since the card has left the stack zone)
        move_to_zone(game, self, Zone.STACK, Zone.EXILE)

        # "After you FIRST resolve a spell with this name" — register the
        # recurring main-phase trigger only once per controller.
        seen = getattr(controller, "_paradigm_first_resolved", None)
        if seen is None:
            seen = set()
            controller._paradigm_first_resolved = seen
        if self.name in seen:
            return
        seen.add(self.name)
        self._register_paradigm_trigger(game, controller)

    def _register_paradigm_trigger(self, game: "GameState", controller: Any) -> None:
        """At the beginning of each of *controller*'s precombat main
        phases, they may cast a copy of this card from exile for free."""
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.stack import StackObject, copy_spell
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            if game.active_player is not controller:
                return False
            # The card must still be in its controller's exile zone.
            return controller.zones[Zone.EXILE].contains(source)

        def _effect(game: "GameState") -> None:
            if not controller.choose_yes_no(
                f"Cast a copy of {source.name} from exile without paying "
                "its mana cost?"
            ):
                return
            # The copy resolves on its own and never changes zones; the
            # exiled original stays in exile.
            template = StackObject(source=source, controller=controller, targets=[])
            game.stack.push(copy_spell(game, template, controller))

        game.trigger_manager.register(TriggerRegistration(
            event_type=BeginningOfPrecombatMainTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
