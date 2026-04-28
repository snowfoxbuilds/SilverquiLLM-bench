"""State-based actions checker and resolver.

State-based actions (SBAs) are game rules that are checked and applied
automatically whenever a player would receive priority.  They are checked
repeatedly until no more actions are taken, at which point triggered
abilities are placed on the stack.

References: MTG Comprehensive Rules §704.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from engine.types import Supertype, Zone
from engine.zones import ZoneContainer

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _battlefield(game: GameState, player: Player) -> ZoneContainer:
    """Return *player*'s battlefield zone."""
    return player.zones[Zone.BATTLEFIELD]


def _graveyard(game: GameState, player: Player) -> ZoneContainer:
    """Return *player*'s graveyard zone."""
    return player.zones[Zone.GRAVEYARD]


def _move_to_graveyard(game: GameState, player: Player, obj: Any) -> None:
    """Move *obj* from the battlefield to its owner's graveyard.

    Per MTG rule §704.5, when a permanent is destroyed or otherwise put
    into a graveyard by an SBA it goes to its **owner's** graveyard, not
    the controller's.  We use duck-typing: if *obj* has an ``owner``
    attribute, the permanent is placed in that player's graveyard;
    otherwise we fall back to *player* (the controller).
    """
    bf = _battlefield(game, player)
    if bf.contains(obj):
        owner = obj.owner if hasattr(obj, "owner") else player
        gy = _graveyard(game, owner)
        bf.remove(obj)
        gy.add(obj)
        # Automatically unregister triggered abilities when leaving the battlefield.
        game.trigger_manager.unregister(obj)


def _owner_of(game: GameState, obj: Any) -> Player:
    """Return the owner of *obj*.

    Falls back to checking which player's battlefield contains the object,
    then defaults to the first player.
    """
    if hasattr(obj, "owner"):
        return obj.owner
    # Fallback: check each player's battlefield
    for player in game.players:
        if _battlefield(game, player).contains(obj):
            return player
    return game.players[0]


# ---------------------------------------------------------------------------
# Individual SBA checks
# ---------------------------------------------------------------------------

def _sba_player_life_zero(game: GameState) -> bool:
    """A player with 0 or less life loses the game."""
    action_taken = False
    for player in game.players:
        if player.life <= 0 and not player.has_lost:
            player.has_lost = True
            action_taken = True
    return action_taken


def _sba_creature_zero_toughness(game: GameState) -> bool:
    """A creature with toughness 0 or less is put into its owner's graveyard."""
    action_taken = False
    to_remove: list[tuple[Player, Any]] = []
    for player in game.players:
        for obj in _battlefield(game, player).get_all():
            if hasattr(obj, "toughness") and obj.toughness <= 0:
                to_remove.append((player, obj))
    for player, obj in to_remove:
        _move_to_graveyard(game, player, obj)
        action_taken = True
    return action_taken


def _sba_creature_lethal_damage(game: GameState) -> bool:
    """A creature with lethal damage marked on it is destroyed (moved to graveyard).

    Lethal damage means ``damage_marked >= toughness`` (rule 704.5g) or the
    creature has been dealt damage by a source with deathtouch and has any
    damage marked on it (rule 704.5h).  Creatures with the ``indestructible``
    keyword are skipped.
    """
    action_taken = False
    to_remove: list[tuple[Player, Any]] = []
    for player in game.players:
        for obj in _battlefield(game, player).get_all():
            if not hasattr(obj, "toughness") or not hasattr(obj, "damage_marked"):
                continue

            # Skip indestructible creatures
            if hasattr(obj, "keywords"):
                from engine.types import Keyword

                if Keyword.INDESTRUCTIBLE in obj.keywords:
                    continue

            lethal = obj.damage_marked >= obj.toughness
            # Rule 704.5h: creature dealt damage by a deathtouch source
            deathtouch_lethal = (
                getattr(obj, "dealt_deathtouch_damage", False)
                and obj.damage_marked > 0
            )

            if lethal or deathtouch_lethal:
                to_remove.append((player, obj))

    for player, obj in to_remove:
        _move_to_graveyard(game, player, obj)
        action_taken = True
    return action_taken


def _sba_draw_from_empty_library(game: GameState) -> bool:
    """A player who attempted to draw from an empty library loses the game."""
    action_taken = False
    for player in game.players:
        if (
            hasattr(player, "drawn_from_empty_library")
            and player.drawn_from_empty_library
            and not player.has_lost
        ):
            player.has_lost = True
            action_taken = True
    return action_taken


