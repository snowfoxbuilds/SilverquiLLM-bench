"""Card implementation for Ajani, Caller of the Pride."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.card_queries import choose_object
from engine.stack import surviving_targets
from engine.continuous_effects import (
    DURATION_END_OF_TURN,
    ContinuousEffect,
    Layer,
)
from engine.types import CardType, Color, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player

    from cards.registry import CardRegistry


def _on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _all_creatures(game: Any) -> list[Any]:
    """Every creature on any battlefield (legal target set for +1 / −3)."""
    return [
        obj
        for player in game.players
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    ]


class AjaniCallerOfThePride(Planeswalker):
    """Ajani, Caller of the Pride — {1}{W}{W} — 4 loyalty.

    +1: Put a +1/+1 counter on up to one target creature.
    -3: Target creature gains flying and double strike until end of turn.
    -8: Create X 2/2 white Cat creature tokens, where X is your life total.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ajani, Caller of the Pride")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("starting_loyalty", 4)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ajani"}
        kwargs.setdefault(
            "rules_text",
            "+1: Put a +1/+1 counter on up to one target creature.\n"
            "-3: Target creature gains flying and double strike until end of turn.\n"
            "-8: Create X 2/2 white Cat creature tokens, where X is your life total.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        # ------------------------------------------------------------------
        # +1: Put a +1/+1 counter on up to one target creature.
        # "up to one target" → optional; the ability still activates with no
        # target chosen (targeting returns []).
        # ------------------------------------------------------------------
        def _plus1_targeting(
            game: Any, source: Any, controller: Any
        ) -> list[Any] | None:
            creatures = _all_creatures(game)
            if not creatures:
                return []
            chosen = choose_object(
                game,
                controller,
                creatures,
                "Put a +1/+1 counter on up to one target creature",
                source_card=source,
                optional=True,
            )
            if chosen is None:
                return []
            return [chosen]

        def _plus1(game: Any, targets: list[Any], context: Any = None) -> None:
            from engine.game import add_counter

            legal = surviving_targets(
                game, context, targets,
                is_legal=lambda t: CardType.CREATURE in getattr(t, "card_types", set())
                and hasattr(t, "plus_one_counters"),
            )
            for target in legal:
                add_counter(game, target, "+1/+1", 1)

        # ------------------------------------------------------------------
        # −3: Target creature gains flying and double strike until end of turn.
        # Required target — no legal creature ⇒ cannot be activated.
        # ------------------------------------------------------------------
        def _minus3_targeting(
            game: Any, source: Any, controller: Any
        ) -> list[Any] | None:
            creatures = _all_creatures(game)
            if not creatures:
                return None
            chosen = choose_object(
                game,
                controller,
                creatures,
                "Target creature gains flying and double strike",
                source_card=source,
            )
            if chosen is None:
                return None
            return [chosen]

        def _minus3(game: Any, targets: list[Any], context: Any = None) -> None:
            legal = surviving_targets(
                game, context, targets,
                is_legal=lambda t: CardType.CREATURE in getattr(t, "card_types", set()),
            )
            target = legal[0] if legal else None
            if target is None:
                return
            grant = Keyword.FLYING | Keyword.DOUBLE_STRIKE

            def _apply(g: Any) -> None:
                target.keywords = getattr(target, "keywords", Keyword(0)) | grant

            # Until-end-of-turn: keywords are reset to their originals on every
            # apply_all() pass, so a bare assignment would not survive
            # re-derivation — register a continuous effect that re-grants them.
            target.keywords = getattr(target, "keywords", Keyword(0)) | grant
            game.effect_manager.add(
                ContinuousEffect(
                    source=pw,
                    layer=Layer.ABILITY,
                    apply=_apply,
                    duration=DURATION_END_OF_TURN,
                )
            )

        # ------------------------------------------------------------------
        # −8: Create X 2/2 white Cat creature tokens (X = your life total).
        # Untargeted.
        # ------------------------------------------------------------------
        def _minus8(game: Any) -> None:
            from engine.game import create_token

            controller = pw.controller
            if controller is None:
                return
            life = max(0, getattr(controller, "life", 0))
            if life <= 0:
                return
            from cards.fdn.tokens import make_creature_token

            create_token(
                game,
                controller,
                factory=lambda: make_creature_token(
                    "Cat", {"Cat"}, [Color.WHITE], 2, 2
                ),
                count=life,
            )

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                targeting=_plus1_targeting,
                description="+1: Put a +1/+1 counter on up to one target creature.",
            ),
            LoyaltyAbility(
                loyalty_cost=-3,
                effect=_minus3,
                targeting=_minus3_targeting,
                description="-3: Target creature gains flying and double strike until end of turn.",
            ),
            LoyaltyAbility(
                loyalty_cost=-8,
                effect=_minus8,
                description="-8: Create X 2/2 white Cat tokens, where X is your life total.",
            ),
        ]
