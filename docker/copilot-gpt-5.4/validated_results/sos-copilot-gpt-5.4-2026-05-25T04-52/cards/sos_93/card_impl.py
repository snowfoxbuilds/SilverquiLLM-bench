"""Card implementation for Postmortem Professor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.events import (
    AttacksTriggeredEvent,
    GainsLifeTriggeredEvent,
    LosesLifeTriggeredEvent,
)
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class PostmortemProfessor(Creature):
    """Postmortem Professor."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Postmortem Professor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("subtypes", {"Zombie", "Warlock"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "This creature can't block.\nWhenever this creature attacks, each opponent loses 1 life "
            "and you gain 1 life.\n{1}{B}, Exile an instant or sorcery card from your graveyard: "
            "Return this card from your graveyard to the battlefield.",
        )
        super().__init__(**kwargs)
        self._cant_block = True

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        self._cant_block = True

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(_game: GameState, event: AttacksTriggeredEvent) -> bool:
            return event.creature is source or event.attacker is source

        def _effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            for player in g.players:
                if player is current_controller:
                    continue
                player.life -= 1
                g.trigger_manager.fire_event(
                    g,
                    LosesLifeTriggeredEvent(player=player, amount=1),
                )
            current_controller.life += 1
            current_controller.life_gained_this_turn = (
                getattr(current_controller, "life_gained_this_turn", 0) + 1
            )
            g.trigger_manager.fire_event(
                g,
                GainsLifeTriggeredEvent(player=current_controller, amount=1),
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self
        activation_cost = ManaCost.parse("{1}{B}")

        def _cost(game: GameState, card: Creature) -> bool:
            owner = getattr(card, "owner", None)
            if owner is None or not game.get_graveyard(owner).contains(card):
                return False
            if not owner.mana_pool.can_pay(activation_cost):
                return False

            graveyard = game.get_graveyard(owner)
            candidates = [
                candidate
                for candidate in graveyard.get_all()
                if candidate is not card
                and (
                    CardType.INSTANT in getattr(candidate, "card_types", set())
                    or CardType.SORCERY in getattr(candidate, "card_types", set())
                )
            ]
            if not candidates:
                return False
            try:
                chosen = owner.choose_card(
                    candidates,
                    "instant or sorcery card to exile",
                )
            except Exception:
                chosen = candidates[0]
            if chosen not in candidates:
                chosen = candidates[0]

            owner.mana_pool.pay(activation_cost)
            move_to_zone(game, chosen, Zone.GRAVEYARD, Zone.EXILE)
            return True

        def _effect(game: GameState) -> None:
            owner = getattr(source, "owner", None)
            if owner is None or not game.get_graveyard(owner).contains(source):
                return
            source.controller = owner
            move_to_zone(game, source, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{1}{B}, Exile an instant or sorcery card from your graveyard: Return this "
                    "card from your graveyard to the battlefield."
                ),
            )
        ]
