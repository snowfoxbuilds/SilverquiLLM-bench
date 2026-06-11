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

        # 1. Exile from the top of the library until total mana value >= 4
        #    (or the library runs out).
        library = controller.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top_card = library.get_all()[-1]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top_card)
            cost = getattr(top_card, "mana_cost", None)
            total_mv += cost.cmc if cost is not None else 0

        # 2. May cast any number of spells from among them for free.
        #    Lands are not spells — they stay exiled without a prompt.
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
                pass  # not castable right now — it stays exiled

        # 3. Paradigm — exile this spell. A copy resolving has no zone
        #    presence, so this no-ops for copies (the original stays put).
        move_to_zone(game, self, Zone.STACK, Zone.EXILE)
        self._register_paradigm(game, controller)

    def _register_paradigm(self, game: "GameState", controller: Any) -> None:
        """After you FIRST resolve a spell with this name, register the
        recurring first-main-phase copy-cast trigger (once per player)."""
        from engine.events import (
            BeginningOfPrecombatMainTriggeredEvent,
            SpellCastTriggeredEvent,
        )
        from engine.stack import StackObject, copy_spell
        from engine.triggers import TriggerRegistration

        # Card-local first-resolution tracking, per player and card name.
        resolved_names = getattr(controller, "_paradigm_resolved_names", None)
        if resolved_names is None:
            resolved_names = set()
            controller._paradigm_resolved_names = resolved_names
        if self.name in resolved_names:
            return
        resolved_names.add(self.name)

        source = self

        def _condition(game: Any, event: Any) -> bool:
            return game.active_player is controller

        def _effect(game: "GameState") -> None:
            if not controller.choose_yes_no(
                f"Cast a copy of {source.name} from exile without paying "
                "its mana cost?"
            ):
                return
            # Cast a copy: the exiled card itself never leaves exile.
            template = StackObject(source=source, controller=controller)
            copy_obj = copy_spell(game, template, controller)
            game.stack.push(copy_obj)
            # Unlike casualty copies, a Paradigm copy is *cast* — fire the
            # spell-cast event so cast triggers see it.
            game.trigger_manager.fire_event(
                game,
                SpellCastTriggeredEvent(
                    spell=copy_obj,
                    card=copy_obj.source,
                    controller=controller,
                    player=controller,
                ),
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
