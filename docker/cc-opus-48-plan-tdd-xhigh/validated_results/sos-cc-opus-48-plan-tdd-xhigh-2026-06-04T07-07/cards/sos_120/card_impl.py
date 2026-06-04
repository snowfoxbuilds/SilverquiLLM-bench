"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_MV_THRESHOLD = 4


def _card_mv(card: Any) -> int:
    mc = getattr(card, "mana_cost", None)
    if mc is None:
        return 0
    return getattr(mc, "cmc", 0)


def _is_castable_spell(card: Any) -> bool:
    """A card can be cast as a spell iff it is not a land."""
    types = getattr(card, "card_types", set())
    if not types:
        return False
    return CardType.LAND not in types


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with total
    mana value 4 or greater.  You may cast any number of spells from among them
    without paying their mana costs.
    Paradigm (Then exile this spell.  After you first resolve a spell with this
    name, you may cast a copy of it from exile without paying its mana cost at
    the beginning of each of your first main phases.)

    SOS collector number 120.

    On resolution the spell exiles the top of the controller's library until the
    accumulated mana value reaches 4, then offers a free cast (via
    ``cast_spell_free``) of each non-land exiled card.  Paradigm is modeled by
    redirecting this very spell to exile on resolution (a one-shot
    ``SpellToGraveyardReplacementEvent`` replacement, mirroring SOS 1) and, on
    the controller's first resolution, registering a repeating precombat
    main-phase trigger that offers to cast a free copy of the card from exile.
    A cast copy ceases to exist instead of reaching a public zone.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Lesson"}
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
        self._is_paradigm_copy: bool = False

    def on_resolve(self, game: "GameState") -> None:
        controller = getattr(self, "controller", None)
        if controller is None:
            return

        self._exile_and_offer_casts(game, controller)

        if self._is_paradigm_copy:
            # A cast copy ceases to exist rather than reaching a public zone.
            self._register_cease_to_exist(game)
            return

        # Paradigm: exile this spell instead of putting it in the graveyard,
        # and (on first resolution) set up the recurring copy cast.
        self._register_self_exile(game)
        self._register_paradigm_trigger(game, controller)

    # ------------------------------------------------------------------
    # Core effect
    # ------------------------------------------------------------------

    def _exile_and_offer_casts(self, game: "GameState", controller: Any) -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.zones import move_to_zone

        library = controller.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < _MV_THRESHOLD:
            top = library.top(1)
            if not top:
                break  # library ran out before reaching the threshold
            card = top[0]
            move_to_zone(game, card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(card)
            total_mv += _card_mv(card)

        for card in exiled:
            if not _is_castable_spell(card):
                continue
            if not controller.zones[Zone.EXILE].contains(card):
                continue
            if not controller.choose_yes_no(
                f"Cast {getattr(card, 'name', 'card')} for free?"
            ):
                continue
            try:
                cast_spell_free(game, controller, card, Zone.EXILE)
            except CastingError:
                continue

    # ------------------------------------------------------------------
    # Paradigm plumbing
    # ------------------------------------------------------------------

    def _register_self_exile(self, game: "GameState") -> None:
        from engine.events import SpellToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        source = self
        marker = type(
            "CapstoneSelfExile", (), {"name": "Improvisation Capstone self-exile"}
        )()

        def _condition(game: Any, event: Any) -> bool:
            return getattr(event, "spell", None) is source

        def _replacement(game: Any, event: Any) -> Any:
            event.destination = "exile"
            game.replacement_manager.unregister(marker)
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=SpellToGraveyardReplacementEvent,
                source=marker,
                condition=_condition,
                replacement=_replacement,
                controller=getattr(self, "controller", None),
            )
        )

    def _register_cease_to_exist(self, game: "GameState") -> None:
        from engine.events import SpellToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        source = self
        marker = type(
            "CapstoneCopyCease", (), {"name": "Improvisation Capstone copy cease"}
        )()

        def _condition(game: Any, event: Any) -> bool:
            return getattr(event, "spell", None) is source

        def _replacement(game: Any, event: Any) -> Any:
            event.prevented = True
            game.replacement_manager.unregister(marker)
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=SpellToGraveyardReplacementEvent,
                source=marker,
                condition=_condition,
                replacement=_replacement,
                controller=getattr(self, "controller", None),
            )
        )

    def _register_paradigm_trigger(self, game: "GameState", controller: Any) -> None:
        # "After you first resolve a spell with this name" — register once.
        if getattr(controller, "_improv_capstone_paradigm", False):
            return
        controller._improv_capstone_paradigm = True

        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            return (
                getattr(event, "player", None) is ctrl
                and getattr(event, "is_precombat", False)
            )

        def _effect(game: "GameState") -> None:
            from engine.casting import CastingError, cast_spell_free

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            if not ctrl.zones[Zone.EXILE].contains(source):
                return
            if not ctrl.choose_yes_no(
                "Cast a copy of Improvisation Capstone from exile for free?"
            ):
                return
            copy = source._make_paradigm_copy()
            ctrl.zones[Zone.EXILE].add(copy)
            try:
                cast_spell_free(game, ctrl, copy, Zone.EXILE)
            except CastingError:
                if ctrl.zones[Zone.EXILE].contains(copy):
                    ctrl.zones[Zone.EXILE].remove(copy)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def _make_paradigm_copy(self) -> "ImprovisationCapstone":
        copy = ImprovisationCapstone(owner=self.owner, controller=self.controller)
        copy._is_paradigm_copy = True
        return copy
