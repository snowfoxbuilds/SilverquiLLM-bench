"""Card implementation for Lorehold Charm."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, Keyword, ManaCost, Zone, TargetRequirement

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdCharm(Instant):
    """Lorehold Charm — {R}{W} — Instant.

    Choose one —
    • Each opponent sacrifices a nontoken artifact of their choice.
    • Return target artifact or creature card with mana value 2 or less from
      your graveyard to the battlefield.
    • Creatures you control get +1/+1 and gain trample until end of turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold Charm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{W}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState", mode: int = 0, **kwargs: Any) -> list[Any]:
        """Return target requirements based on mode."""
        if mode == 2:
            def filter_fn(obj: Any) -> bool:
                card_types = getattr(obj, "card_types", set())
                is_valid_type = CardType.CREATURE in card_types or CardType.ARTIFACT in card_types
                if not is_valid_type:
                    return False
                mana_cost = getattr(obj, "mana_cost", None)
                if mana_cost is None:
                    return True
                return mana_cost.cmc <= 2

            return [TargetRequirement(
                filter_fn=filter_fn,
                description="Target artifact or creature card with mana value 2 or less in your graveyard",
                zone=Zone.GRAVEYARD,
            )]
        return []

    def on_resolve(self, game: "GameState") -> None:
        """Resolve based on chosen mode."""
        mode = getattr(self, "chosen_mode", None)
        if mode == 1:
            self._resolve_mode_1(game)
        elif mode == 2:
            self._resolve_mode_2(game)
        elif mode == 3:
            self._resolve_mode_3(game)

    def _resolve_mode_1(self, game: "GameState") -> None:
        """Each opponent sacrifices a nontoken artifact of their choice."""
        controller = self.controller
        for player in game.players:
            if player is controller:
                continue
            bf = game.get_battlefield(player)
            # Find nontoken artifacts
            nontoken_artifacts = []
            for obj in bf.get_all():
                card_types = getattr(obj, "card_types", set())
                is_token = getattr(obj, "is_token", False)
                if CardType.ARTIFACT in card_types and not is_token:
                    nontoken_artifacts.append(obj)
            if nontoken_artifacts:
                # Sacrifice the first one (opponent's choice - default)
                sac = nontoken_artifacts[0]
                bf.remove(sac)
                game.get_graveyard(player).add(sac)

    def _resolve_mode_2(self, game: "GameState") -> None:
        """Return target artifact or creature card with MV <= 2 from graveyard to battlefield."""
        targets = getattr(self, "chosen_targets", None) or []
        if not targets:
            return
        target = targets[0]
        controller = self.controller
        graveyard = game.get_graveyard(controller)
        if target in graveyard:
            graveyard.remove(target)
            game.get_battlefield(controller).add(target)

    def _resolve_mode_3(self, game: "GameState") -> None:
        """Creatures you control get +1/+1 and gain trample until end of turn."""
        controller = self.controller
        bf = game.get_battlefield(controller)
        for obj in bf.get_all():
            card_types = getattr(obj, "card_types", set())
            if CardType.CREATURE in card_types:
                obj._temp_power_bonus = getattr(obj, "_temp_power_bonus", 0) + 1
                obj._temp_toughness_bonus = getattr(obj, "_temp_toughness_bonus", 0) + 1
                if not hasattr(obj, "keywords_granted"):
                    obj.keywords_granted = set()
                obj.keywords_granted.add(Keyword.TRAMPLE)
