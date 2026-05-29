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
from engine.events import MoveToGraveyardReplacementEvent, SpellCastTriggeredEvent
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
    raw += _get_granted_cost_reduction(game, controller, card)
    # Restore previous controller in case the caller doesn't want a
    # side-effect (get_cost_reduction is a query, not a mutation).
    card.controller = prev_controller
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


# ------------------------------------------------------------------
# Cast spell
# ------------------------------------------------------------------

def cast_spell(
    game: GameState,
    player: Player,
    card: CardImpl,
    payment_choices: dict[Any, int] | None = None,
) -> None:
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
    source_player, source_zone = _find_card_zone(game, card)
    miracle_available = source_zone is not None and _get_miracle_cost(card, source_zone) is not None

    # 1. Timing
    if (
        not miracle_available
        and not can_cast_at_instant_speed(card)
        and not is_sorcery_speed(game, player)
    ):
        raise CastingError(
            f"Cannot cast {card.name!r} — sorcery-speed timing not met"
        )

    # 2. can_cast
    if not card.can_cast(game):
        raise CastingError(f"Cannot cast {card.name!r} — can_cast returned False")

    # 3. Source-zone check
    if source_player is None or source_zone is None:
        raise CastingError(f"Cannot cast {card.name!r} — card not in hand")
    if source_zone != Zone.HAND and not _can_play_card_from_zone(game, player, card, source_zone):
        raise CastingError(f"Cannot cast {card.name!r} — card not in hand")

    hand = game.get_hand(player)
    source_container = source_player.zones[source_zone]

    # 4. Move card from hand to stack zone
    stack_zone = player.zones[Zone.STACK]
    source_container.remove(card)
    stack_zone.add(card)

    # Clear any stale mana-payment metadata from a prior cast before new payment.
    if hasattr(card, "colors_spent"):
        del card.colors_spent
    if hasattr(card, "mana_colors_spent"):
        del card.mana_colors_spent
    if hasattr(card, "actual_mana_spent"):
        del card.actual_mana_spent
    if hasattr(card, "_casted_via_miracle"):
        del card._casted_via_miracle

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
                    source_container.add(card)
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
            source_container.add(card)
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
    reduction = get_cost_reduction(game, card, player)
    effective_cost = _apply_cost_reduction(card.mana_cost, reduction) if reduction > 0 else card.mana_cost
    miracle_cost = _get_miracle_cost(card, source_zone)
    if miracle_cost is not None:
        effective_cost = miracle_cost
        card._casted_via_miracle = True

    if not player.mana_pool.can_pay(effective_cost, spend_context=card):
        # Rollback: move card from stack zone back to hand
        stack_zone.remove(card)
        source_container.add(card)
        raise CastingError(f"Cannot cast {card.name!r} — insufficient mana")

    if not player.mana_pool.pay(effective_cost, choices=payment_choices, spend_context=card):
        stack_zone.remove(card)
        source_container.add(card)
        raise CastingError(f"Cannot cast {card.name!r} — insufficient mana")

    # Store colors of mana spent on the card for mechanics like Converge
    # that care about the colors used to cast the spell.
    mana_colors_spent = list(player.mana_pool.last_payment_colors)
    card.colors_spent = len(mana_colors_spent)  # type: ignore[attr-defined]
    card.mana_colors_spent = mana_colors_spent  # type: ignore[attr-defined]
    card.actual_mana_spent = effective_cost.cmc  # type: ignore[attr-defined]

    casualty_values_paid = _pay_casualty_costs(game, player, card)

    # 7. Call on_cast hook
    card.on_cast(game)

    # 8. Build on_resolve callback and push StackObject
    stack_obj = StackObject(
        source=card,
        controller=player,
        targets=chosen_targets,
        on_resolve=lambda g: None,  # replaced below
    )

    def _on_resolve(g: GameState) -> None:
        _resolve_spell(g, card, player, stack_obj)

    stack_obj.on_resolve = _on_resolve
    game.stack.push(stack_obj)
    game.trigger_manager.fire_event(
        game,
        SpellCastTriggeredEvent(
            spell=card,
            card=card,
            player=player,
            controller=player,
        ),
    )
    for casualty_value in casualty_values_paid:
        game.stack.push(_build_casualty_trigger(game, player, stack_obj, casualty_value))


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

    # Clear any stale mana-payment metadata from a prior cast.
    if hasattr(card, "colors_spent"):
        del card.colors_spent
    if hasattr(card, "mana_colors_spent"):
        del card.mana_colors_spent
    if hasattr(card, "actual_mana_spent"):
        del card.actual_mana_spent
    card.actual_mana_spent = 0  # type: ignore[attr-defined]

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

    casualty_values_paid = _pay_casualty_costs(game, player, card)

    # 4. Call on_cast hook
    card.on_cast(game)

    # 5. Build on_resolve callback and push StackObject
    stack_obj = StackObject(
        source=card,
        controller=player,
        targets=chosen_targets,
        on_resolve=lambda g: None,  # replaced below
    )

    def _on_resolve(g: GameState) -> None:
        _resolve_spell(g, card, player, stack_obj)

    stack_obj.on_resolve = _on_resolve
    game.stack.push(stack_obj)
    game.trigger_manager.fire_event(
        game,
        SpellCastTriggeredEvent(
            spell=card,
            card=card,
            player=player,
            controller=player,
        ),
    )
    for casualty_value in casualty_values_paid:
        game.stack.push(_build_casualty_trigger(game, player, stack_obj, casualty_value))


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
        # Instant/sorcery: usually move from stack to graveyard. Some effects
        # (for example, "if that spell would be put into your graveyard, exile
        # it instead") mark the resolving spell with a destination override.
        destination = getattr(card, "_graveyard_destination_override", Zone.GRAVEYARD)
        replacement_event = None
        if destination != Zone.GRAVEYARD:
            replacement_event = MoveToGraveyardReplacementEvent(
                controller=player,
                owner=getattr(card, "owner", player),
                destination=destination.value,
            )
        move_to_zone(
            game,
            card,
            Zone.STACK,
            destination,
            replacement_event=replacement_event,
        )
        if hasattr(card, "_graveyard_destination_override"):
            delattr(card, "_graveyard_destination_override")


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

    # Card must be in hand or be temporarily playable from another zone.
    source_player, source_zone = _find_card_zone(game, land_card)
    if source_player is None or source_zone is None:
        raise CastingError(
            f"Cannot play land {land_card.name!r} — card not in hand"
        )
    if source_zone != Zone.HAND and not _can_play_card_from_zone(game, player, land_card, source_zone):
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
    move_to_zone(game, land_card, source_zone, Zone.BATTLEFIELD)

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


