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
    total mana value 4 or greater.  You may cast any number of spells
    from among them without paying their mana costs.
    Paradigm (Then exile this spell. After you first resolve a spell
    with this name, you may cast a copy of it from exile without paying
    its mana cost at the beginning of each of your first main phases.)

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

    # ------------------------------------------------------------------
    # Paradigm helpers
    # ------------------------------------------------------------------

    def _register_exile_redirect(self, game: "GameState", card: Any) -> None:
        """One-shot replacement: *card* leaving the stack goes to exile."""
        from engine.events import MoveToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        sentinel = object()

        def _condition(g: Any, event: Any) -> bool:
            return event.card is card

        def _replacement(g: Any, event: Any) -> Any:
            event.destination = "exile"
            g.replacement_manager.unregister(sentinel)
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=sentinel,
                condition=_condition,
                replacement=_replacement,
                controller=self.controller,
            )
        )

    def _register_paradigm_trigger(self, game: "GameState") -> None:
        """Recurring: at the beginning of each of your first main phases,
        you may cast this from exile without paying its mana cost.

        Registered only on the *first* resolution of a spell with this
        name (per controller).  Deliberate simplification: the original
        card object is recast from exile (returning to exile afterwards)
        rather than a fresh copy — observable behavior is the same and no
        zombie copy objects accumulate.
        """
        from engine.casting import CastingError, cast_spell_free
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.triggers import TriggerRegistration

        controller = self.controller
        if controller is None:
            return

        registered: set[str] = getattr(controller, "_paradigm_registered", set())
        if self.name in registered:
            return
        registered.add(self.name)
        controller._paradigm_registered = registered

        source = self

        def _condition(g: Any, event: Any) -> bool:
            return g.active_player is controller

        def _effect(g: "GameState") -> None:
            owner = source.owner or controller
            if not owner.zones[Zone.EXILE].contains(source):
                return
            if not controller.choose_yes_no(
                f"Cast a copy of {source.name} from exile without paying "
                "its mana cost?"
            ):
                return
            try:
                cast_spell_free(g, controller, source, Zone.EXILE)
            except CastingError:
                return

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

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
            top_card = library.top(1)[0]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top_card)
            total_mv += getattr(top_card, "mana_cost", ManaCost()).cmc

        # 2. You may cast any number of spells from among them for free.
        #    Lands are not spells and stay exiled.
        for card in exiled:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            if controller.choose_yes_no(
                f"Cast {card.name} without paying its mana cost?"
            ):
                try:
                    cast_spell_free(game, controller, card, Zone.EXILE)
                except CastingError:
                    pass

        # 3. Paradigm: exile this spell instead of binning it, and set up
        #    the recurring first-main-phase recast on first resolution.
        self._register_exile_redirect(game, self)
        self._register_paradigm_trigger(game)
