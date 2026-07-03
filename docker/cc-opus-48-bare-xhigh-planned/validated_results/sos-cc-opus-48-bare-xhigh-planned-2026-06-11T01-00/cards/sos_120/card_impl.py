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
            "spells from among them without paying their mana costs.\n"
            "Paradigm (Then exile this spell. After you first resolve a spell "
            "with this name, you may cast a copy of it from exile without "
            "paying its mana cost at the beginning of each of your first main "
            "phases.)",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return

        exiled = self._exile_until_mv_4(game, controller)
        self._offer_free_casts(game, controller, exiled)

        # Paradigm setup happens only on the first (non-copy) resolution.
        if not getattr(self, "_is_paradigm_copy", False):
            # "Then exile this spell." — redirect this spell to exile instead
            # of the graveyard (card-local flag honored by _resolve_spell).
            self._exile_instead_of_graveyard = True
            self._register_paradigm(game, controller)

    def _exile_until_mv_4(self, game: "GameState", controller: Any) -> list:
        from engine.zones import move_to_zone

        library = controller.zones[Zone.LIBRARY]
        exiled: list = []
        total = 0
        while total < 4 and len(library) > 0:
            top = library.top(1)[0]
            move_to_zone(game, top, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top)
            cost = getattr(top, "mana_cost", None)
            total += cost.cmc if cost is not None else 0
        return exiled

    def _offer_free_casts(
        self, game: "GameState", controller: Any, exiled: list
    ) -> None:
        from engine.casting import cast_spell_free

        for card in exiled:
            # Lands aren't spells; non-castable cards stay exiled.
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            if not card.can_cast(game):
                continue
            try:
                if controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} from exile for free?"
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

        source = self  # the exiled Capstone that copies are made from

        def _condition(game: Any, event: Any) -> bool:
            return game.active_player is controller

        def _effect(game: "GameState") -> None:
            # Only while the original is still in exile.
            if not controller.zones[Zone.EXILE].contains(source):
                return
            try:
                if not controller.choose_yes_no(
                    "Cast a copy of Improvisation Capstone from exile for free?"
                ):
                    return
            except Exception:
                return
            original_so = StackObject(source=source, controller=controller, targets=[])
            copy_obj = copy_spell(game, original_so, controller)
            # The copy does the main effect but must not re-arm Paradigm.
            copy_obj.source._is_paradigm_copy = True
            game.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
