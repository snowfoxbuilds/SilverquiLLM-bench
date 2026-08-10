"""Zone containers for managing game objects across game zones."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.types import CardType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class IllegalMoveError(Exception):
    """Raised when a zone move is illegal (e.g. object not found in source zone)."""


class ZoneContainer:
    """Wraps an ordered list of game-object references for a single zone.

    Internal list convention: index 0 is the *bottom*, index -1 is the *top*.
    This matches the intuitive model where ``add(obj, position="top")``
    appends, and ``top(n)`` returns the last *n* items.
    """

    def __init__(self) -> None:
        self._objects: list[Any] = []

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def add(self, obj: Any, position: str = "top") -> None:
        """Add *obj* to this zone.

        Parameters:
            obj: The game object to add.
            position: ``"top"`` (default) appends to the end of the internal
                list; ``"bottom"`` inserts at position 0.
        """
        if position == "top":
            self._objects.append(obj)
        elif position == "bottom":
            self._objects.insert(0, obj)
        else:
            raise ValueError(f"Invalid position: {position!r}; expected 'top' or 'bottom'")

    def remove(self, obj: Any) -> None:
        """Remove *obj* from this zone (identity-based lookup).

        Raises:
            ValueError: If *obj* is not in the zone.
        """
        for i, item in enumerate(self._objects):
            if item is obj:
                del self._objects[i]
                return
        raise ValueError(f"{obj!r} not in zone")

    def shuffle(self) -> None:
        """Randomly shuffle the contents of this zone (used for libraries)."""
        random.shuffle(self._objects)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def contains(self, obj: Any) -> bool:
        """Return ``True`` if *obj* is in this zone (identity-based lookup)."""
        return any(item is obj for item in self._objects)

    def get_all(self) -> list[Any]:
        """Return a shallow copy of all objects in order (bottom → top)."""
        return list(self._objects)

    def top(self, n: int) -> list[Any]:
        """Return the top *n* items (last *n* in the internal list).

        If *n* >= len, returns all items.  Order is bottom-to-top (same
        orientation as the internal list).
        """
        if n <= 0:
            return []
        return self._objects[-n:]

    def bottom(self, n: int) -> list[Any]:
        """Return the bottom *n* items (first *n* in the internal list).

        If *n* >= len, returns all items.
        """
        if n <= 0:
            return []
        return self._objects[:n]

    def __len__(self) -> int:
        return len(self._objects)

    def __repr__(self) -> str:
        return f"ZoneContainer({self._objects!r})"


class Zones:
    """Per-player collection mapping each :class:`Zone` to a :class:`ZoneContainer`."""

    def __init__(self, zones: dict[Zone, ZoneContainer]) -> None:
        self._zones = zones

    @classmethod
    def new_player(cls) -> Zones:
        """Create a fresh set of empty zones for a player."""
        return cls({zone: ZoneContainer() for zone in Zone})

    def __getitem__(self, zone: Zone) -> ZoneContainer:
        return self._zones[zone]

    def __contains__(self, zone: Zone) -> bool:
        return zone in self._zones

    def __repr__(self) -> str:
        return f"Zones({self._zones!r})"


def move_zone(
    obj: Any,
    from_zone: ZoneContainer,
    to_zone: ZoneContainer,
    position: str = "top",
) -> None:
    """Move *obj* from *from_zone* to *to_zone*.

    Parameters:
        obj: The game object to move.
        from_zone: Source :class:`ZoneContainer`.
        to_zone: Destination :class:`ZoneContainer`.
        position: ``"top"`` (default), ``"bottom"``, or ``"shuffle"``
            (add then shuffle the destination).

    Raises:
        IllegalMoveError: If *obj* is not in *from_zone*.
    """
    # Moving an object to the same zone it's already in is a no-op.
    if from_zone is to_zone:
        return

    if not from_zone.contains(obj):
        raise IllegalMoveError(
            f"Object {obj!r} not found in source zone"
        )

    # Validate position *before* mutating either zone so that an invalid
    # position does not leave the object removed from the source without
    # being added to the destination.
    if position not in ("top", "bottom", "shuffle"):
        raise ValueError(f"Invalid position: {position!r}; expected 'top', 'bottom', or 'shuffle'")

    from_zone.remove(obj)

    # Clear transient casting metadata when a card changes zones so that
    # stale data (e.g. colors_spent from a previous cast) does not leak.
    if hasattr(obj, "colors_spent"):
        del obj.colors_spent

    if position == "shuffle":
        to_zone.add(obj, position="top")
        to_zone.shuffle()
    else:
        to_zone.add(obj, position=position)


# Mapping from replacement-effect destination strings to Zone enum values.
_DESTINATION_ZONE_MAP: dict[str, Zone] = {
    "graveyard": Zone.GRAVEYARD,
    "exile": Zone.EXILE,
    "hand": Zone.HAND,
    "library": Zone.LIBRARY,
}


def move_to_zone(
    game: GameState,
    card: Any,
    from_zone: Zone,
    to_zone: Zone,
    *,
    replacement_event: Any | None = None,
) -> None:
    """High-level zone transition with trigger/replacement-effect hooks.

    Centralises the bookkeeping that was previously duplicated across
    ``destroy()``, ``sacrifice()``, ``exile()``, ``create_token()``,
    ``_move_to_graveyard()`` (SBAs), and ``_resolve_spell()`` (casting).

    Steps:
    1. Consult replacement effects for zone-change redirection (if
       *replacement_event* is supplied and the card is leaving the
       battlefield).  The replacement may change the destination zone
       (e.g. exile instead of graveyard) or set ``prevented = True`` to
       signal that it handled the zone move directly.
    2. Remove *card* from the source zone.
    3. Add *card* to the (possibly redirected) destination zone.
    4. If leaving the battlefield:
       a. Fire ``LeavesBattlefieldTriggeredEvent``.
       b. Fire ``CreatureDiesTriggeredEvent`` if the card is a creature
          **and** the final destination is the graveyard.
       c. Unregister triggers and replacement effects (fires happen
          **before** unregister so self-referencing triggers still match).
    5. If entering the battlefield:
       a. Register triggers (``register_triggers``) and replacement
          effects (``register_replacement_effects``).
       b. Fire ``EntersBattlefieldTriggeredEvent``.

    Parameters:
        game: The current game state.
        card: The game object being moved.
        from_zone: The :class:`Zone` the card is currently in.
        to_zone: The intended destination :class:`Zone`.
        replacement_event: Optional typed replacement-event object
            (e.g. ``CreatureDiesReplacementEvent``).  When ``None``,
            no replacement effects are consulted (useful for simple
            moves like casting resolution or exile-from-graveyard).
    """
    from engine.events import (
        CreatureDiesTriggeredEvent,
        EntersBattlefieldTriggeredEvent,
        LeavesBattlefieldTriggeredEvent,
    )

    controller = getattr(card, "controller", None)
    owner = getattr(card, "owner", controller)

    leaving_battlefield = from_zone == Zone.BATTLEFIELD
    entering_battlefield = to_zone == Zone.BATTLEFIELD

    # --- Determine the source player for zone lookup ---
    # When leaving the battlefield, use the controller's zone.
    # For other zones (hand, graveyard, etc.), use the owner's zone.
    if leaving_battlefield:
        source_player = controller
    else:
        source_player = owner

    # Fallback: search all players for the zone containing the card.
    # Also triggered when the inferred player's zone doesn't contain the card
    # (e.g. discarding a card that's in a different player's hand than its owner).
    if source_player is None or not source_player.zones[from_zone].contains(card):
        for player in game.players:
            if player.zones[from_zone].contains(card):
                source_player = player
                break

    if source_player is None:
        return  # Card not found anywhere

    source_container = source_player.zones[from_zone]
    if not source_container.contains(card):
        return  # Safety: card not in any player's zone

    if owner is None:
        owner = source_player

    # --- Replacement effects (zone-change redirection) ---
    dest_zone = to_zone
    if replacement_event is not None and leaving_battlefield:
        replacement_event = game.replacement_manager.apply(game, replacement_event)
        if getattr(replacement_event, "prevented", False):
            return
        destination_str = getattr(replacement_event, "destination", "graveyard")
        dest_zone = _DESTINATION_ZONE_MAP.get(destination_str, to_zone)

    # --- Perform the zone move ---
    source_container.remove(card)

    # Determine the destination player (always the owner for graveyard/exile/hand/library).
    if entering_battlefield:
        dest_player = controller if controller is not None else owner
    else:
        dest_player = owner

    dest_player.zones[dest_zone].add(card)

    # A zone change yields a new object: break instance-id continuity in the
    # refs registry even when the new stint is never observed by a query
    # (e.g. a flicker's exile leg). Minting stays lazy — the registry
    # re-mints on the next observation.
    game.refs.note_zone_change(card)

    # --- Leaving battlefield hooks ---
    removed_source_effects = False
    if leaving_battlefield:
        card_types = getattr(card, "card_types", set())
        is_creature = CardType.CREATURE in card_types

        # Fire events BEFORE unregistering (KEY_DECISIONS convention).
        game.trigger_manager.fire_event(
            game,
            LeavesBattlefieldTriggeredEvent(permanent=card, controller=controller),
        )
        if is_creature and dest_zone == Zone.GRAVEYARD:
            game.trigger_manager.fire_event(
                game,
                CreatureDiesTriggeredEvent(creature=card, controller=controller, owner=owner),
            )

        # Now unregister triggers and replacement effects.
        game.trigger_manager.unregister(card)
        game.replacement_manager.unregister(card)

        # An Equipment that itself leaves the battlefield detaches: clear
        # attached_to, clear its internal effect references, and run its detach
        # hook exactly once (rule 704.5q keeps it attached only while both are
        # on the battlefield). This leaves no stale attachment state in the
        # graveyard/hand/exile/stack copy, so the Equipment can be equipped
        # again after it is bounced, blinked, destroyed, or replayed. The
        # equipped-creature-leaves case is handled separately by the attachment
        # SBA, which detaches while the Equipment stays on the battlefield.
        if getattr(card, "is_equipment", False) and getattr(card, "attached_to", None) is not None:
            detach = getattr(card, "detach", None)
            if callable(detach):
                detach(game)
                removed_source_effects = True

        # A permanent that leaves the battlefield stops producing its
        # continuous effects immediately (rule 603/611) — remove every effect
        # this card sources so a lord/anthem's buff vanishes without waiting
        # for the next turn-boundary cleanup. Mirrors the replay executor's
        # per-card cleanup so the executor can rely on the engine. (For an
        # Equipment the detach above already removed its buff effects; this
        # sweep catches any other effect the card still sources.)
        effect_manager = getattr(game, "effect_manager", None)
        if effect_manager is not None:
            for effect in effect_manager.get_effects_by_source(card):
                effect_manager.remove(effect)
                removed_source_effects = True

    # --- Entering battlefield hooks ---
    if entering_battlefield:
        # Register the card's own triggers/replacement effects *before* firing
        # the ENTERS_BATTLEFIELD event, so a permanent's own enters-trigger
        # fires on its own entry (rule 603.3a — a permanent's own
        # enters-the-battlefield ability triggers when that permanent enters).
        # An "another …"-style ability must exclude the source in its own
        # condition filter (the card-text responsibility), not rely on the
        # engine suppressing the whole event — see the Phase F subscriber audit.
        if hasattr(card, "register_triggers"):
            card.register_triggers(game)
        if hasattr(card, "register_replacement_effects"):
            card.register_replacement_effects(game)
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(
                permanent=card,
                controller=controller if controller is not None else owner,
            ),
        )

    # --- Re-derive continuous effects on any battlefield change ---
    # A lord/anthem entering mid-turn buffs the team now; a departed source's
    # effect stops applying now — not only at the next cleanup step. apply_all
    # is idempotent (reset-then-reapply). The fast-path skips the common
    # no-effects case for cheap zone churn, but a removal that empties the
    # manager still needs one reset pass to strip the departed buff.
    if leaving_battlefield or entering_battlefield:
        effect_manager = getattr(game, "effect_manager", None)
        if effect_manager is not None and (
            len(effect_manager) > 0 or removed_source_effects
        ):
            effect_manager.apply_all(game)


# Destination string → Zone for replacement-effect zone redirection.
_DESTINATION_ZONE_MAP: dict[str, Zone] = {
    "graveyard": Zone.GRAVEYARD,
    "exile": Zone.EXILE,
    "hand": Zone.HAND,
    "library": Zone.LIBRARY,
}
