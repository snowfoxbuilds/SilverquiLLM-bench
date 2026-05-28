"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3.

    Creature — Cat Cleric

    When this creature enters, target player creates a 1/1 white and
    black Inkling creature token with flying. Then if an opponent controls
    more creatures than you, this creature becomes prepared.

    Prepare spell: Swords to Plowshares — {W} — Instant
    Exile target creature. Its controller gains life equal to its power.

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white "
            "and black Inkling creature token with flying. Then if an "
            "opponent controls more creatures than you, this creature "
            "becomes prepared.",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def get_targets(self, game: GameState) -> list[Any]:
        """Target player for the ETB ability."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Schedule the ETB effect on the stack for after the creature enters.

        The engine fires the ETB event before registering the card's own
        triggers (by design, to avoid self-referencing), so self-ETB
        effects must be pushed onto the stack from on_resolve.  The
        stack object resolves after the creature has moved to the
        battlefield, so creature counts are correct for the prepared
        check.
        """
        from engine.stack import StackObject

        source = self

        def _etb_callback(g: GameState) -> None:
            _do_etb_effect(g, source)

        stack_obj = StackObject(
            source=self,
            controller=self.controller or self.owner,
            on_resolve=_etb_callback,
        )
        game.stack.push(stack_obj)

    def resolve_prepare_spell(self, game: GameState, target: Any) -> None:
        """Resolve the Swords to Plowshares prepare spell.

        Exile target creature. Its controller gains life equal to its power.
        Then this creature becomes unprepared.
        """
        from engine.zones import move_to_zone

        # Record the creature's power and controller before moving.
        creature_power = getattr(target, "base_power", 0)
        creature_controller = getattr(target, "controller", None) or getattr(target, "owner", None)

        # Exile the target creature (move from battlefield to exile).
        move_to_zone(game, target, Zone.BATTLEFIELD, Zone.EXILE)

        # Its controller gains life equal to its power.
        if creature_controller is not None and creature_power > 0:
            creature_controller.life += creature_power

        # Casting the prepare spell unprepares this creature.
        self.is_prepared = False

    def register_triggers(self, game: GameState) -> None:
        """Register the ETB trigger for Inkling token creation and prepared check.

        This trigger fires when the creature re-enters the battlefield
        (e.g. after being flickered).  The initial ETB on cast is handled
        by on_resolve pushing a stack object.
        """
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: EntersBattlefieldTriggeredEvent) -> bool:
            """Only fire when this creature itself enters the battlefield."""
            return event.permanent is source

        def _effect(game: GameState) -> None:
            _do_etb_effect(game, source)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )


def _do_etb_effect(game: Any, source: EmeritusOfTruceSwordsToPlowshares) -> None:
    """Execute the ETB effect: create Inkling token, then check prepared.

    Creates a 1/1 white+black Inkling creature token with flying for the
    target player, then sets is_prepared if an opponent controls more
    creatures than the controller.
    """
    from engine.game import create_token

    ctrl = getattr(source, "controller", None)
    if ctrl is None:
        return

    # Determine the target player from chosen_targets.
    chosen = getattr(source, "chosen_targets", None)
    target_player = chosen[0] if chosen else ctrl

    # Create a 1/1 white+black Inkling creature token with flying.
    inkling = Creature(
        name="Inkling",
        base_power=1,
        base_toughness=1,
        subtypes={"Inkling"},
        keywords=Keyword.FLYING,
        owner=target_player,
        controller=target_player,
    )
    inkling.is_token = True
    create_token(game, target_player, inkling)

    # Check prepared condition: if any opponent controls more creatures
    # than the controller.
    ctrl_creatures = _count_creatures(game, ctrl)
    for player in game.players:
        if player is ctrl:
            continue
        opp_creatures = _count_creatures(game, player)
        if opp_creatures > ctrl_creatures:
            source.is_prepared = True
            break


def _count_creatures(game: Any, player: Any) -> int:
    """Count the number of creatures on a player's battlefield."""
    bf = game.get_battlefield(player)
    count = 0
    for obj in bf.get_all():
        card_types = getattr(obj, "card_types", set())
        if CardType.CREATURE in card_types:
            count += 1
    return count
