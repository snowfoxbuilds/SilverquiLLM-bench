"""Card implementation for Improvisation Capstone (SOS #120)."""

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
    this name, you may cast a copy of it from exile without paying its mana
    cost at the beginning of each of your first main phases.)

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

    def on_resolve(self, game: "GameState") -> None:
        """Main effect + Paradigm."""
        controller = self.controller
        if controller is None:
            return

        # --- Main effect: exile from top of library until total MV >= 4 ---
        library = game.get_library(controller)
        exile_zone = game.get_exile(controller)
        exiled_cards: list[Any] = []
        total_mv = 0

        while total_mv < 4 and len(library) > 0:
            top_card = library.top(1)[0]
            library.remove(top_card)
            if top_card.owner is None:
                top_card.owner = controller
            if top_card.controller is None:
                top_card.controller = controller
            exile_zone.add(top_card)
            exiled_cards.append(top_card)
            mc = getattr(top_card, "mana_cost", None)
            total_mv += mc.cmc if mc is not None else 0

        # --- You may cast any number of spells for free ---
        from engine.casting import cast_spell_free

        for card in list(exiled_cards):
            if not exile_zone.contains(card):
                continue
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            try:
                wants = controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} without paying its mana cost?"
                )
            except Exception:
                wants = False
            if wants:
                try:
                    cast_spell_free(game, controller, card, Zone.EXILE)
                except Exception:
                    pass

        # --- Paradigm: exile this spell instead of going to graveyard ---
        self._exile_on_resolve = True  # type: ignore[attr-defined]

        # --- Paradigm: first-time trigger registration ---
        _PARADIGM_FLAG = "_improvisation_capstone_paradigm"
        if not getattr(controller, _PARADIGM_FLAG, False):
            setattr(controller, _PARADIGM_FLAG, True)
            self._register_paradigm_trigger(game, controller)

    def _register_paradigm_trigger(
        self, game: "GameState", controller: Any
    ) -> None:
        """Register a recurring trigger: offer free copy at each precombat main."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration
        from engine.types import Phase

        sentinel: object = object()

        def _condition(g: "GameState", event: Any) -> bool:
            return (
                event.player is controller
                and event.phase == Phase.PRECOMBAT_MAIN
            )

        def _effect(g: "GameState") -> None:
            exile = g.get_exile(controller)
            has_ic = any(
                getattr(c, "name", "") == "Improvisation Capstone"
                for c in exile.get_all()
            )
            if not has_ic:
                return

            try:
                wants = controller.choose_yes_no(
                    "Cast a copy of Improvisation Capstone from exile without "
                    "paying its mana cost?"
                )
            except Exception:
                wants = False

            if not wants:
                return

            from engine.casting import cast_spell_free

            copy_card = ImprovisationCapstone(owner=controller, controller=controller)
            exile.add(copy_card)
            try:
                cast_spell_free(g, controller, copy_card, Zone.EXILE)
            except Exception:
                if exile.contains(copy_card):
                    exile.remove(copy_card)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=sentinel,
                controller=controller,
            )
        )
