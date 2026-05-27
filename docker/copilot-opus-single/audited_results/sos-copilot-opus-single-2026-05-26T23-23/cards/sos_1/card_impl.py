"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

    This spell costs {1} less to cast for each instant and sorcery card
    in your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost. If that
    spell would be put into your graveyard, exile it instead.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery card in your graveyard.\n"
            "Reach\n"
            "Whenever The Dawning Archaic attacks, you may cast target instant or sorcery card "
            "from your graveyard without paying its mana cost. If that spell would be put into "
            "your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Return {1} reduction for each instant/sorcery in controller's graveyard."""
        controller = self.controller or self.owner
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        count = 0
        for card in graveyard.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                count += 1
        return count

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger."""
        source = self
        controller = self.controller or self.owner or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            """Fire when this creature attacks."""
            creature = getattr(event, "creature", None) or getattr(event, "attacker", None)
            return creature is source

        def _effect(game: "GameState") -> None:
            """Cast target instant/sorcery from graveyard, exile instead of GY."""
            chosen = getattr(source, "chosen_targets", None)
            if not chosen:
                return
            target_card = chosen[0]
            ctrl = source.controller or source.owner
            if ctrl is None:
                return
            graveyard = game.get_graveyard(ctrl)
            exile = game.get_exile(ctrl)
            # Move from graveyard to exile (simulating cast + exile replacement)
            if graveyard.contains(target_card):
                graveyard.remove(target_card)
                exile.add(target_card)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

