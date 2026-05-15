"""Card implementation for Sphinx of Forgotten Lore."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SphinxOfForgottenLore(Creature):
    """Sphinx of Forgotten Lore — {2}{U}{U} — 3/3 — Sphinx — Flash, Flying.

    Whenever this creature attacks, target instant or sorcery card in your
    graveyard gains flashback until end of turn. The flashback cost is equal
    to that card's mana cost.

    FDN collector number 51.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sphinx of Forgotten Lore")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}{U}"))
        kwargs.setdefault("subtypes", {"Sphinx"})
        kwargs.setdefault("keywords", Keyword.FLASH | Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flash\nFlying\nWhenever this creature attacks, target instant "
            "or sorcery card in your graveyard gains flashback until end of "
            "turn. The flashback cost is equal to that card's mana cost.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register attack trigger: grant flashback to instant/sorcery in graveyard."""
        from engine.triggers import EventType, TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _attack_condition(game: Any, data: dict) -> bool:
            attacker = data.get("attacker") or data.get("creature")
            return attacker is source

        def _attack_effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            eligible = [
                c for c in graveyard.get_all()
                if CardType.INSTANT in getattr(c, "card_types", set())
                or CardType.SORCERY in getattr(c, "card_types", set())
            ]
            if not eligible:
                return
            try:
                chosen = ctrl.choose_card(
                    eligible,
                    "Choose an instant or sorcery card to gain flashback",
                )
            except Exception:
                chosen = eligible[0] if eligible else None
            if chosen is not None:
                # ENGINE LIMITATION: Flashback is not natively supported.
                # We set a flag on the card and register end-of-turn cleanup.
                chosen.has_flashback = True
                chosen.flashback_cost = getattr(chosen, "mana_cost", None)

                # Register end-of-turn cleanup to remove flashback
                def _cleanup_flashback(game: Any, data: dict) -> bool:
                    return True

                def _remove_flashback(game: "GameState") -> None:
                    if hasattr(chosen, "has_flashback"):
                        chosen.has_flashback = False
                    if hasattr(chosen, "flashback_cost"):
                        del chosen.flashback_cost

                game.trigger_manager.register(TriggerRegistration(
                    event_type=EventType.END_OF_TURN,
                    condition=_cleanup_flashback,
                    effect=_remove_flashback,
                    source=source,
                    controller=ctrl,
                ))

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ATTACKS,
            condition=_attack_condition,
            effect=_attack_effect,
            source=self,
            controller=controller,
        ))
