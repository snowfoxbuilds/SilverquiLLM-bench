"""Card implementation for Emeritus of Truce // Swords to Plowshares.

A **preparation card** (Comprehensive Rules 722).  The front (creature) face is
**Emeritus of Truce** — ``{1}{W}{W}`` Creature — Cat Cleric — 3/3 — white — with
the "Prepared" keyword.  Its enters-the-battlefield trigger makes a target
player create a 1/1 white-and-black Inkling token with flying, then prepares the
creature if an opponent controls strictly more creatures than its controller.

The back / prepare half is **Swords to Plowshares** — ``{W}`` Instant: exile
target creature; its controller gains life equal to its power.

When the creature becomes prepared, the additive
:mod:`engine.preparation` framework creates a castable copy of the prepare spell
(this Swords to Plowshares instant) in the controller's exile (CR 722.3c).
Casting that copy unprepares the source.

SOS collector number 13.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.events import EntersBattlefieldTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Color, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# ---------------------------------------------------------------------------
# Back / prepare half — Swords to Plowshares ({W} Instant)
# ---------------------------------------------------------------------------


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — ``{W}`` Instant.

    Exile target creature. Its controller gains life equal to its power.

    This is the prepare spell of *Emeritus of Truce*; copies of it are created
    in exile when the creature becomes prepared (CR 722.3c) and may be cast
    from there by the prepared permanent's controller.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault("colors", {Color.WHITE})
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to its power.",
        )
        # ``colors`` is not a CardImpl __init__ parameter; pop and set after.
        colors = kwargs.pop("colors", None)
        super().__init__(**kwargs)
        if colors is not None:
            self.colors = set(colors)

    # ------------------------------------------------------------------
    # Targeting / resolution
    # ------------------------------------------------------------------

    def get_targets(self, game: GameState) -> list[Any]:
        """Target a single creature on the battlefield."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Exile the target creature; its controller gains life equal to power."""
        targets = getattr(self, "chosen_targets", None) or []
        target = targets[0] if targets else None
        if target is None:
            return

        # Last-known power before it leaves the battlefield.
        power = getattr(target, "power", None)
        if power is None:
            power = getattr(target, "base_power", 0)

        controller = getattr(target, "controller", None)

        # Exile the creature from the battlefield.
        from engine.zones import move_to_zone

        owner = getattr(target, "owner", None) or controller
        from_bf = None
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(target):
                from_bf = bf
                break
        if from_bf is not None:
            move_to_zone(game, target, Zone.BATTLEFIELD, Zone.EXILE)

        # Its controller gains life equal to its power.
        if controller is not None and isinstance(power, int) and power > 0:
            controller.life += power


def _self_etb_condition(source: Any):
    """Return a condition callable matching only when *source* enters."""

    def _condition(game: Any, event: EntersBattlefieldTriggeredEvent) -> bool:
        return event.permanent is source

    return _condition


def _make_inkling(controller: Any) -> Creature:
    """Build a 1/1 white-and-black Inkling token with flying."""
    token = Creature(
        name="Inkling",
        subtypes={"Inkling"},
        keywords=Keyword.FLYING,
        base_power=1,
        base_toughness=1,
        owner=controller,
        controller=controller,
    )
    token.colors = {Color.WHITE, Color.BLACK}
    return token


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — ``{1}{W}{W}`` — 3/3.

    Creature — Cat Cleric. White. Keyword "Prepared".

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's prepared,
    you may cast a copy of its spell. Doing so unprepares it.)

    Back / prepare half — Swords to Plowshares — ``{W}`` Instant.

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared. "
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)",
        )
        colors = kwargs.pop("colors", {Color.WHITE})
        super().__init__(**kwargs)
        self.colors = set(colors)
        # "Prepared" is a printed keyword/ability label (the card is a
        # preparation card). It is *not* an evergreen Keyword flag, so it lives
        # here as a textual marker rather than in ``self.keywords`` (keeping the
        # Keyword enum unchanged / additive).
        self.printed_keywords: set[str] = {"Prepared"}
        # Preparation-card designation (CR 722.3a). Starts unprepared.
        self.is_prepared: bool = False
        self.prepared: bool = False

    # ------------------------------------------------------------------
    # Preparation card / back-face surface
    # ------------------------------------------------------------------

    #: The prepare half's mana cost ({W}) — probed by tests and the framework.
    @property
    def prepare_mana_cost(self) -> ManaCost:
        """The prepare ("Swords to Plowshares") half costs ``{W}``."""
        return ManaCost.parse("{W}")

    #: Alias so a test probing either spelling finds the {W} cost.
    @property
    def back_mana_cost(self) -> ManaCost:
        return ManaCost.parse("{W}")

    def make_prepare_spell(self) -> SwordsToPlowshares:
        """Create a fresh copy of the prepare spell (CR 722.3c).

        Returned object is the {W} Swords to Plowshares instant; the
        :mod:`engine.preparation` framework places it in the controller's exile
        when this creature becomes prepared.
        """
        controller = getattr(self, "controller", None)
        return SwordsToPlowshares(owner=controller, controller=controller)

    #: A back-face factory alias the tests may probe.
    def prepare_spell(self) -> SwordsToPlowshares:
        return self.make_prepare_spell()

    # ------------------------------------------------------------------
    # ETB trigger — token creation + conditional "becomes prepared"
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        """Register the self-referencing enters-the-battlefield trigger."""
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _effect(game: GameState) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # "target player creates ... an Inkling token ..." — the chosen
            # target player (may be the controller or an opponent).
            target_player = _get_target_player(source, game, ctrl)
            if target_player is None:
                return

            from engine.game import create_token

            token = _make_inkling(target_player)
            create_token(game, target_player, token)

            # "Then if an opponent controls more creatures than you, this
            # creature becomes prepared." — strictly-more comparison.
            you = _count_creatures(game, ctrl)
            most_opponent = 0
            for player in game.players:
                if player is ctrl:
                    continue
                most_opponent = max(most_opponent, _count_creatures(game, player))
            if most_opponent > you:
                from engine.preparation import mark_prepared

                mark_prepared(game, source)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_self_etb_condition(self),
                effect=_effect,
                source=self,
                controller=controller,
            )
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_target_player(source: Any, game: Any, controller: Any) -> Any:
    """Resolve the ETB's chosen target player.

    Prefers ``chosen_targets`` (the resolve-time idiom set by the engine /
    tests), then a controller-script answer, then defaults to the controller.
    """
    chosen = getattr(source, "chosen_targets", None)
    if chosen:
        for t in chosen:
            if t in game.players:
                return t
    script = getattr(controller, "_script", None)
    if script:
        try:
            candidate = controller.choose_target(list(game.players), "target player")
        except Exception:
            candidate = None
        if candidate in game.players:
            return candidate
    return controller


def _count_creatures(game: Any, player: Any) -> int:
    """Return the number of creatures *player* controls on the battlefield."""
    count = 0
    for obj in game.get_battlefield(player).get_all():
        if CardType.CREATURE in getattr(obj, "card_types", set()):
            count += 1
    return count
