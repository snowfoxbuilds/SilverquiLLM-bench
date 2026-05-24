"""Card implementation for Ajani, Caller of the Pride."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import LoyaltyAbility, Planeswalker
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, ManaType, Supertype
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.engine.player import Player

    from cards.registry import CardRegistry

class AjaniCallerOfThePride(Planeswalker):
    """Ajani, Caller of the Pride — {1}{W}{W} — 4 loyalty.

    +1: Put a +1/+1 counter on up to one target creature.
    -3: Target creature gains flying and double strike until end of turn.
    -8: Create X 2/2 white Cat creature tokens, where X is your life total.

    (Simplified: abilities are stubs that adjust loyalty only.)
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

        def _plus1(game: Any) -> None:
            # Put a +1/+1 counter on up to one target creature.
            target = getattr(pw, "_resolve_target", None)
            if target is not None and hasattr(target, "plus_one_counters"):
                target.plus_one_counters += 1
                target._base_plus_one_counters = target.plus_one_counters

        def _minus3(game: Any) -> None:
            # Target creature gains flying and double strike until end of turn.
            target = getattr(pw, "_resolve_target", None)
            if target is not None and hasattr(target, "keywords"):
                from benchmarks.sos.workspace.engine.types import Keyword
                target.keywords = target.keywords | Keyword.FLYING | Keyword.DOUBLE_STRIKE

        def _minus8(game: Any) -> None:
            # Create X 2/2 white Cat creature tokens, where X is your life total.
            controller = pw.controller
            if controller is not None:
                from benchmarks.sos.workspace.engine.card import Creature
                from benchmarks.sos.workspace.engine.game import create_token
                life = getattr(controller, "life", 0)
                for _ in range(max(0, life)):
                    token = Creature(name="Cat", base_power=2, base_toughness=2)
                    create_token(game, controller, token)

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Put a +1/+1 counter on up to one target creature."),
            LoyaltyAbility(loyalty_cost=-3, effect=_minus3, description="-3: Target creature gains flying and double strike until end of turn."),
            LoyaltyAbility(loyalty_cost=-8, effect=_minus8, description="-8: Create X 2/2 Cat tokens, where X is your life total."),
        ]
