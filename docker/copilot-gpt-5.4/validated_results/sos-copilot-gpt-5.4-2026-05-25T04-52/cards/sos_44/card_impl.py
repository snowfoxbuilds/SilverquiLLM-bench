"""Card implementation for Echocasting Symposium."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.game import create_token
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class EchocastingSymposium(Sorcery):
    """Echocasting Symposium."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Echocasting Symposium")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        super().__init__(**kwargs)
        self.paradigm_enabled = True

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        controller = self.controller
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "zones"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj, _controller=controller: (
                    isinstance(obj, Creature)
                    and getattr(obj, "controller", None) is _controller
                ),
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: GameState) -> None:
        chosen = getattr(self, "chosen_targets", [])
        target_player = chosen[0] if len(chosen) > 0 else None
        target_creature = chosen[1] if len(chosen) > 1 else None
        if target_player not in game.players or not isinstance(target_creature, Creature):
            return
        if not target_creature.is_on_battlefield(game):
            return
        token = self._create_token_copy(target_creature)
        create_token(game, target_player, token)

    def _create_token_copy(self, target_creature: Creature) -> Creature:
        token_kwargs = {
            "name": target_creature.name,
            "mana_cost": target_creature.mana_cost,
            "card_types": set(getattr(target_creature, "card_types", set())),
            "subtypes": set(getattr(target_creature, "subtypes", set())),
            "supertypes": set(getattr(target_creature, "supertypes", set())),
            "keywords": getattr(target_creature, "keywords", None),
            "rules_text": getattr(target_creature, "rules_text", ""),
            "base_power": target_creature.base_power,
            "base_toughness": target_creature.base_toughness,
        }
        token_class = target_creature.__class__
        try:
            token = token_class(**token_kwargs)
        except TypeError:
            token = Creature(**token_kwargs)
        if hasattr(target_creature, "colors"):
            token.colors = set(getattr(target_creature, "colors", set()))  # type: ignore[attr-defined]
        ward_cost = getattr(target_creature, "ward_cost", None)
        if ward_cost is not None:
            token.ward_cost = ward_cost
        return token
