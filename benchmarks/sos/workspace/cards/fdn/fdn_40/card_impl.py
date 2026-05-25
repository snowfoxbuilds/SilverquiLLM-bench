"""Card implementation for High Fae Trickster."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
)
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return True if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class HighFaeTrickster(Creature):
    """High Fae Trickster — {3}{U} — 4/2 — Faerie Wizard — Flash, Flying.

    You may cast spells as though they had flash.

    FDN collector number 40.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "High Fae Trickster")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault("subtypes", {"Faerie", "Wizard"})
        kwargs.setdefault("keywords", Keyword.FLASH | Keyword.FLYING)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Flash\nFlying\nYou may cast spells as though they had flash.",
        )
        super().__init__(**kwargs)
        self._flash_effect_ref: ContinuousEffect | None = None

    def register_triggers(self, game: "GameState") -> None:
        """Register continuous effect: controller may cast spells as though they had flash."""
        source = self

        def _apply_flash_grant(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            if not _is_on_battlefield(game, source):
                return
            # ENGINE LIMITATION: There's no native "cast as though flash"
            # mechanism. We set a player attribute that casting could check.
            ctrl.can_cast_as_flash = True

        self._flash_effect_ref = game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_flash_grant,
            duration=DURATION_PERMANENT,
        ))

    def unregister_triggers(self, game: "GameState") -> None:
        """Clean up flash grant when leaving battlefield."""
        ctrl = getattr(self, "controller", None)
        if self._flash_effect_ref is not None:
            game.effect_manager.remove(self._flash_effect_ref)
            self._flash_effect_ref = None
        # Only remove the ability if no other Trickster remains on battlefield
        if ctrl is not None:
            has_other = False
            for player in game.players:
                for obj in game.get_battlefield(player).get_all():
                    if (
                        obj is not self
                        and isinstance(obj, HighFaeTrickster)
                        and getattr(obj, "controller", None) is ctrl
                    ):
                        has_other = True
                        break
                if has_other:
                    break
            if not has_other:
                ctrl.can_cast_as_flash = False