def _sba_legend_rule(game: GameState) -> bool:
    """If a player controls 2+ legendaries with the same name, they choose one to keep.

    The player is asked to choose which legendary permanent to keep via
    ``player.choose()``.  All others are moved to the graveyard.
    """
    action_taken = False
    for player in game.players:
        bf = _battlefield(game, player)
        legendaries: dict[str, list[Any]] = defaultdict(list)
        for obj in bf.get_all():
            if (
                hasattr(obj, "supertypes")
                and Supertype.LEGENDARY in obj.supertypes
                and hasattr(obj, "name")
            ):
                legendaries[obj.name].append(obj)
        for name, objs in legendaries.items():
            if len(objs) >= 2:
                # Let the player choose which to keep
                keep = player.choose(objs, f"legend rule: choose which {name!r} to keep")
                for obj in objs:
                    if obj is not keep:
                        _move_to_graveyard(game, player, obj)
                action_taken = True
    return action_taken


def _sba_token_not_on_battlefield(game: GameState) -> bool:
    """Tokens that are not on the battlefield cease to exist (removed from game).

    Checks all non-battlefield zones for tokens and removes them entirely.
    """
    action_taken = False
    non_battlefield_zones = [
        Zone.HAND,
        Zone.GRAVEYARD,
        Zone.LIBRARY,
        Zone.EXILE,
        Zone.STACK,
        Zone.COMMAND,
    ]
    for player in game.players:
        for zone_type in non_battlefield_zones:
            zone = player.zones[zone_type]
            tokens = [
                obj
                for obj in zone.get_all()
                if hasattr(obj, "is_token") and obj.is_token
            ]
            for token in tokens:
                zone.remove(token)
                action_taken = True
    return action_taken


def _sba_aura_unattached(game: GameState) -> bool:
    """An Aura not attached to a legal object is put into its owner's graveyard.

    An aura is considered illegally attached if:
    - It has an ``attached_to`` attribute that is ``None``, OR
    - The object it is attached to is no longer on the battlefield.
    """
    action_taken = False
    to_remove: list[tuple[Player, Any]] = []

    # Collect all objects on all battlefields for checking attachment legality
    all_on_battlefield: set[int] = set()
    for player in game.players:
        for obj in _battlefield(game, player).get_all():
            all_on_battlefield.add(id(obj))

    for player in game.players:
        for obj in _battlefield(game, player).get_all():
            if hasattr(obj, "attached_to") and getattr(obj, "is_aura", True):
                target = obj.attached_to
                if target is None or id(target) not in all_on_battlefield:
                    to_remove.append((player, obj))

    for player, obj in to_remove:
        _move_to_graveyard(game, player, obj)
        action_taken = True
    return action_taken


def _sba_counter_annihilation(game: GameState) -> bool:
    """+1/+1 and -1/-1 counters on the same permanent annihilate in pairs."""
    action_taken = False
    for player in game.players:
        for obj in _battlefield(game, player).get_all():
            if (
                hasattr(obj, "plus_one_counters")
                and hasattr(obj, "minus_one_counters")
            ):
                plus = obj.plus_one_counters
                minus = obj.minus_one_counters
                if plus > 0 and minus > 0:
                    annihilate = min(plus, minus)
                    obj.plus_one_counters -= annihilate
                    obj.minus_one_counters -= annihilate
                    action_taken = True
    return action_taken


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_state_based_actions(game: GameState) -> bool:
    """Perform a single pass of all state-based actions.

    Returns ``True`` if any action was taken during this pass.  The caller
    should invoke this repeatedly until it returns ``False`` to ensure the
    game state is fully stable.
    """
    action_taken = False
    # Player with 0 or less life loses
    action_taken = _sba_player_life_zero(game) or action_taken
    # Creature with toughness 0 or less → graveyard
    action_taken = _sba_creature_zero_toughness(game) or action_taken
    # Creature with lethal damage → destroyed
    action_taken = _sba_creature_lethal_damage(game) or action_taken
    # Player who drew from empty library loses
    action_taken = _sba_draw_from_empty_library(game) or action_taken
    # Legend rule
    action_taken = _sba_legend_rule(game) or action_taken
    # Token not on battlefield → ceases to exist
    action_taken = _sba_token_not_on_battlefield(game) or action_taken
    # Aura not attached to legal object → graveyard
    action_taken = _sba_aura_unattached(game) or action_taken
    # +1/+1 and -1/-1 counter annihilation
    action_taken = _sba_counter_annihilation(game) or action_taken
    return action_taken


def resolve_state_based_actions(game: GameState) -> None:
    """Run state-based actions in a loop until no more actions are taken.

    After the loop stabilises, this is where triggered abilities would be
    checked and placed on the stack (not yet implemented).
    """
    while check_state_based_actions(game):
        pass
    # TODO: check for triggered abilities and put them on the stack
