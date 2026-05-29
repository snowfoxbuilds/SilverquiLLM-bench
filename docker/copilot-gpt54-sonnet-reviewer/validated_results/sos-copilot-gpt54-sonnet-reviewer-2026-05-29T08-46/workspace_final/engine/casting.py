"""Casting and resolution pipeline for spells and lands.

Provides the full flow from casting a spell or playing a land through
resolution:

- :func:`cast_spell` — verify timing & legality → move hand to stack →
  choose targets → pay costs → call ``on_cast`` → push :class:`StackObject`.
- :func:`play_land` — verify land play remaining → move hand to
  battlefield → decrement ``land_plays_remaining``.
- :func:`is_sorcery_speed` / :func:`can_cast_at_instant_speed` — timing
  helpers used by the casting pipeline.

Resolution is embedded in the :class:`StackObject` ``on_resolve`` callback
created by :func:`cast_spell`:

- Call ``card.on_resolve(game)``.
- Permanents (creature / enchantment / artifact / planeswalker) move from
  the stack to the battlefield.
- Non-permanents (instant / sorcery) move to the graveyard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import CardImpl
from engine.events import MoveToGraveyardReplacementEvent
from engine.stack import StackObject, copy_spell
from engine.types import CardType, Keyword, ManaCost, Phase, Zone
from engine.zones import move_zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


# Card types that represent permanents — these go to the battlefield on resolve.
_PERMANENT_TYPES: frozenset[CardType] = frozenset({
    CardType.CREATURE,
    CardType.ENCHANTMENT,
    CardType.ARTIFACT,
    CardType.PLANESWALKER,
})


class CastingError(Exception):
    """Raised when a spell cast or land play is illegal."""


# ------------------------------------------------------------------
# Timing helpers
# ------------------------------------------------------------------

def is_sorcery_speed(game: GameState, player: Player) -> bool:
    """Return ``True`` if sorcery-speed timing is met for *player*.

    Sorcery speed requires all of:

    * *player* is the active player.
    * The current phase is a main phase (``PRECOMBAT_MAIN`` or
      ``POSTCOMBAT_MAIN``).
    * The stack is empty.
    """
    if player is not game.active_player:
        return False
    if game.phase not in (Phase.PRECOMBAT_MAIN, Phase.POSTCOMBAT_MAIN):
        return False
    if not game.stack.is_empty():
        return False
    return True


def can_cast_at_instant_speed(card: CardImpl) -> bool:
    """Return ``True`` if *card* may be cast at instant speed.

    A card has instant-speed timing if it is an instant or has the
    :attr:`~engine.types.Keyword.FLASH` keyword.
    """
    if CardType.INSTANT in card.card_types:
        return True
    if Keyword.FLASH & card.keywords:
        return True
    return False


# ------------------------------------------------------------------
# Cost reduction
# ------------------------------------------------------------------

def get_cost_reduction(game: GameState, card: CardImpl, controller: Player) -> int:
    """Return the generic mana reduction for casting *card*.

    Queries ``card.cost_reduction(game)`` and clamps the result so that
    the generic portion of the mana cost cannot go below 0.

    This is a simplified single-card self-reduction model.  Full MTG
    cost-reduction interactions (Trinisphere, multiple reductions from
    different sources) are deferred.
    """
    # Ensure card.controller is set so the hook can reference "you" / the
    # casting player even when the card was never explicitly assigned one.
    prev_controller = card.controller
    card.controller = controller
    raw = card.cost_reduction(game)
    # Restore previous controller in case the caller doesn't want a
    # side-effect (get_cost_reduction is a query, not a mutation).
    card.controller = prev_controller
    raw += _get_granted_cost_reduction(game, controller, card)
    generic = card.mana_cost.generic if card.mana_cost else 0
    return max(0, min(raw, generic))


def _apply_cost_reduction(cost: ManaCost, reduction: int) -> ManaCost:
    """Return a new :class:`ManaCost` with *reduction* subtracted from generic."""
    new_generic = max(0, cost.generic - reduction)
    return ManaCost(
        generic=new_generic,
        pips=dict(cost.pips),
        x_count=cost.x_count,
        hybrid=list(cost.hybrid),
    )


def _get_granted_cost_reduction(
    game: GameState,
    player: Player,
    card: CardImpl,
) -> int:
    """Return the total generic mana reduction granted to *card* on the battlefield."""
    granted_reduction = 0
    for permanent in game.get_battlefield(player).get_all():
        get_granted_cost_reduction = getattr(
            permanent,
            "get_granted_cost_reduction",
            None,
        )
        if get_granted_cost_reduction is None:
            continue
        reduction = get_granted_cost_reduction(game, card)
        if reduction is None:
            continue
        granted_reduction += int(reduction)
    return granted_reduction


def _get_granted_casualty_value(
    game: GameState,
    player: Player,
    card: CardImpl,
) -> int:
    """Return the highest casualty value granted to *card* on the battlefield."""
    granted_value = 0
    for permanent in game.get_battlefield(player).get_all():
        get_granted_casualty_value = getattr(
            permanent,
            "get_granted_casualty_value",
            None,
        )
        if get_granted_casualty_value is None:
            continue
        value = get_granted_casualty_value(game, card)
        if value is None:
            continue
        granted_value = max(granted_value, int(value))
    return granted_value


def _get_legal_targets_for_requirement(
    game: GameState,
    requirement: Any,
) -> list[Any]:
    """Return currently legal targets for *requirement*.

    The current engine only needs battlefield-target support for the shipped
    tests. Players are also considered legal targets when the filter allows it.
    """
    legal_targets: list[Any] = []
    filter_fn = getattr(requirement, "filter_fn", None)
    if filter_fn is None:
        return legal_targets

    zone = getattr(requirement, "zone", None)
    if zone == Zone.BATTLEFIELD:
        for current_player in game.players:
            for obj in game.get_battlefield(current_player).get_all():
                if filter_fn(obj):
                    legal_targets.append(obj)

    for current_player in game.players:
        if filter_fn(current_player):
            legal_targets.append(current_player)

    return legal_targets


def _choose_casualty_copy_targets(
    game: GameState,
    player: Player,
    stack_obj: StackObject,
) -> list[Any] | None:
    """Let *player* optionally choose new targets for a casualty copy."""
    if not stack_obj.targets:
        return None

    if not player.choose_yes_no(
        f"Choose new targets for copy of {getattr(stack_obj.source, 'name', 'that spell')}?"
    ):
        return None

    requirements = getattr(stack_obj.source, "get_targets", lambda _game: [])(game)
    new_targets: list[Any] = []
    for requirement in requirements:
        legal_targets = _get_legal_targets_for_requirement(game, requirement)
        if not legal_targets:
            return None
        new_targets.append(player.choose_target(legal_targets, requirement))
    return new_targets


def _apply_granted_casualty(
    game: GameState,
    player: Player,
    card: CardImpl,
    stack_obj: StackObject,
) -> None:
    """Apply any battlefield-granted casualty to *card* as it is cast."""
    casualty_value = _get_granted_casualty_value(game, player, card)
    if casualty_value <= 0:
        return

    legal_creatures = [
        permanent
        for permanent in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(permanent, "card_types", set())
        and getattr(permanent, "power", 0) >= casualty_value
    ]
    if not legal_creatures:
        return

    if not player.choose_yes_no(
        f"Sacrifice a creature with power {casualty_value} or greater for casualty {casualty_value}?"
    ):
        return

    chosen_creature = player.choose_card(
        legal_creatures,
        f"creature to sacrifice for casualty {casualty_value}",
    )
    if chosen_creature not in legal_creatures:
        return
    if not game.get_battlefield(player).contains(chosen_creature):
        return

    from engine.game import sacrifice

    sacrifice(game, player, chosen_creature)
    new_targets = _choose_casualty_copy_targets(game, player, stack_obj)
    game.stack.push(copy_spell(game, stack_obj, player, new_targets))


# ------------------------------------------------------------------
# Cast spell
# ------------------------------------------------------------------

def cast_spell(game: GameState, player: Player, card: CardImpl) -> None:
    """Cast *card* from *player*'s hand.

    Pipeline
    --------
    1. **Timing check** — instants (and cards with flash) can be cast
       whenever the player has priority; everything else requires
       sorcery-speed timing.
    2. **can_cast** — ask the card whether it can legally be cast.
    3. **Hand check** — the card must be in the player's hand.
    4. **Move hand → stack zone** — remove the card from the hand and
       place it into the player's stack zone.
    5. **Choose targets** — if the card specifies targets (via
       :meth:`CardImpl.get_targets`), the player is asked to choose.
    6. **Mana check / payment** — the player's mana pool must be able to
       pay the card's mana cost.  If payment fails, the card is rolled
       back from the stack zone to the hand.
    7. **Call on_cast** — invoke the card's ``on_cast`` hook.
    8. **Push StackObject** — push a :class:`StackObject` whose
       ``on_resolve`` callback handles resolution.

    Raises:
        CastingError: If any legality check fails.
    """
    cast_spell_with_options(game, player, card)


def cast_spell_with_options(
    game: GameState,
    player: Player,
    card: CardImpl,
    *,
    alternative_cost: ManaCost | None = None,
    ignore_timing: bool = False,
) -> None:
    """Cast *card* from hand with optional timing and cost overrides."""
    # 1. Timing
    if (
        not ignore_timing
        and not can_cast_at_instant_speed(card)
        and not is_sorcery_speed(game, player)
    ):
        raise CastingError(
            f"Cannot cast {card.name!r} — sorcery-speed timing not met"
        )

    # 2. can_cast
    if not card.can_cast(game):
        raise CastingError(f"Cannot cast {card.name!r} — can_cast returned False")

    # 3. Hand check
    hand = game.get_hand(player)
    if not hand.contains(card):
        raise CastingError(f"Cannot cast {card.name!r} — card not in hand")

    # 4. Move card from hand to stack zone
    stack_zone = player.zones[Zone.STACK]
    hand.remove(card)
    stack_zone.add(card)

    # Clear any stale colors_spent from a prior cast before new payment.
    if hasattr(card, "colors_spent"):
        del card.colors_spent

    # 5. Choose targets
    target_specs = card.get_targets(game)
    chosen_targets: list[Any] = []
    if target_specs:
        for spec in target_specs:
            target = player.choose_target(target_specs, spec)
            # Validate against filter_fn if the spec provides one
            filter_fn = getattr(spec, "filter_fn", None)
            if filter_fn is not None and target is not None:
                if not filter_fn(target):
                    stack_zone.remove(card)
                    hand.add(card)
                    raise CastingError(
                        f"Cannot cast {card.name!r} — chosen target does not "
                        f"satisfy filter: {getattr(spec, 'description', '')}"
                    )
            chosen_targets.append(target)

    # 5b. Protection check — reject targets that have protection from this
    #     spell (the T in DEBT).
    from engine.protection import has_protection_from

    for target in chosen_targets:
        if has_protection_from(target, card):
            # Rollback: move card from stack zone back to hand
            stack_zone.remove(card)
            hand.add(card)
            raise CastingError(
                f"Cannot cast {card.name!r} — target has protection from this spell"
            )

    # Targets are stored on the StackObject (not the card) and passed
    # through the resolve pipeline via on_resolve(game, targets=...).

    # 6. Mana check / payment (rollback on failure)
    # Ensure the card knows its controller so that cost_reduction() hooks
    # (e.g. Embercleave counting attacking creatures you control) see the
    # casting player, even for cards that were added to hand without an
    # explicit controller assignment.
    if card.controller is None:
        card.controller = player
    if alternative_cost is None:
        reduction = get_cost_reduction(game, card, player)
        effective_cost = (
            _apply_cost_reduction(card.mana_cost, reduction)
            if reduction > 0 else card.mana_cost
        )
    else:
        effective_cost = alternative_cost

    can_pay_for = getattr(player.mana_pool, "can_pay_for", None)
    if callable(can_pay_for):
        can_pay = bool(can_pay_for(effective_cost, {"usage": "cast_spell", "card": card}))
    else:
        can_pay = player.mana_pool.can_pay(effective_cost)

    if not can_pay:
        # Rollback: move card from stack zone back to hand
        stack_zone.remove(card)
        hand.add(card)
        raise CastingError(f"Cannot cast {card.name!r} — insufficient mana")

    # TODO: Phase 3 — support player choice for generic mana payment to optimize Converge color count
    pay_for = getattr(player.mana_pool, "pay_for", None)
    if callable(pay_for):
        payment_succeeded = bool(pay_for(effective_cost, {"usage": "cast_spell", "card": card}))
    else:
        payment_succeeded = player.mana_pool.pay(effective_cost)
    if not payment_succeeded:
        stack_zone.remove(card)
        hand.add(card)
        raise CastingError(f"Cannot cast {card.name!r} — insufficient mana")

    # Store colors of mana spent on the card for mechanics like Converge
    # that care about the colors used to cast the spell.
    card.colors_spent = list(player.mana_pool.last_payment_colors)  # type: ignore[attr-defined]
    card.mana_spent_total = player.mana_pool.last_payment_total  # type: ignore[attr-defined]

    # 7. Call on_cast hook
    card.on_cast(game)

    from engine.miracle import clear_miracle_window

    clear_miracle_window(game, card=card)

    # 8. Build on_resolve callback and push StackObject
    stack_obj = StackObject(
        source=card,
        controller=player,
        targets=chosen_targets,
        is_spell=True,
        on_resolve=lambda g: None,  # replaced below
    )

    def _on_resolve(g: GameState) -> None:
        _resolve_spell(g, card, player, stack_obj)

    stack_obj.on_resolve = _on_resolve
    game.stack.push(stack_obj)
    _apply_granted_casualty(game, player, card, stack_obj)


def cast_spell_via_miracle(game: GameState, player: Player, card: CardImpl) -> None:
    """Cast *card* from hand for its currently active miracle cost."""
    from engine.miracle import can_cast_via_miracle, get_miracle_window

    if not can_cast_via_miracle(game, player, card):
        raise CastingError(f"Cannot cast {card.name!r} via miracle")

    window = get_miracle_window(game, player, card)
    if window is None:
        raise CastingError(f"Cannot cast {card.name!r} via miracle")

    cast_spell_with_options(
        game,
        player,
        card,
        alternative_cost=window.cost,
        ignore_timing=True,
    )


# ------------------------------------------------------------------
# Cast spell without paying mana cost (free-cast from any zone)
# ------------------------------------------------------------------


def cast_spell_free(
    game: GameState,
    player: Player,
    card: CardImpl,
    from_zone: Zone,
) -> None:
    """Cast *card* without paying its mana cost, using the stack.

    This is used by effects that allow casting from zones other than hand
    (e.g. exile) without paying mana costs — such as Etali, Primal Storm
    or cascade.

    Pipeline
    --------
    1. **can_cast** — ask the card whether it can legally be cast (same
       legality as :func:`cast_spell`, minus mana/timing constraints).
    2. Move *card* from *from_zone* to the stack zone.
    3. Choose targets (if applicable) with validation and protection check.
    4. Call ``on_cast`` hook.
    5. Push a :class:`StackObject` whose ``on_resolve`` callback handles
       resolution normally (permanents → battlefield, non-permanents →
       graveyard).

    No timing check or mana payment is performed.  The spell goes on the
    stack and can be responded to normally (e.g. countered).

    If targeting or other post-move checks fail, the card is rolled back
    to its source zone.

    Parameters:
        game: The current game state.
        player: The player casting the spell.
        card: The card to cast.
        from_zone: The zone the card is currently in.

    Raises:
        CastingError: If the card cannot be found in *from_zone* or
            legality checks fail.
    """
    from engine.zones import move_to_zone

    # Ensure controller is set
    card.controller = player
    if card.owner is None:
        card.owner = player

    # 1. can_cast legality (same as cast_spell but skipping mana/timing)
    if not card.can_cast(game):
        raise CastingError(f"Cannot cast {card.name!r} — can_cast returned False")

    # 2. Locate card in source zone
    source_zone_container = player.zones[from_zone]
    if not source_zone_container.contains(card):
        # Try to find the card in any player's zone
        source_zone_container = None
        for p in game.players:
            z = p.zones[from_zone]
            if z.contains(card):
                source_zone_container = z
                break

    if source_zone_container is None or not source_zone_container.contains(card):
        raise CastingError(
            f"Cannot cast {card.name!r} — card not found in {from_zone.name}"
        )

    # Move card from source zone to stack zone
    stack_zone = player.zones[Zone.STACK]
    source_zone_container.remove(card)
    stack_zone.add(card)

    # 3. Choose targets (with rollback on failure)
    try:
        target_specs = card.get_targets(game)
        chosen_targets: list[Any] = []
        if target_specs:
            for spec in target_specs:
                target = player.choose_target(target_specs, spec)
                # Validate against filter_fn if the spec provides one
                filter_fn = getattr(spec, "filter_fn", None)
                if filter_fn is not None and target is not None:
                    if not filter_fn(target):
                        raise CastingError(
                            f"Cannot cast {card.name!r} — chosen target does not "
                            f"satisfy filter: {getattr(spec, 'description', '')}"
                        )
                chosen_targets.append(target)

        # Protection check — reject targets that have protection from this spell
        from engine.protection import has_protection_from

        for target in chosen_targets:
            if has_protection_from(target, card):
                raise CastingError(
                    f"Cannot cast {card.name!r} — target has protection from this spell"
                )
    except Exception as exc:
        # Rollback: move card from stack zone back to source zone
        stack_zone.remove(card)
        source_zone_container.add(card)
        raise CastingError(str(exc)) from exc

    # 4. Call on_cast hook
    card.colors_spent = []  # type: ignore[attr-defined]
    card.mana_spent_total = 0  # type: ignore[attr-defined]
    card.on_cast(game)

    from engine.miracle import clear_miracle_window

    clear_miracle_window(game, card=card)

    # 5. Build on_resolve callback and push StackObject
    stack_obj = StackObject(
        source=card,
        controller=player,
        targets=chosen_targets,
        is_spell=True,
        on_resolve=lambda g: None,  # replaced below
    )

    def _on_resolve(g: GameState) -> None:
        _resolve_spell(g, card, player, stack_obj)

    stack_obj.on_resolve = _on_resolve
    game.stack.push(stack_obj)
    _apply_granted_casualty(game, player, card, stack_obj)


# ------------------------------------------------------------------
# Resolution (called when the stack pops)
# ------------------------------------------------------------------

def _resolve_spell(
    game: GameState,
    card: CardImpl,
    player: Player,
    stack_obj: StackObject,
) -> None:
    """Resolve *card* cast by *player*.

    1. Call ``card.on_resolve(game, targets=targets)``.
    2. Remove the card from the stack zone.
    3. If the card is a permanent type, move it to the battlefield via
       :func:`~engine.zones.move_to_zone` (which handles trigger/effect
       registration and the ETB event).
    4. Otherwise (instant / sorcery), move it to the owner's graveyard.
    """
    from engine.zones import move_to_zone

    # Read targets from the StackObject — the single source of truth.
    # Set chosen_targets on the card just before resolution so that
    # _get_chosen_target helpers (which read via getattr) work.
    targets = stack_obj.targets
    if targets is not None:
        card.chosen_targets = targets  # type: ignore[attr-defined]

    card.on_resolve(game)

    if card.card_types & _PERMANENT_TYPES:
        # Move from stack to battlefield via move_to_zone, which handles
        # trigger/replacement-effect registration and ENTERS_BATTLEFIELD event.
        move_to_zone(game, card, Zone.STACK, Zone.BATTLEFIELD)
    else:
        # Instant/sorcery: move from stack to graveyard via move_to_zone.
        move_to_zone(
            game,
            card,
            Zone.STACK,
            Zone.GRAVEYARD,
            replacement_event=MoveToGraveyardReplacementEvent(
                moving_card=card,
                destination="graveyard",
                controller=player,
                owner=getattr(card, "owner", player),
            ),
        )


def counter_spell(game: GameState, stack_obj: Any) -> None:
    """Counter *stack_obj* and move its card through the zone pipeline.

    Uses :func:`engine.zones.move_to_zone` so stack-to-graveyard replacement
    effects (for example "exile it instead") apply the same way they do for
    normal spell resolution.
    """
    if not isinstance(stack_obj, StackObject):
        return

    from engine.zones import move_to_zone

    card = stack_obj.source
    stack_items = game.stack._items  # noqa: SLF001
    found = False
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            found = True
            break

    if not found:
        return

    move_to_zone(
        game,
        card,
        Zone.STACK,
        Zone.GRAVEYARD,
        replacement_event=MoveToGraveyardReplacementEvent(
            moving_card=card,
            destination="graveyard",
            controller=stack_obj.controller,
            owner=getattr(card, "owner", stack_obj.controller),
        ),
    )


# ------------------------------------------------------------------
# Play land (special action — does not use the stack)
# ------------------------------------------------------------------

def play_land(game: GameState, player: Player, land_card: CardImpl) -> None:
    """Play *land_card* from *player*'s hand onto the battlefield.

    Requirements (all must hold):

    * *land_card* has :attr:`CardType.LAND`.
    * *player* is the active player.
    * Current phase is a main phase.
    * The stack is empty.
    * ``player.land_plays_remaining > 0``.
    * The card is in the player's hand.

    On success the card moves from hand to battlefield and
    ``land_plays_remaining`` is decremented.

    Raises:
        CastingError: If any requirement is not met.
    """
    # Must be a land
    if CardType.LAND not in land_card.card_types:
        raise CastingError(
            f"Cannot play {land_card.name!r} as a land — not a land card"
        )

    # Sorcery-speed timing (active player, main phase, stack empty)
    if not is_sorcery_speed(game, player):
        raise CastingError(
            f"Cannot play land {land_card.name!r} — must be active player "
            "during main phase with empty stack"
        )

    # Land plays remaining
    if player.land_plays_remaining <= 0:
        raise CastingError(
            f"Cannot play land {land_card.name!r} — no land plays remaining"
        )

    # Card must be in hand
    hand = game.get_hand(player)
    if not hand.contains(land_card):
        raise CastingError(
            f"Cannot play land {land_card.name!r} — card not in hand"
        )

    # Ensure owner/controller are set so move_to_zone routes correctly.
    if land_card.owner is None:
        land_card.owner = player
    land_card.controller = player

    # Move from hand to battlefield via move_to_zone, which fires
    # ENTERS_BATTLEFIELD and registers triggers/replacement effects.
    from engine.zones import move_to_zone
    move_to_zone(game, land_card, Zone.HAND, Zone.BATTLEFIELD)

    # Decrement land plays
    player.land_plays_remaining -= 1


def resolve_top(game: GameState) -> None:
    """Resolve the top spell/ability on the stack.

    Pops the top item from the stack, calls its on_resolve callback,
    then runs state-based actions.  If the stack is empty this is a no-op.
    """
    if game.stack.is_empty():
        return
    from engine.state_based_actions import resolve_state_based_actions

    obj = game.stack.pop()
    obj.on_resolve(game)
    resolve_state_based_actions(game)
