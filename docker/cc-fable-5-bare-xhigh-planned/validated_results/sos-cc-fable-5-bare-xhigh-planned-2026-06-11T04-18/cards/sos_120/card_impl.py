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

    def on_resolve(self, game: GameState) -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # 1. Exile from the top of the library until total mana value >= 4
        #    (or the library runs out).
        library = game.get_library(controller)
        exiled: list[Any] = []
        total = 0
        while total < 4 and len(library) > 0:
            card = library.top(1)[0]
            move_to_zone(game, card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(card)
            total += getattr(getattr(card, "mana_cost", None), "cmc", 0)

        # 2. You may cast any number of them without paying their costs.
        #    Repeated choose_card over the remaining castable cards; None
        #    stops. Lands are not castable and stay exiled.
        castable = [
            c for c in exiled if CardType.LAND not in getattr(c, "card_types", set())
        ]
        while castable:
            try:
                chosen = controller.choose_card(
                    castable,
                    "cast a spell from among the exiled cards without paying "
                    "its mana cost (None to stop)",
                )
            except Exception:
                chosen = None
            if chosen is None or chosen not in castable:
                break
            castable.remove(chosen)
            try:
                cast_spell_free(game, controller, chosen, Zone.EXILE)
            except CastingError:
                continue  # uncastable card stays exiled

        # 3. Paradigm — exile this spell. (For a copy, which exists in no
        #    zone, this is a silent no-op.)
        move_to_zone(game, self, Zone.STACK, Zone.EXILE)

        # "After you FIRST resolve a spell with this name": register the
        # recurring first-main-phase trigger only once per player per name.
        resolved_names = getattr(controller, "_paradigm_resolved_names", None)
        if resolved_names is None:
            resolved_names = set()
            controller._paradigm_resolved_names = resolved_names
        if self.name in resolved_names:
            return
        resolved_names.add(self.name)
        self._register_paradigm_trigger(game, controller)

    def _register_paradigm_trigger(self, game: GameState, controller: Any) -> None:
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.stack import StackObject, copy_spell
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: Any, event: Any) -> bool:
            return g.active_player is controller

        def _effect(g: GameState) -> None:
            # The exiled original must still be in exile to copy it.
            owner = getattr(source, "owner", controller)
            if owner is None or not g.get_exile(owner).contains(source):
                return
            try:
                wants = controller.choose_yes_no(
                    f"cast a copy of {source.name} from exile without paying "
                    "its mana cost?"
                )
            except Exception:
                wants = False
            if not wants:
                return
            original_so = StackObject(source=source, controller=controller)
            copy_obj = copy_spell(g, original_so, controller)
            g.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
