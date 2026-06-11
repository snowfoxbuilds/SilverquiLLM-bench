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

        self._exile_and_cast(game, controller)

        # Paradigm setup happens once, on the original spell's first resolution
        # (copies skip it).
        if not getattr(self, "_is_paradigm_copy", False) and not getattr(
            self, "_paradigm_set_up", False
        ):
            self._setup_paradigm(game, controller)

    def _exile_and_cast(self, game: "GameState", controller: Any) -> None:
        """Exile from top of library until total MV >= 4; may free-cast them."""
        from engine.casting import cast_spell_free
        from engine.zones import move_to_zone

        library = controller.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top = library.top(1)[0]
            move_to_zone(game, top, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top)
            cost = getattr(top, "mana_cost", None)
            total_mv += cost.cmc if cost else 0

        # You may cast any number of (nonland) spells from among them for free.
        for card in exiled:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            if not card.can_cast(game):
                continue
            if controller.choose_yes_no(f"Cast {card.name} without paying its mana cost?"):
                try:
                    cast_spell_free(game, controller, card, Zone.EXILE)
                except Exception:
                    pass

    def _setup_paradigm(self, game: "GameState", controller: Any) -> None:
        """Exile this spell instead of the graveyard, then arm the recurring
        first-main-phase copy."""
        from engine.triggers import TriggerRegistration
        from engine.events import (
            BeginningOfPrecombatMainTriggeredEvent,
            SpellToGraveyardReplacementEvent,
        )
        from engine.replacement_effects import ReplacementEffect

        source = self
        self._paradigm_set_up = True

        # "Then exile this spell." — redirect this card's graveyard move to exile.
        def _cond_repl(g: Any, ev: Any) -> bool:
            return ev.card is source

        def _repl(g: Any, ev: Any) -> Any:
            ev.destination = "exile"
            g.replacement_manager.unregister(source)  # one-shot redirect
            return ev

        game.replacement_manager.register(ReplacementEffect(
            event_type=SpellToGraveyardReplacementEvent,
            source=source,
            condition=_cond_repl,
            replacement=_repl,
            controller=controller,
        ))

        # Recurring: at the beginning of each of your first (precombat) main
        # phases, you may cast a copy of this from exile for free.
        def _cond(g: Any, ev: Any) -> bool:
            return g.active_player is controller

        def _eff(g: "GameState") -> None:
            if not controller.zones[Zone.EXILE].contains(source):
                return
            if not controller.choose_yes_no(
                "Cast a copy of Improvisation Capstone from exile for free?"
            ):
                return
            from engine.casting import cast_spell_free

            spell_copy = _copy.copy(source)
            spell_copy._is_paradigm_copy = True
            spell_copy.controller = controller
            spell_copy.owner = controller
            for attr in ("chosen_targets", "colors_spent", "mana_spent"):
                if hasattr(spell_copy, attr):
                    try:
                        delattr(spell_copy, attr)
                    except Exception:
                        pass
            controller.zones[Zone.EXILE].add(spell_copy)
            try:
                cast_spell_free(g, controller, spell_copy, Zone.EXILE)
            except Exception:
                pass

        game.trigger_manager.register(TriggerRegistration(
            event_type=BeginningOfPrecombatMainTriggeredEvent,
            condition=_cond,
            effect=_eff,
            source=source,
            controller=controller,
        ))
