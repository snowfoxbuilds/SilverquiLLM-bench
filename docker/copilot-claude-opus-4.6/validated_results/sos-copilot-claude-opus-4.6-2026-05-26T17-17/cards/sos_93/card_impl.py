"""Card implementation for Postmortem Professor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, ActivatedAbility
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class _GraveyardAbility:
    """Represents the graveyard activated ability for Postmortem Professor."""

    def __init__(self, source: "PostmortemProfessor", game: "GameState") -> None:
        self.source = source
        self.game = game

    def can_activate(self, game: "GameState") -> bool:
        """Check if there's an instant or sorcery in the graveyard to exile."""
        controller = self.source.owner
        graveyard = game.get_graveyard(controller)
        for card in graveyard.get_all():
            if card is self.source:
                continue
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                return True
        return False


class PostmortemProfessor(Creature):
    """Postmortem Professor — {1}{B} — Creature — Zombie Warlock.

    2/2. This creature can't block.
    Whenever this creature attacks, each opponent loses 1 life and you gain 1 life.
    {1}{B}, Exile an instant or sorcery card from your graveyard: Return this
    card from your graveyard to the battlefield.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Postmortem Professor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", {"Zombie", "Warlock"})
        super().__init__(**kwargs)

    def can_block(self, game: Any = None) -> bool:
        """This creature can't block."""
        return False

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger."""
        controller = self.controller

        def _condition(g: "GameState", event: AttacksTriggeredEvent) -> bool:
            return event.creature is self or event.attacker is self

        def _effect(g: "GameState") -> None:
            # Each opponent loses 1 life, you gain 1 life
            for player in g.players:
                if player is not self.controller:
                    player.life -= 1
            self.controller.life += 1
            if hasattr(self.controller, "life_gained_this_turn"):
                self.controller.life_gained_this_turn += 1
            else:
                self.controller.life_gained_this_turn = 1

        game.trigger_manager.register(TriggerRegistration(
            event_type=AttacksTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))

    def get_activated_abilities(self, game: "GameState" = None) -> list[Any]:
        """Return the graveyard ability."""
        if game is None:
            return []
        return [_GraveyardAbility(self, game)]

    def activate_ability(self, game: "GameState", ability_index: int = 0,
                         costs_paid: bool = False, targets: list[Any] | None = None) -> None:
        """Activate graveyard ability: exile instant/sorcery, return self to battlefield."""
        controller = self.owner
        graveyard = game.get_graveyard(controller)

        if not targets:
            return

        exile_target = targets[0]
        card_types = getattr(exile_target, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return

        # Exile the instant/sorcery
        if graveyard.contains(exile_target):
            graveyard.remove(exile_target)
            game.get_exile(controller).add(exile_target)

        # Return self from graveyard to battlefield
        if graveyard.contains(self):
            graveyard.remove(self)
            bf = game.get_battlefield(controller)
            bf.add(self)
            self.controller = controller
            # Register triggers on entering battlefield
            self.register_triggers(game)
