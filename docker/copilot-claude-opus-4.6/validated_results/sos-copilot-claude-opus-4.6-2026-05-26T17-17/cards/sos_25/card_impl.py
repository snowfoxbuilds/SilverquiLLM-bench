"""Card implementation for Practiced Offense."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class PracticedOffense(Sorcery):
    """Practiced Offense — {2}{W} — Sorcery.

    Put a +1/+1 counter on each creature target player controls.
    Target creature gains your choice of double strike or lifelink until
    end of turn.
    Flashback {1}{W}.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Practiced Offense")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("keywords", Keyword.FLASHBACK)
        super().__init__(**kwargs)
        self.flashback_cost: ManaCost = ManaCost.parse("{1}{W}")
        self.chosen_mode: str | None = None
        self.cast_from_graveyard: bool = False
        self.zone: Zone | None = None

    def on_resolve(self, game: "GameState") -> None:
        """Put +1/+1 counter on each creature target player controls,
        target creature gains double strike or lifelink."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        target_player = chosen[0] if len(chosen) > 0 else None
        target_creature = chosen[1] if len(chosen) > 1 else None

        # Put +1/+1 counter on each creature target player controls
        if target_player is not None:
            battlefield = game.get_battlefield(target_player)
            for card in battlefield.get_all():
                if CardType.CREATURE in getattr(card, "card_types", set()):
                    card.plus_one_counters = getattr(card, "plus_one_counters", 0) + 1
                    if hasattr(card, "_base_plus_one_counters"):
                        card._base_plus_one_counters = card.plus_one_counters

        # Target creature gains chosen keyword
        if target_creature is not None:
            mode = getattr(self, "chosen_mode", None)
            if mode == "double_strike":
                target_creature.keywords = target_creature.keywords | Keyword.DOUBLE_STRIKE
            elif mode == "lifelink":
                target_creature.keywords = target_creature.keywords | Keyword.LIFELINK

        # If cast from graveyard (flashback), exile
        if self.cast_from_graveyard:
            self.zone = Zone.EXILE
