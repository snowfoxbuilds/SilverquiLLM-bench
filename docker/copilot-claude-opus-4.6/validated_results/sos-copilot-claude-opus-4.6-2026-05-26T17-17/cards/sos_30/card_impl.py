"""Card implementation for Restoration Seminar."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RestorationSeminar(Sorcery):
    """Restoration Seminar — {5}{W}{W} — Sorcery — Lesson.

    Return target nonland permanent card from your graveyard to the battlefield.
    Paradigm (Then exile this spell. After you first resolve a spell with this
    name, you may cast a copy of it from exile without paying its mana cost at
    the beginning of each of your first main phases.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Restoration Seminar")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{W}{W}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Return target nonland permanent card from your graveyard to the "
            "battlefield.\nParadigm (Then exile this spell. After you first "
            "resolve a spell with this name, you may cast a copy of it from "
            "exile without paying its mana cost at the beginning of each of "
            "your first main phases.)",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target nonland permanent card in your graveyard."""
        def _filter(obj: Any) -> bool:
            card_types = getattr(obj, "card_types", set())
            if CardType.LAND in card_types:
                return False
            permanent_types = {CardType.CREATURE, CardType.ENCHANTMENT,
                              CardType.ARTIFACT, CardType.PLANESWALKER}
            return bool(card_types & permanent_types)

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target nonland permanent card",
                zone=Zone.GRAVEYARD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Return target from graveyard to battlefield, then exile self (Paradigm)."""
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        controller = self.controller

        if target is not None and controller is not None:
            # Move target from graveyard to battlefield
            graveyard = game.get_graveyard(controller)
            if graveyard.contains(target):
                graveyard.remove(target)
                target.controller = controller
                game.get_battlefield(controller).add(target)

        # Paradigm: exile this spell and register paradigm
        if controller is not None:
            # Move self to exile (it's currently on the stack zone, which
            # will be handled by the resolution pipeline moving to graveyard.
            # We override by moving to exile instead.)
            # The casting pipeline moves instant/sorcery to graveyard after
            # on_resolve. We need to intercept. Set a flag for post-resolve.
            self._paradigm_exile = True
            game.register_paradigm(controller, self.name)

    def _post_resolve(self, game: "GameState") -> None:
        """Called after resolution to handle paradigm exile."""
        controller = self.controller
        if controller is not None and getattr(self, "_paradigm_exile", False):
            # Move from graveyard to exile
            graveyard = game.get_graveyard(controller)
            if graveyard.contains(self):
                graveyard.remove(self)
                game.get_exile(controller).add(self)
