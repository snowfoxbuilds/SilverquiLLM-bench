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
        self._paradigm_active: bool = False

    def on_resolve(self, game: GameState) -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # Exile from the top of the library until total mana value >= 4
        # (or the library runs out).
        library = game.get_library(controller)
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top_card = library.get_all()[-1]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top_card)
            total_mv += getattr(top_card, "mana_cost", ManaCost()).cmc

        # Offer to cast any number of them for free.  Lands cannot be
        # cast and stay exiled (mirrors fdn_194 Etali).
        castable = [
            c for c in exiled
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

        # Paradigm setup — only on the first resolution of this card.
        if not self._paradigm_active:
            self._paradigm_active = True
            self._register_paradigm(game, controller)

    def _register_paradigm(self, game: GameState, controller: Any) -> None:
        """Exile this spell instead of binning it; recast each of your
        first main phases.

        Modeled as the exiled card itself being recast from exile each
        time (observably equivalent to "cast a copy from exile": the card
        is back in exile after each resolution).
        """
        from engine.casting import CastingError, cast_spell_free
        from engine.events import (
            BeginningOfPrecombatMainTriggeredEvent,
            SpellToGraveyardReplacementEvent,
        )
        from engine.replacement_effects import ReplacementEffect
        from engine.triggers import TriggerRegistration

        source = self

        # Permanent redirect: whenever this spell would go from the stack
        # to the graveyard, it goes to exile instead ("Then exile this
        # spell", and after every Paradigm recast).
        def _to_exile(g: GameState, event: Any) -> Any:
            event.destination = "exile"
            return event

        game.replacement_manager.register(ReplacementEffect(
            event_type=SpellToGraveyardReplacementEvent,
            source=source,
            condition=lambda g, e: getattr(e, "card", None) is source,
            replacement=_to_exile,
            controller=controller,
        ))

        # Recurring: at the beginning of each of your first main phases,
        # you may cast it from exile for free.
        def _condition(g: GameState, event: Any) -> bool:
            return (
                g.active_player is controller
                and g.get_exile(controller).contains(source)
            )

        def _effect(g: GameState) -> None:
            if not g.get_exile(controller).contains(source):
                return
            if not controller.choose_yes_no(
                f"Cast {source.name} from exile without paying its mana cost?"
            ):
                return
            try:
                cast_spell_free(g, controller, source, Zone.EXILE)
            except CastingError:
                pass

        game.trigger_manager.register(TriggerRegistration(
            event_type=BeginningOfPrecombatMainTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=source,
            controller=controller,
        ))
