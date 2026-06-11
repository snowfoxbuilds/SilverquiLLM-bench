"""Card implementation for Glorious Decay."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant, Mode
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class GloriousDecay(Instant):
    """Glorious Decay — {1}{G} — Instant.

    Choose one —
    • Destroy target artifact.
    • Glorious Decay deals 4 damage to target creature with flying.
    • Exile target card from a graveyard. Draw a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Glorious Decay")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        super().__init__(**kwargs)
        self.modes: list[Mode] = [
            Mode(name="Destroy target artifact"),
            Mode(name="Deal 4 damage to target creature with flying"),
            Mode(name="Exile target card from a graveyard. Draw a card."),
        ]
        self.chosen_mode: int = 0
        self.chosen_targets: list[Any] = []

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Return targeting requirements based on chosen mode."""
        mode = self.chosen_mode
        if mode == 0:
            return [TargetRequirement(
                filter_fn=lambda obj: CardType.ARTIFACT in getattr(obj, "card_types", set()),
                description="target artifact",
                zone=Zone.BATTLEFIELD,
            )]
        elif mode == 1:
            return [TargetRequirement(
                filter_fn=lambda obj: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and Keyword.FLYING in getattr(obj, "keywords", Keyword(0))
                ),
                description="target creature with flying",
                zone=Zone.BATTLEFIELD,
            )]
        elif mode == 2:
            return [TargetRequirement(
                filter_fn=lambda obj: True,
                description="target card in a graveyard",
                zone=Zone.GRAVEYARD,
            )]
        return []

    def on_resolve(self, game: "GameState") -> None:
        """Resolve based on chosen mode."""
        targets = getattr(self, "chosen_targets", [])
        if not targets:
            return

        target = targets[0]
        mode = self.chosen_mode

        if mode == 0:
            # Destroy target artifact
            from engine.game import destroy
            destroy(game, target)
        elif mode == 1:
            # Deal 4 damage to target creature with flying
            target.damage_marked = getattr(target, "damage_marked", 0) + 4
            # Check if lethal (SBA: toughness <= damage)
            toughness = getattr(target, "toughness", None)
            if toughness is not None and target.damage_marked >= toughness:
                # Move to graveyard
                controller = getattr(target, "controller", None)
                if controller is not None:
                    bf = game.get_battlefield(controller)
                    if bf.contains(target):
                        bf.remove(target)
                        game.get_graveyard(controller).add(target)
        elif mode == 2:
            # Exile target card from a graveyard, draw a card
            owner = getattr(target, "owner", None)
            # Find which graveyard contains the target
            for player in game.players:
                gy = game.get_graveyard(player)
                if gy.contains(target):
                    gy.remove(target)
                    break
            # Exile it
            exile_owner = owner if owner else self.controller
            game.get_exile(exile_owner).add(target)
            # Draw a card
            from engine.game import draw_card
            draw_card(game, self.controller)
