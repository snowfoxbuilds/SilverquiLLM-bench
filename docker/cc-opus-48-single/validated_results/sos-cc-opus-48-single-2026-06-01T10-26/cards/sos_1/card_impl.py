"""Card implementation for The Dawning Archaic (SOS 1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


# Card types that count toward The Dawning Archaic's cost reduction.
_INSTANT_OR_SORCERY = frozenset({CardType.INSTANT, CardType.SORCERY})


def _is_instant_or_sorcery(card: Any) -> bool:
    """Return ``True`` if *card* is an instant or sorcery card."""
    return bool(getattr(card, "card_types", set()) & _INSTANT_OR_SORCERY)


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost.  If that
    spell would be put into your graveyard, exile it instead.

    SOS collector number 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery "
            "card in your graveyard.\nReach\nWhenever The Dawning Archaic "
            "attacks, you may cast target instant or sorcery card from your "
            "graveyard without paying its mana cost. If that spell would be "
            "put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Cost reduction
    # ------------------------------------------------------------------

    def cost_reduction(self, game: GameState) -> int:
        """Return {1} per instant/sorcery card in the controller's graveyard.

        Reports the raw per-card count; ``engine.casting.get_cost_reduction``
        clamps it to the printed generic at payment time.
        """
        controller = getattr(self, "controller", None) or getattr(self, "owner", None)
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        return sum(1 for card in graveyard.get_all() if _is_instant_or_sorcery(card))

    # ------------------------------------------------------------------
    # Attack trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        """Register the 'whenever ~ attacks' free-cast-from-graveyard trigger."""
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: AttacksTriggeredEvent) -> bool:
            return event.creature is source

        def _effect(game: GameState) -> None:
            _cast_from_graveyard(game, source)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )


def _cast_from_graveyard(game: GameState, source: Any) -> None:
    """Resolve the attack trigger: optionally free-cast a graveyard spell.

    Contract exposed for the deterministic test pipeline:

    * ``controller.choose_yes_no`` is asked first (the "you may" clause).
      Script ``True`` to cast, ``False`` to decline.
    * If casting, ``controller.choose_card`` selects the target instant or
      sorcery from the controller's graveyard.
    * The chosen spell is cast for free via
      :func:`engine.casting.cast_spell_free` from the graveyard, and is
      flagged (``card._exile_if_goes_to_graveyard = True``) so the engine
      exiles it instead of putting it into the graveyard on resolution —
      registered through the replacement-effect machinery.
    """
    from engine.casting import cast_spell_free, CastingError
    from engine.types import Zone

    controller = getattr(source, "controller", None)
    if controller is None:
        return

    graveyard = game.get_graveyard(controller)
    candidates = [c for c in graveyard.get_all() if _is_instant_or_sorcery(c)]
    if not candidates:
        return

    # "you may" — ask whether to use the ability.
    if not controller.choose_yes_no(
        "Cast an instant or sorcery from your graveyard for free?"
    ):
        return

    target = controller.choose_card(
        candidates, "target instant or sorcery card in your graveyard"
    )
    if target is None or not graveyard.contains(target):
        return

    # Register the "exile instead of graveyard" replacement for this spell
    # before casting it, using the engine's replacement-effect machinery.
    _register_exile_replacement(game, target, controller)

    try:
        cast_spell_free(game, controller, target, Zone.GRAVEYARD)
    except CastingError:
        # Could not be cast (e.g. illegal target choices) — clean up the
        # replacement so it does not linger.
        game.replacement_manager.unregister(target)
        if hasattr(target, "_exile_if_goes_to_graveyard"):
            del target._exile_if_goes_to_graveyard


def _register_exile_replacement(game: GameState, spell: Any, controller: Any) -> None:
    """Register a replacement: if *spell* would go to a graveyard, exile it.

    Uses ``engine.replacement_effects.ReplacementEffect`` keyed to the
    spell as source.  The replacement self-unregisters after firing once.
    """
    from engine.events import SpellToGraveyardReplacementEvent
    from engine.replacement_effects import ReplacementEffect

    spell._exile_if_goes_to_graveyard = True

    def _condition(game: Any, event: SpellToGraveyardReplacementEvent) -> bool:
        return event.spell is spell and event.destination == "graveyard"

    def _replacement(
        game: Any, event: SpellToGraveyardReplacementEvent
    ) -> SpellToGraveyardReplacementEvent:
        event.destination = "exile"
        return event

    game.replacement_manager.register(
        ReplacementEffect(
            event_type=SpellToGraveyardReplacementEvent,
            source=spell,
            condition=_condition,
            replacement=_replacement,
            controller=controller,
        )
    )
