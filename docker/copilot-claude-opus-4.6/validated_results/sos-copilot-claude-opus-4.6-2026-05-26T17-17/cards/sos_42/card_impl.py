"""Card implementation for Deluge Virtuoso."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class DelugeVirtuoso(Creature):
    """Deluge Virtuoso — {2}{U} — Creature — Human Wizard (2/2).

    ETB: tap target creature an opponent controls and put a stun counter on it.
    Opus: Whenever you cast an instant or sorcery, +1/+1 until EOT.
    If 5+ mana spent, +2/+2 instead.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Deluge Virtuoso")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """ETB target: creature an opponent controls."""
        controller = self.controller
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "controller", None) is not controller
                    and getattr(obj, "controller", None) is not None
                ),
                description="target creature an opponent controls",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """ETB: tap target and put a stun counter on it."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]
        if target is None:
            return

        # Tap target
        target.is_tapped = True

        # Put a stun counter on it
        if not hasattr(target, "stun_counters"):
            target.stun_counters = 0
        target.stun_counters += 1

    def register_triggers(self, game: "GameState") -> None:
        """Register the opus trigger for instant/sorcery casts.
        
        The actual trigger logic is handled via on_spell_cast which is
        called by game.notify_spell_cast and game.trigger_spell_cast.
        """
        pass

    def on_spell_cast(self, game: "GameState", event: Any) -> None:
        """Handle opus trigger via on_spell_cast notification."""
        spell = event.spell
        spell_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in spell_types and CardType.SORCERY not in spell_types:
            return
        if event.player is not self.controller:
            return
        mana_spent = getattr(event, "mana_spent", 0)
        if not hasattr(self, "_temp_power_bonus"):
            self._temp_power_bonus = 0
        if not hasattr(self, "_temp_toughness_bonus"):
            self._temp_toughness_bonus = 0
        if mana_spent >= 5:
            self._temp_power_bonus += 2
            self._temp_toughness_bonus += 2
        else:
            self._temp_power_bonus += 1
            self._temp_toughness_bonus += 1
