"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with total
    mana value 4 or greater. You may cast any number of spells from among them
    without paying their mana costs.
    Paradigm (Then exile this spell. After you first resolve a spell with this
    name, you may cast a copy of it from exile without paying its mana cost at
    the beginning of each of your first main phases.)

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
            "spells from among them without paying their mana costs.\nParadigm",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return

        self._exile_and_cast(game, controller)

        # Paradigm — only the originally-cast spell (not its copies) exiles
        # itself and sets up the recurring copy trigger.
        if not getattr(self, "_paradigm_copy", False):
            self._resolve_to_zone = Zone.EXILE  # "Then exile this spell."
            self._register_paradigm(game, controller)

    # ------------------------------------------------------------------
    # Main effect
    # ------------------------------------------------------------------

    def _exile_and_cast(self, game: "GameState", controller: Any) -> None:
        from engine.casting import cast_spell_free
        from engine.zones import move_to_zone

        library = controller.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4:
            top = library.top(1)
            if not top:
                break  # library ran out before total MV 4.
            card = top[0]
            move_to_zone(game, card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(card)
            cost = getattr(card, "mana_cost", None)
            total_mv += cost.cmc if cost is not None else 0

        # You may cast any number of spells from among them, for free.
        for card in exiled:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue  # lands aren't spells — they stay exiled.
            try:
                if controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} for free from exile?"
                ):
                    cast_spell_free(game, controller, card, Zone.EXILE)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Paradigm
    # ------------------------------------------------------------------

    def _register_paradigm(self, game: "GameState", controller: Any) -> None:
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.stack import StackObject, copy_spell
        from engine.triggers import TriggerRegistration

        source = self

        def _cond(game: Any, event: Any) -> bool:
            # At the beginning of each of YOUR first main phases, while this
            # spell is still in exile.
            return game.active_player is controller and controller.zones[
                Zone.EXILE
            ].contains(source)

        def _eff(game: "GameState") -> None:
            try:
                if not controller.choose_yes_no(
                    "Cast a copy of Improvisation Capstone from exile?"
                ):
                    return
            except Exception:
                return
            # Cast a copy from exile (the original stays exiled). The copy is
            # flagged so it doesn't re-apply Paradigm.
            temp = StackObject(source=source, controller=controller, targets=[])
            copy_obj = copy_spell(game, temp, controller)
            copy_obj.source._paradigm_copy = True
            game.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_cond,
                effect=_eff,
                source=source,
                controller=controller,
            )
        )
