"""Card implementation for Improvisation Capstone (SOS 120)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


# Non-land card types that identify an object as a castable "spell".
_SPELL_TYPES = frozenset(
    {
        CardType.INSTANT,
        CardType.SORCERY,
        CardType.CREATURE,
        CardType.ENCHANTMENT,
        CardType.ARTIFACT,
        CardType.PLANESWALKER,
    }
)

_PARADIGM_REMINDER = (
    "Paradigm (Then exile this spell. After you first resolve a spell with "
    "this name, you may cast a copy of it from exile without paying its mana "
    "cost at the beginning of each of your first main phases.)"
)


def _mana_value(card: Any) -> int:
    """Return the mana value (cmc) of *card*, defaulting to 0."""
    cost = getattr(card, "mana_cost", None)
    if cost is None:
        return 0
    return int(getattr(cost, "cmc", 0) or 0)


def _is_spell(obj: Any) -> bool:
    """Return ``True`` if *obj* is a castable spell (not a land/player)."""
    if obj is None:
        return False
    if hasattr(obj, "life"):
        return False
    card_types = getattr(obj, "card_types", None)
    if not card_types:
        return False
    return bool(card_types & _SPELL_TYPES)


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
            + _PARADIGM_REMINDER,
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Paradigm: self-exile instead of graveyard
    # ------------------------------------------------------------------

    def register_replacement_effects(self, game: "GameState") -> None:
        """Paradigm: "Then exile this spell." — redirect this spell's
        stack->graveyard move to exile, using the sos_1 convention."""
        from engine.events import SpellToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        # Idempotent: only register the self-exile replacement once, so that
        # both the engine (on battlefield entry / explicit call) and our own
        # ``on_resolve`` can request it without stacking duplicates.
        if getattr(self, "_paradigm_exile_registered", False):
            return
        self._paradigm_exile_registered = True

        spell = self

        def _condition(g: Any, event: SpellToGraveyardReplacementEvent) -> bool:
            return event.spell is spell and event.destination == "graveyard"

        def _replacement(
            g: Any, event: SpellToGraveyardReplacementEvent
        ) -> SpellToGraveyardReplacementEvent:
            event.destination = "exile"
            return event

        controller = getattr(self, "controller", None) or getattr(self, "owner", None)
        game.replacement_manager.register(
            ReplacementEffect(
                event_type=SpellToGraveyardReplacementEvent,
                source=spell,
                condition=_condition,
                replacement=_replacement,
                controller=controller,
            )
        )

    # ------------------------------------------------------------------
    # Main resolution
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        controller = getattr(self, "controller", None) or getattr(self, "owner", None)
        if controller is None:
            return

        exiled = self._exile_until_total_mv(game, controller, threshold=4)
        self._offer_free_casts(game, controller, exiled)
        # Paradigm: ensure this spell exiles itself instead of hitting the
        # graveyard, and set up the recurring recast-from-exile trigger.
        self.register_replacement_effects(game)
        self._register_paradigm_recast(game, controller)

    def _exile_until_total_mv(
        self, game: "GameState", controller: Any, threshold: int
    ) -> list[Any]:
        """Exile cards off the top of *controller*'s library one at a time
        until their cumulative mana value reaches *threshold*. Returns the
        list of exiled cards."""
        library = game.get_library(controller)
        exile = game.get_exile(controller)
        exiled: list[Any] = []
        total = 0
        while total < threshold and len(library) > 0:
            # Top of library is the last element.
            top = library.get_all()[-1]
            library.remove(top)
            exile.add(top)
            exiled.append(top)
            total += _mana_value(top)
        return exiled

    def _offer_free_casts(
        self, game: "GameState", controller: Any, exiled: list[Any]
    ) -> None:
        """For each spell among *exiled*, ask the controller whether to cast
        it for free (no mana paid). Lands are not offered."""
        from engine.casting import cast_spell_free, CastingError
        from engine.types import Zone

        exile = game.get_exile(controller)
        for card in exiled:
            if not _is_spell(card):
                continue
            if not exile.contains(card):
                continue
            if not controller.choose_yes_no(
                f"Cast {getattr(card, 'name', 'spell')!r} for free from exile?"
            ):
                continue
            try:
                cast_spell_free(game, controller, card, Zone.EXILE)
            except CastingError:
                # Could not be cast — leave it in exile.
                continue

    # ------------------------------------------------------------------
    # Paradigm: recast a copy at the beginning of each first main phase
    # ------------------------------------------------------------------

    def _register_paradigm_recast(self, game: "GameState", controller: Any) -> None:
        """Register the recurring begin-of-(first)-main-phase trigger that
        lets the controller cast a copy of this spell from exile for free
        (sos_57 begin-of-main-phase convention)."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: Any, event: Any) -> bool:
            return getattr(event, "player", None) is controller

        def _effect(g: "GameState") -> None:
            _recast_copy_from_exile(g, source, controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )


def _recast_copy_from_exile(game: "GameState", source: Any, controller: Any) -> None:
    """Paradigm payoff: optionally cast a copy of *source* from exile without
    paying its mana cost. No-op if the source is not in exile or the player
    declines."""
    from engine.casting import cast_spell_free, CastingError
    from engine.types import Zone

    if controller is None:
        return
    exile = game.get_exile(controller)
    if not exile.contains(source):
        return
    if not controller.choose_yes_no(
        "Cast a copy of Improvisation Capstone from exile for free?"
    ):
        return
    try:
        cast_spell_free(game, controller, source, Zone.EXILE)
    except CastingError:
        return
