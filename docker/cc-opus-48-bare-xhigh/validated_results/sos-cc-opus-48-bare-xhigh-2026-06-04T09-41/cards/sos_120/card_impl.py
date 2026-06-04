"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Phase, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


_IMPULSE_THRESHOLD = 4


def _is_castable(card: Any) -> bool:
    """A card can be cast if it has a type and isn't (only) a land."""
    card_types = getattr(card, "card_types", set())
    return bool(card_types) and CardType.LAND not in card_types


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells from
    among them without paying their mana costs.

    Paradigm: then exile this spell; at the beginning of each of your first
    main phases you may cast a copy of it from exile for free.
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
            "Paradigm",
        )
        super().__init__(**kwargs)
        # Paradigm: this spell is exiled (not put in the graveyard) on resolve.
        self._exile_instead_of_graveyard = True
        self._paradigm_active = False

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return
        self._impulse_and_cast(game, controller)
        self._setup_paradigm(game, controller)

    # ------------------------------------------------------------------
    # Core effect
    # ------------------------------------------------------------------

    def _impulse_and_cast(self, game: "GameState", controller: "Player") -> None:
        exiled = self._impulse_exile(game, controller)
        self._offer_free_casts(game, controller, exiled)

    def _impulse_exile(self, game: "GameState", controller: "Player") -> list[Any]:
        library = controller.zones[Zone.LIBRARY]
        exile_zone = controller.zones[Zone.EXILE]
        exiled: list[Any] = []
        total = 0
        while total < _IMPULSE_THRESHOLD and len(library) > 0:
            top = library.top(1)[0]
            library.remove(top)
            if top.owner is None:
                top.owner = controller
            exile_zone.add(top)
            exiled.append(top)
            cost = getattr(top, "mana_cost", None)
            total += cost.cmc if cost is not None else 0
        return exiled

    def _offer_free_casts(
        self, game: "GameState", controller: "Player", exiled: list[Any]
    ) -> None:
        from engine.casting import CastingError, cast_spell_free

        candidates = [c for c in exiled if _is_castable(c)]
        while candidates:
            # Keep only spells that are still in exile (uncast).
            candidates = [
                c for c in candidates if controller.zones[Zone.EXILE].contains(c)
            ]
            if not candidates:
                return
            choice = controller.choose(
                candidates + [None],
                "choose a spell to cast for free (or stop)",
            )
            if choice is None or choice not in candidates:
                return
            candidates.remove(choice)
            try:
                cast_spell_free(game, controller, choice, Zone.EXILE)
            except CastingError:
                continue

    # ------------------------------------------------------------------
    # Paradigm — recurring free cast at each first main phase
    # ------------------------------------------------------------------

    def _setup_paradigm(self, game: "GameState", controller: "Player") -> None:
        if self._paradigm_active:
            return
        self._paradigm_active = True

        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: "GameState", event: Any) -> bool:
            ctrl = source.controller
            if ctrl is None or getattr(event, "player", None) is not ctrl:
                return False
            # "first main phase" = the precombat main phase.
            return g.phase == Phase.PRECOMBAT_MAIN

        def _effect(g: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            if not ctrl.choose_yes_no(
                "Cast a copy of Improvisation Capstone from exile for free?"
            ):
                return
            source._impulse_and_cast(g, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