def _find_card_zone(game: GameState, card: CardImpl) -> tuple[Player | None, Zone | None]:
    """Return the player/zone currently containing *card*, if any."""
    for candidate_player in game.players:
        for zone in Zone:
            if candidate_player.zones[zone].contains(card):
                return candidate_player, zone
    return None, None


def _can_play_card_from_zone(game: GameState, player: Player, card: CardImpl, zone: Zone) -> bool:
    """Return ``True`` if *player* has a temporary or legacy permission to play *card*."""
    if zone == Zone.GRAVEYARD and getattr(card, "_castable_from_graveyard", False):
        return True

    playable_by = getattr(card, "_playable_by", None)
    if getattr(card, "_playable_this_turn", False):
        return playable_by is None or playable_by is player
    if getattr(card, "_playable_until_next_turn", False):
        return playable_by is None or playable_by is player

    return getattr(game, "can_player_temporarily_play_card", lambda *_args: False)(player, card)


def _get_miracle_cost(card: CardImpl, source_zone: Zone) -> ManaCost | None:
    """Return the miracle cost currently available for *card*, if any."""
    if source_zone != Zone.HAND:
        return None
    if not getattr(card, "_miracle_eligible", False):
        return None
    return getattr(card, "_miracle_cost_override", None)


def _get_casualty_grants(game: GameState, player: Player, card: CardImpl) -> list[tuple[Any, int]]:
    """Return casualty grants applied to *card* by permanents *player* controls."""
    if not getattr(card, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}:
        return []

    values: list[tuple[Any, int]] = []
    for permanent in game.get_battlefield(player).get_all():
        grant_fn = getattr(permanent, "granted_casualty_values_for", None)
        if grant_fn is None:
            continue
        granted = grant_fn(game, player, card)
        if isinstance(granted, int):
            granted = [granted]
        for value in granted or []:
            if isinstance(value, int) and value > 0:
                values.append((permanent, value))
    return values


