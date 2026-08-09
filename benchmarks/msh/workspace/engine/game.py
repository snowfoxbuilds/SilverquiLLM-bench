"""Game setup, helper actions, and the full game loop.

Provides the top-level functions for creating, running, and interacting with
a game of Magic: The Gathering:

- :func:`create_game` — initialise a full game state for two players.
- Helper actions — module-level functions for common game operations
  (``deal_damage``, ``destroy``, ``sacrifice``, ``exile``, ``draw_card``,
  ``discard``, ``create_token``, ``add_counter``, ``remove_counter``,
  ``tap``, ``untap``).
- :func:`run_game` — execute turns until the game ends, returning the winner.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.events import (
    AddCounterReplacementEvent,
    CounterAddedTriggeredEvent,
    CreateTokenReplacementEvent,
    CreatureDiesReplacementEvent,
    DealsDamageTriggeredEvent,
    DrawsCardTriggeredEvent,
    EntersBattlefieldTriggeredEvent,
    GainsLifeTriggeredEvent,
    LosesLifeTriggeredEvent,
    PermanentDestroyedReplacementEvent,
    SacrificeReplacementEvent,
)
from engine.game_state import GameState
from engine.turn import run_turn
from engine.types import Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.card import CardImpl, Creature
    from engine.player import Player


# Maximum number of turns before the game is considered a draw.
# Prevents infinite loops in deterministic or stuck game states.
MAX_TURNS: int = 1000


# ---------------------------------------------------------------------------
# Game creation
# ---------------------------------------------------------------------------

def create_game(
    player1: Player,
    player2: Player,
    deck1: list[CardImpl],
    deck2: list[CardImpl],
) -> GameState:
    """Create and initialise a new two-player game.

    Steps performed:

    1. Set each player's life total to 20.
    2. Place *deck1* / *deck2* into the respective player's library zone.
    3. Shuffle each library.
    4. Draw 7 cards for each player.
    5. Set the active player to *player1*.

    Card ownership is set so that each card's ``owner`` and ``controller``
    point to the player whose deck it came from.

    Parameters:
        player1: The first player (goes first).
        player2: The second player.
        deck1: Cards comprising player1's deck.
        deck2: Cards comprising player2's deck.

    Returns:
        A fully initialised :class:`GameState` ready for play.
    """
    # 1. Set life totals
    player1.life = 20
    player2.life = 20

    # 2. Place deck cards into libraries and set ownership
    library1 = player1.zones[Zone.LIBRARY]
    for card in deck1:
        card.owner = player1
        card.controller = player1
        library1.add(card)

    library2 = player2.zones[Zone.LIBRARY]
    for card in deck2:
        card.owner = player2
        card.controller = player2
        library2.add(card)

    # 3. Shuffle libraries
    library1.shuffle()
    library2.shuffle()

    # Build the game state
    game = GameState([player1, player2])

    # 4. Draw 7 cards each
    for _ in range(7):
        draw_card(game, player1)
    for _ in range(7):
        draw_card(game, player2)

    # 5. Active player is player1 (index 0 — already the default)
    game.active_player_index = 0
    game.priority_player_index = 0

    return game


# ---------------------------------------------------------------------------
# Common helper actions
# ---------------------------------------------------------------------------

def deal_damage(game: GameState, source: Any, target: Any, amount: int) -> None:
    """Deal *amount* damage from *source* to *target*.

    If *target* has a ``life`` attribute (i.e. is a player), life is reduced.
    If *target* has a ``damage_marked`` attribute (i.e. is a creature),
    damage is marked on it.

    Fires :attr:`EventType.DEALS_DAMAGE` via the trigger manager.

    Parameters:
        game: The current game state.
        source: The object dealing the damage.
        target: The player or creature receiving the damage.
        amount: The amount of damage to deal (must be > 0 to have effect).
    """
    if amount <= 0:
        return

    from engine.protection import has_protection_from
    from engine.types import Keyword

    # Protection prevents damage from sources with the protected-from quality.
    if has_protection_from(target, source):
        return

    if hasattr(target, "life"):
        # Target is a player
        target.life -= amount
        # Fire damage trigger
        game.trigger_manager.fire_event(
            game,
            DealsDamageTriggeredEvent(source=source, target=target, amount=amount),
        )
        # Fire loses-life trigger
        game.trigger_manager.fire_event(
            game,
            LosesLifeTriggeredEvent(player=target, amount=amount),
        )
    elif hasattr(target, "damage_marked"):
        # Target is a creature
        target.damage_marked += amount

        # Track deathtouch damage for SBA rule 704.5h
        source_kw = getattr(source, "keywords", Keyword(0))
        if Keyword.DEATHTOUCH in source_kw:
            target.dealt_deathtouch_damage = True

        # Fire damage trigger
        game.trigger_manager.fire_event(
            game,
            DealsDamageTriggeredEvent(source=source, target=target, amount=amount),
        )

    # Lifelink: controller of source gains life equal to damage dealt
    source_kw = getattr(source, "keywords", Keyword(0))
    if Keyword.LIFELINK in source_kw:
        controller = getattr(source, "controller", None)
        if controller is not None and hasattr(controller, "life"):
            gain_life(game, controller, amount)


def gain_life(game: GameState, player: Any, amount: int, source: Any = None) -> None:
    """Have *player* gain *amount* life.

    One of the two sanctioned life-mutation paths (the other is
    :func:`lose_life`). Adjusts the total and fires
    :class:`GainsLifeTriggeredEvent` so "whenever you gain life" abilities
    (Ajani's Pridemate et al.) trigger regardless of the gain's source —
    lifelink, ETB triggers, or spell effects. Card impls must call this
    instead of mutating ``player.life`` directly (enforced by the AST guard
    in ``engine_tests/test_card_impl_ast_guard.py``).

    Parameters:
        game: The current game state.
        player: The player gaining life.
        amount: The amount gained (must be > 0 to have effect).
        source: Optional object causing the gain (informational).
    """
    if amount <= 0 or not hasattr(player, "life"):
        return
    player.life += amount
    if hasattr(game, "trigger_manager"):
        game.trigger_manager.fire_event(
            game, GainsLifeTriggeredEvent(player=player, amount=amount)
        )


def lose_life(game: GameState, player: Any, amount: int, source: Any = None) -> None:
    """Have *player* lose *amount* life (not via damage).

    The sanctioned counterpart to :func:`gain_life`: adjusts the total and
    fires :class:`LosesLifeTriggeredEvent` so "whenever you/an opponent lose
    life" abilities trigger. Use this for drain effects, "each opponent loses
    N life", forced self-loss, and life *payments* — any life reduction that
    is **not** combat/spell damage (damage already fires the event from
    :func:`deal_damage`). Card impls must call this instead of mutating
    ``player.life`` directly (enforced by the AST guard).

    Parameters:
        game: The current game state.
        player: The player losing life.
        amount: The amount lost (must be > 0 to have effect).
        source: Optional object causing the loss (informational).
    """
    if amount <= 0 or not hasattr(player, "life"):
        return
    player.life -= amount
    if hasattr(game, "trigger_manager"):
        game.trigger_manager.fire_event(
            game, LosesLifeTriggeredEvent(player=player, amount=amount)
        )


def destroy(game: GameState, permanent: Any) -> None:
    """Destroy *permanent* — move it from the battlefield to its owner's graveyard.

    Respects replacement effects via :func:`move_to_zone`.
    Creatures with the ``INDESTRUCTIBLE`` keyword are not destroyed.

    Parameters:
        game: The current game state.
        permanent: The permanent to destroy.
    """
    from engine.types import Keyword

    # Indestructible permanents cannot be destroyed
    kw = getattr(permanent, "keywords", Keyword(0))
    if Keyword.INDESTRUCTIBLE in kw:
        return

    controller = getattr(permanent, "controller", None)
    if controller is None:
        # Fallback: find which player's battlefield contains it
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(permanent):
                controller = player
                break
    if controller is None:
        return

    bf = game.get_battlefield(controller)
    if not bf.contains(permanent):
        return

    from engine.types import CardType

    card_types = getattr(permanent, "card_types", set())
    is_creature = CardType.CREATURE in card_types
    owner = getattr(permanent, "owner", controller)

    if is_creature:
        repl_event: CreatureDiesReplacementEvent | PermanentDestroyedReplacementEvent = (
            CreatureDiesReplacementEvent(
                creature=permanent, destination="graveyard",
                controller=controller, owner=owner,
            )
        )
    else:
        repl_event = PermanentDestroyedReplacementEvent(
            permanent=permanent, destination="graveyard",
            controller=controller, owner=owner,
        )

    move_to_zone(
        game,
        permanent,
        Zone.BATTLEFIELD,
        Zone.GRAVEYARD,
        replacement_event=repl_event,
    )


def sacrifice(game: GameState, player: Player, permanent: Any) -> None:
    """Sacrifice *permanent* — move it from the battlefield to its owner's graveyard.

    Sacrificing cannot be prevented by indestructible or regeneration, but
    replacement effects that modify zone changes (e.g. "if this would be
    put into a graveyard, exile it instead") still apply via
    :func:`move_to_zone`.

    Parameters:
        game: The current game state.
        player: The player performing the sacrifice.
        permanent: The permanent to sacrifice.
    """
    bf = game.get_battlefield(player)
    if not bf.contains(permanent):
        return

    owner = getattr(permanent, "owner", player)
    move_to_zone(
        game,
        permanent,
        Zone.BATTLEFIELD,
        Zone.GRAVEYARD,
        replacement_event=SacrificeReplacementEvent(
            permanent=permanent, destination="graveyard",
            controller=player, owner=owner,
        ),
    )


def exile(game: GameState, obj: Any) -> None:
    """Exile *obj* — move it to its owner's exile zone.

    Works for objects on the battlefield, in the graveyard, on the stack,
    or in hand.

    Parameters:
        game: The current game state.
        obj: The game object to exile.
    """
    # Find which zone the object is currently in
    source_zone_type = None
    for player in game.players:
        for zone_type in Zone:
            zone = player.zones[zone_type]
            if zone.contains(obj):
                source_zone_type = zone_type
                break
        if source_zone_type is not None:
            break

    if source_zone_type is None:
        return

    move_to_zone(game, obj, source_zone_type, Zone.EXILE)


def draw_card(game: GameState, player: Player) -> Any | None:
    """Draw a card for *player* — move the top card of library to hand.

    If the library is empty, sets ``player.drawn_from_empty_library = True``
    (SBAs will handle the game loss).

    Fires :attr:`EventType.DRAWS_CARD` via the trigger manager.

    Parameters:
        game: The current game state.
        player: The player drawing a card.

    Returns:
        The drawn card, or ``None`` if the library was empty.
    """
    library = player.zones[Zone.LIBRARY]

    if len(library) == 0:
        player.drawn_from_empty_library = True
        return None

    # Top of library is the last element (index -1)
    cards = library.top(1)
    card = cards[0]
    library.remove(card)

    hand = player.zones[Zone.HAND]
    hand.add(card)

    # Track cards drawn this turn
    if not hasattr(player, "cards_drawn_this_turn"):
        player.cards_drawn_this_turn = 0
    player.cards_drawn_this_turn += 1

    # Fire trigger (only if game has a trigger_manager — may not during setup)
    if hasattr(game, "trigger_manager"):
        game.trigger_manager.fire_event(
            game,
            DrawsCardTriggeredEvent(player=player, card=card),
        )

    return card


def discard(game: GameState, player: Player, card: Any) -> None:
    """Discard *card* from *player*'s hand to the owner's graveyard.

    Parameters:
        game: The current game state.
        player: The player discarding.
        card: The card to discard (must be in the player's hand).
    """
    hand = game.get_hand(player)
    if not hand.contains(card):
        return

    move_to_zone(game, card, Zone.HAND, Zone.GRAVEYARD)


def _place_token(game: GameState, player: Player, token: Any, grp_id: Any) -> None:
    """Place a single already-built token on *player*'s battlefield + fire hooks."""
    token.is_token = True
    token.owner = player
    token.controller = player
    # Identity hook for the replay executor's token correlation (next phase):
    # a stable attachment point for an external GRE id, so tokens can be
    # matched without name reverse-lookup. Defaults to None.
    if getattr(token, "_grp_id", None) is None:
        token._grp_id = grp_id

    # Tokens don't come from an existing zone — add directly and fire hooks.
    # Ordering matches move_to_zone: fire ETB *before* registering the token's
    # own triggers so a token's ETB trigger doesn't self-fire on entry.
    battlefield = game.get_battlefield(player)
    battlefield.add(token)

    if hasattr(game, "trigger_manager"):
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=token, controller=player),
        )

    # Register triggers/replacement effects after the ETB event.
    if hasattr(token, "register_triggers"):
        token.register_triggers(game)
    if hasattr(token, "register_replacement_effects"):
        token.register_replacement_effects(game)

    # Re-derive continuous effects so anthems/lords buff the new token
    # immediately (and the token's own static effect, if any, is applied).
    if hasattr(game, "effect_manager") and len(game.effect_manager) > 0:
        game.effect_manager.apply_all(game)


def _clone_token(token: Any) -> Any:
    """Return a fresh shallow copy of *token* with an independent identity.

    Used when a creation-replacement effect (Doubling Season) multiplies a
    single supplied token object into several. Assigns a new ``object_id`` and
    copies the mutable characteristic containers so the copies do not alias.
    """
    import copy as _copy

    from engine.card import GameObject

    clone = _copy.copy(token)
    clone.object_id = GameObject._next_id
    GameObject._next_id += 1
    # Break aliasing of mutable containers shared by the shallow copy.
    for attr in ("card_types", "subtypes", "supertypes"):
        val = getattr(clone, attr, None)
        if isinstance(val, set):
            setattr(clone, attr, set(val))
    if isinstance(getattr(clone, "_generic_counters", None), dict):
        clone._generic_counters = dict(clone._generic_counters)
    clone._grp_id = None
    return clone


def create_token(
    game: GameState,
    player: Player,
    token: Any = None,
    *,
    factory: Any = None,
    count: int = 1,
    grp_id: Any = None,
) -> list[Any]:
    """Create one or more tokens on the battlefield under *player*'s control.

    Consults :class:`CreateTokenReplacementEvent` first, so token-doubling
    effects (Doubling Season) take effect. Each token is stamped with
    ``is_token``, ``owner``/``controller``, and a ``_grp_id`` identity hook,
    then entered via the battlefield hooks (ETB event, trigger/replacement
    registration, continuous-effect re-derivation).

    Callers may pass either a pre-built ``token`` object (the common case) or
    a ``factory`` callable that mints a fresh token each call (preferred when
    ``count`` may be multiplied, since every token needs a distinct object).
    When only ``token`` is given and the effective count exceeds one, the
    extra copies are cloned via :func:`_clone_token`.

    Parameters:
        game: The current game state.
        player: The player who controls the tokens.
        token: A pre-built token object (mutually exclusive-ish with factory).
        factory: Optional ``() -> token`` callable producing fresh tokens.
        count: Number of tokens to create before replacement (default 1).
        grp_id: Optional external identity stamped onto each token's
            ``_grp_id`` if not already set.

    Returns:
        The list of tokens actually placed on the battlefield.
    """
    if token is None and factory is None:
        return []

    # Creation-replacement effects (Doubling Season et al.) may change count.
    if hasattr(game, "replacement_manager"):
        event = game.replacement_manager.apply(
            game, CreateTokenReplacementEvent(player=player, count=count)
        )
        count = getattr(event, "count", count)
    if count <= 0:
        return []

    placed: list[Any] = []
    for i in range(count):
        if factory is not None:
            tok = factory()
        elif i == 0:
            tok = token
        else:
            tok = _clone_token(token)
        _place_token(game, player, tok, grp_id)
        placed.append(tok)
    return placed


def add_counter(
    game: GameState,
    permanent: Any,
    counter_type: str,
    amount: int = 1,
) -> None:
    """Add *amount* counters of *counter_type* to *permanent*.

    Supports ``"+1/+1"`` and ``"-1/-1"`` counter types via the
    ``plus_one_counters`` / ``minus_one_counters`` attributes.  For other
    counter types, uses a generic ``counters`` dict.

    Counters are a real engine primitive:

    * ``AddCounterReplacementEvent`` is consulted first, so effects that
      modify counter placement (e.g. Doubling Season) can adjust *amount*.
    * ``+1/+1`` / ``-1/-1`` counters persist their ``_base_*`` shadow fields
      so they survive the reset-then-reapply cycle in
      :meth:`~engine.continuous_effects.EffectManager.apply_all`. Card impls
      must **not** hand-roll ``_base_plus_one_counters = plus_one_counters``.
    * Other counter types live in the generic ``_generic_counters`` dict,
      surfaced read-only via the ``counters`` property.
    * ``CounterAddedTriggeredEvent`` fires after the counters land, so
      "whenever a counter is put on…" abilities trigger.

    Parameters:
        game: The current game state.
        permanent: The permanent to add counters to.
        counter_type: The type of counter (e.g. ``"+1/+1"``, ``"-1/-1"``,
            ``"loyalty"``, ``"charge"``).
        amount: Number of counters to add (default 1).
    """
    if amount <= 0:
        return

    # Replacement effects (Doubling Season et al.) may change the amount.
    if hasattr(game, "replacement_manager"):
        event = game.replacement_manager.apply(
            game,
            AddCounterReplacementEvent(
                permanent=permanent, counter_type=counter_type, amount=amount
            ),
        )
        amount = getattr(event, "amount", amount)
        if amount <= 0:
            return

    if counter_type == "+1/+1" and hasattr(permanent, "plus_one_counters"):
        permanent.plus_one_counters += amount
        if hasattr(permanent, "_base_plus_one_counters"):
            permanent._base_plus_one_counters += amount
    elif counter_type == "-1/-1" and hasattr(permanent, "minus_one_counters"):
        permanent.minus_one_counters += amount
        if hasattr(permanent, "_base_minus_one_counters"):
            permanent._base_minus_one_counters += amount
    elif counter_type == "loyalty" and hasattr(permanent, "loyalty"):
        permanent.loyalty += amount
    else:
        # Generic counter storage (charge, stash, oil, …).
        store = getattr(permanent, "_generic_counters", None)
        if store is None:
            store = {}
            permanent._generic_counters = store
        store[counter_type] = store.get(counter_type, 0) + amount

    # Fire the counter-added trigger after the counters have landed.
    if hasattr(game, "trigger_manager"):
        game.trigger_manager.fire_event(
            game,
            CounterAddedTriggeredEvent(
                permanent=permanent, counter_type=counter_type, amount=amount
            ),
        )


def remove_counter(
    game: GameState,
    permanent: Any,
    counter_type: str,
    amount: int = 1,
) -> None:
    """Remove *amount* counters of *counter_type* from *permanent*.

    Will not reduce below zero.

    Parameters:
        game: The current game state.
        permanent: The permanent to remove counters from.
        counter_type: The type of counter to remove.
        amount: Number of counters to remove (default 1).
    """
    if amount <= 0:
        return

    if counter_type == "+1/+1" and hasattr(permanent, "plus_one_counters"):
        permanent.plus_one_counters = max(0, permanent.plus_one_counters - amount)
        if hasattr(permanent, "_base_plus_one_counters"):
            permanent._base_plus_one_counters = permanent.plus_one_counters
    elif counter_type == "-1/-1" and hasattr(permanent, "minus_one_counters"):
        permanent.minus_one_counters = max(0, permanent.minus_one_counters - amount)
        if hasattr(permanent, "_base_minus_one_counters"):
            permanent._base_minus_one_counters = permanent.minus_one_counters
    elif counter_type == "loyalty" and hasattr(permanent, "loyalty"):
        permanent.loyalty = max(0, permanent.loyalty - amount)
    else:
        store = getattr(permanent, "_generic_counters", None)
        if store is not None and counter_type in store:
            store[counter_type] = max(0, store[counter_type] - amount)


def tap(game: GameState, permanent: Any) -> None:
    """Tap *permanent* — set ``is_tapped = True``.

    Parameters:
        game: The current game state.
        permanent: The permanent to tap.
    """
    if hasattr(permanent, "is_tapped"):
        permanent.is_tapped = True


def untap(game: GameState, permanent: Any) -> None:
    """Untap *permanent* — set ``is_tapped = False``.

    Parameters:
        game: The current game state.
        permanent: The permanent to untap.
    """
    if hasattr(permanent, "is_tapped"):
        permanent.is_tapped = False


# ---------------------------------------------------------------------------
# Game loop
# ---------------------------------------------------------------------------

def run_game(game: GameState) -> Player | None:
    """Run the game loop until the game ends.

    Executes :func:`~engine.turn.run_turn` in a loop, checking
    :attr:`GameState.is_game_over` after each turn.  State-based actions
    are resolved before and after each turn to catch game-ending conditions
    even when the priority loop auto-passes.

    Includes a safety limit of :data:`MAX_TURNS` to prevent infinite loops
    in deterministic or stuck game states.

    Parameters:
        game: The game state to run.

    Returns:
        The winning player, or ``None`` if the game ended in a draw (or
        hit the turn limit).
    """
    from engine.state_based_actions import resolve_state_based_actions

    while not game.is_game_over and game.turn_number <= MAX_TURNS:
        # Check SBAs before the turn (catches pre-existing conditions)
        resolve_state_based_actions(game)
        _check_game_over(game)
        if game.is_game_over:
            break

        run_turn(game)

        # Check SBAs after the turn
        resolve_state_based_actions(game)
        _check_game_over(game)

    return game.winner


def _check_game_over(game: GameState) -> None:
    """Check whether the game has ended and update ``game.is_game_over`` / ``game.winner``.

    The game ends when:
    - One player has lost (``has_lost``): the other player wins.
    - Both players have lost: the game is a draw (``winner = None``).
    - The turn limit is exceeded: the game is a draw.
    """
    lost_players = [p for p in game.players if p.has_lost]

    if len(lost_players) == len(game.players):
        # All players have lost — draw
        game.is_game_over = True
        game.winner = None
    elif len(lost_players) == 1:
        # One player lost — the other wins
        game.is_game_over = True
        game.winner = [p for p in game.players if not p.has_lost][0]
    elif game.turn_number > MAX_TURNS:
        # Turn limit exceeded — draw
        game.is_game_over = True
        game.winner = None
