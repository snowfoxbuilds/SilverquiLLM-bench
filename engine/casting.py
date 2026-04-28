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
from engine.stack import StackObject
from engine.types import CardType, Keyword, Phase, Zone
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
    # 1. Timing
    if not can_cast_at_instant_speed(card) and not is_sorcery_speed(game, player):
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

    # 5. Choose targets
    target_specs = card.get_targets(game)
    chosen_targets: list[Any] = []
    if target_specs:
        for spec in target_specs:
            target = player.choose_target(target_specs, spec)
            chosen_targets.append(target)

    # 6. Mana check / payment (rollback on failure)
    if not player.mana_pool.can_pay(card.mana_cost):
        # Rollback: move card from stack zone back to hand
        stack_zone.remove(card)
        hand.add(card)
        raise CastingError(f"Cannot cast {card.name!r} — insufficient mana")

    player.mana_pool.pay(card.mana_cost)

    # 7. Call on_cast hook
    card.on_cast(game)

    # 8. Build on_resolve callback and push StackObject
    def _on_resolve(g: GameState) -> None:
        _resolve_spell(g, card, player)

    stack_obj = StackObject(
        source=card,
        controller=player,
        targets=chosen_targets,
        on_resolve=_on_resolve,
    )
    game.stack.push(stack_obj)


# ------------------------------------------------------------------
# Resolution (called when the stack pops)
# ------------------------------------------------------------------

def _resolve_spell(game: GameState, card: CardImpl, player: Player) -> None:
    """Resolve *card* cast by *player*.

    1. Call ``card.on_resolve(game)``.
    2. Remove the card from the stack zone.
    3. If the card is a permanent type, move it to the battlefield.
    4. Otherwise (instant / sorcery), move it to the owner's graveyard.
    """
    card.on_resolve(game)

    # Remove from stack zone
    stack_zone = player.zones[Zone.STACK]
    if stack_zone.contains(card):
        stack_zone.remove(card)

    if card.card_types & _PERMANENT_TYPES:
        game.get_battlefield(player).add(card)
        # Automatically register triggered abilities when entering the battlefield.
        if hasattr(card, "register_triggers"):
            card.register_triggers(game)
        # Automatically register replacement effects when entering the battlefield.
        if hasattr(card, "register_replacement_effects"):
            card.register_replacement_effects(game)
    else:
        # Use card's owner for graveyard (consistent with SBA convention).
        # Fall back to caster if owner is not set.
        graveyard_owner = card.owner if card.owner is not None else player
        game.get_graveyard(graveyard_owner).add(card)


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

    # Move from hand to battlefield
    battlefield = game.get_battlefield(player)
    move_zone(land_card, hand, battlefield)

    # Automatically register triggered abilities when entering the battlefield.
    if hasattr(land_card, "register_triggers"):
        land_card.register_triggers(game)
    # Automatically register replacement effects when entering the battlefield.
    if hasattr(land_card, "register_replacement_effects"):
        land_card.register_replacement_effects(game)

    # Decrement land plays
    player.land_plays_remaining -= 1
