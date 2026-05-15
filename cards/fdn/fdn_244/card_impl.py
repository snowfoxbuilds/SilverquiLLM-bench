"""Card implementation for Progenitus."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.protection import ProtectionAbility
from engine.replacement_effects import ReplacementEffect
from engine.types import ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class Progenitus(Creature):
    """Progenitus — {W}{W}{U}{U}{B}{B}{R}{R}{G}{G} — 10/10 — Legendary Hydra Avatar.

    Protection from everything.
    If Progenitus would be put into a graveyard from anywhere, reveal
    Progenitus and shuffle it into its owner's library instead.

    FDN collector number 244.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Progenitus")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}{W}{U}{U}{B}{B}{R}{R}{G}{G}"))
        kwargs.setdefault("subtypes", {"Hydra", "Avatar"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 10)
        kwargs.setdefault("base_toughness", 10)
        kwargs.setdefault(
            "rules_text",
            "Protection from everything\n"
            "If Progenitus would be put into a graveyard from anywhere, "
            "reveal Progenitus and shuffle it into its owner's library "
            "instead.",
        )
        super().__init__(**kwargs)
        # Protection from everything: matches any source
        self._init_protection()

    def _init_protection(self) -> None:
        """Set up protection from everything. Called from __init__ and
        can be re-invoked after characteristic resets."""
        self.protections = [
            ProtectionAbility(
                quality="everything",
                predicate=lambda source: True,
            )
        ]

    def _reset_characteristics(self) -> None:
        """Override to reapply protection from everything after reset."""
        super()._reset_characteristics()
        self._init_protection()

    def register_replacement_effects(self, game: "GameState") -> None:
        """Register graveyard-shuffle replacement effect.

        Registered for both ``"move_to_graveyard"`` (direct callers) and
        ``"creature_dies"`` / ``"sacrifice"`` so the engine's zone-move
        pipeline can also consult this replacement.
        """
        source = self

        def _condition(game: Any, event_data: dict) -> bool:
            return event_data.get("card") is source

        def _replacement(game: Any, event_data: dict) -> dict:
            # Instead of going to graveyard, shuffle into owner's library
            owner = getattr(source, "owner", None)
            if owner is not None:
                library = owner.zones[Zone.LIBRARY]
                library.add(source)
                library.shuffle()
            event_data["prevented"] = True
            return event_data

        controller = getattr(self, "controller", None)
        for event_type in ("move_to_graveyard", "creature_dies", "sacrifice"):
            game.replacement_manager.register(ReplacementEffect(
                event_type=event_type,
                source=self,
                condition=_condition,
                replacement=_replacement,
                controller=controller,
            ))
