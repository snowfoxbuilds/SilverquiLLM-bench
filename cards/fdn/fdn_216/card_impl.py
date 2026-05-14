"""Card implementation for Doubling Season."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Enchantment
from engine.replacement_effects import ReplacementEffect
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class DoublingSeason(Enchantment):
    """Doubling Season — {4}{G} — Enchantment.

    If an effect would create one or more tokens under your control,
    it creates twice that many of those tokens instead.
    If an effect would put one or more counters on a permanent you
    control, it puts twice that many of those counters on that permanent
    instead.

    FDN collector number 216.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Doubling Season")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{G}"))
        kwargs.setdefault(
            "rules_text",
            "If an effect would create one or more tokens under your control, "
            "it creates twice that many of those tokens instead.\n"
            "If an effect would put one or more counters on a permanent you "
            "control, it puts twice that many of those counters on that "
            "permanent instead.",
        )
        super().__init__(**kwargs)

    def register_replacement_effects(self, game: "GameState") -> None:
        """Register token doubling and counter doubling replacement effects.

        ENGINE NOTE: ``engine.game.create_token()`` and
        ``engine.game.add_counter()`` do not yet consult the replacement
        manager automatically.  These replacements are correctly registered
        and work when callers go through ``replacement_manager.apply()``,
        but full integration requires engine-level changes to ``create_token``
        and ``add_counter`` to query replacements before executing.
        """
        source = self

        # Token doubling replacement effect
        def _token_condition(game: Any, event_data: dict) -> bool:
            ctrl = getattr(source, "controller", None)
            player = event_data.get("player")
            return player is ctrl

        def _token_replacement(game: Any, event_data: dict) -> dict:
            count = event_data.get("count", 1)
            event_data["count"] = count * 2
            return event_data

        game.replacement_manager.register(ReplacementEffect(
            event_type="create_token",
            source=self,
            condition=_token_condition,
            replacement=_token_replacement,
            controller=getattr(self, "controller", None),
        ))

        # Counter doubling replacement effect
        def _counter_condition(game: Any, event_data: dict) -> bool:
            ctrl = getattr(source, "controller", None)
            permanent = event_data.get("permanent")
            perm_ctrl = getattr(permanent, "controller", None)
            return perm_ctrl is ctrl

        def _counter_replacement(game: Any, event_data: dict) -> dict:
            amount = event_data.get("amount", 1)
            event_data["amount"] = amount * 2
            return event_data

        game.replacement_manager.register(ReplacementEffect(
            event_type="add_counter",
            source=self,
            condition=_counter_condition,
            replacement=_counter_replacement,
            controller=getattr(self, "controller", None),
        ))
