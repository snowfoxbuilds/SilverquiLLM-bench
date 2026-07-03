"""Card implementation for Applied Geometry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class AppliedGeometry(Sorcery):
    """Applied Geometry — {2}{G}{U} — Sorcery.

    Create a token that's a copy of target non-Aura permanent you control,
    except it's a 0/0 Fractal creature in addition to its other types.
    Put six +1/+1 counters on it.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Applied Geometry")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}{U}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Target a non-Aura permanent you control."""
        controller = self.controller

        def _filter(obj: Any) -> bool:
            # Reject auras
            if getattr(obj, "is_aura", False):
                return False
            if hasattr(obj, "subtypes") and "Aura" in obj.subtypes:
                return False
            # Must be controlled by us
            if getattr(obj, "controller", None) is not controller:
                return False
            return True

        return [TargetRequirement(
            filter_fn=_filter,
            description="target non-Aura permanent you control",
            zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game: "GameState") -> None:
        """Create a Fractal token copy with six +1/+1 counters."""
        targets = getattr(self, "chosen_targets", None)
        if not targets:
            return

        target = targets[0] if isinstance(targets, list) else targets
        if target is None:
            return

        # Create a 0/0 Fractal creature token that copies the target's name
        # and card types, with Fractal and Creature added
        token_card_types = set(getattr(target, "card_types", set())) | {CardType.CREATURE}
        token_subtypes = set(getattr(target, "subtypes", set())) | {"Fractal"}

        token = Creature(
            name=target.name,
            owner=self.controller,
            controller=self.controller,
            base_power=0,
            base_toughness=0,
            card_types=token_card_types,
            subtypes=token_subtypes,
        )
        token.is_token = True
        token.plus_one_counters = 6
        token._base_plus_one_counters = 6

        game.get_battlefield(self.controller).add(token)