def _get_granted_cost_reduction(game: GameState, player: Player, card: CardImpl) -> int:
    """Return total generic mana reduction granted to *card* by player's permanents."""
    total = 0
    for permanent in game.get_battlefield(player).get_all():
        grant_fn = getattr(permanent, "granted_cost_reduction_for", None)
        if not callable(grant_fn):
            continue
        granted = grant_fn(game, player, card)
        if isinstance(granted, int) and granted > 0:
            total += granted
    return total


def _get_eligible_casualty_creatures(
    game: GameState,
    player: Player,
    casualty_value: int,
    excluded_source: Any | None = None,
) -> list[Any]:
    """Return creatures the player may sacrifice to pay casualty."""
    eligible: list[Any] = []
    for permanent in game.get_battlefield(player).get_all():
        if permanent is excluded_source:
            continue
        if CardType.CREATURE not in getattr(permanent, "card_types", set()):
            continue
        if getattr(permanent, "power", 0) < casualty_value:
            continue
        eligible.append(permanent)
    return eligible


def _pay_casualty_costs(game: GameState, player: Player, card: CardImpl) -> list[int]:
    """Ask the player to pay any casualty costs granted to *card*."""
    from engine.game import sacrifice
    from engine.player import ScriptExhaustedError

    paid: list[int] = []
    for _, casualty_value in _get_casualty_grants(game, player, card):
        eligible = _get_eligible_casualty_creatures(game, player, casualty_value)
        if not eligible:
            continue
        try:
            wants_to_pay = player.choose_yes_no(f"Pay casualty {casualty_value} for {card.name}?")
        except ScriptExhaustedError:
            wants_to_pay = False
        if not wants_to_pay:
            continue
        chooser = getattr(player, "choose_card", None)
        if chooser is None:
            chooser = getattr(player, "choose")
        chosen = chooser(
            eligible,
            f"Choose a creature with power {casualty_value} or greater to sacrifice",
        )
        if chosen not in eligible:
            continue
        sacrifice(game, player, chosen)
        paid.append(casualty_value)
    return paid


def _iter_zone_objects(game: GameState, zone: Zone) -> list[Any]:
    """Return objects currently in *zone* across the game."""
    if zone == Zone.STACK:
        return list(game.stack.objects())

    objects: list[Any] = []
    for player in game.players:
        objects.extend(player.zones[zone].get_all())
    return objects


def _choose_targets_for_spell_copy(
    game: GameState,
    player: Player,
    stack_obj: StackObject,
) -> list[Any] | None:
    """Choose targets for a copied spell, defaulting to the original targets."""
    target_requirements = getattr(stack_obj.source, "get_targets", lambda _game: [])(game)
    if not target_requirements:
        return None

    new_targets: list[Any] = []
    original_targets = list(getattr(stack_obj, "targets", []) or [])
    for index, requirement in enumerate(target_requirements):
        legal_targets: list[Any] = []
        filter_fn = getattr(requirement, "filter_fn", None)
        if filter_fn is None:
            legal_targets.extend(_iter_zone_objects(game, getattr(requirement, "zone", Zone.BATTLEFIELD)))
        else:
            for obj in _iter_zone_objects(game, getattr(requirement, "zone", Zone.BATTLEFIELD)):
                if filter_fn(obj):
                    legal_targets.append(obj)
            for game_player in game.players:
                if filter_fn(game_player):
                    legal_targets.append(game_player)

        if not legal_targets:
            if index < len(original_targets):
                new_targets.append(original_targets[index])
            continue

        chosen = player.choose_target(legal_targets, requirement)
        if chosen not in legal_targets and index < len(original_targets):
            chosen = original_targets[index]
        new_targets.append(chosen)

    return new_targets


def _build_casualty_trigger(
    game: GameState,
    player: Player,
    original_stack_obj: StackObject,
    casualty_value: int,
) -> StackObject:
    """Create the casualty triggered ability for a spell that paid its casualty cost."""
    trigger_obj = StackObject(
        source=original_stack_obj.source,
        controller=player,
        targets=[],
        on_resolve=lambda _game: None,
    )
    trigger_obj.is_spell = False  # type: ignore[attr-defined]
    trigger_obj.casualty_value = casualty_value  # type: ignore[attr-defined]

    def _on_resolve(g: GameState) -> None:
        if original_stack_obj not in g.stack._items:  # noqa: SLF001
            return
        new_targets = _choose_targets_for_spell_copy(g, player, original_stack_obj)
        copy_obj = copy_spell(g, original_stack_obj, player, new_targets)
        g.stack.push(copy_obj)

    trigger_obj.on_resolve = _on_resolve
    return trigger_obj
