"""Card implementation for Cauldron of Essence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Artifact, Creature
from benchmarks.sos.workspace.engine.casting import is_sorcery_speed
from benchmarks.sos.workspace.engine.events import (
    CreatureDiesTriggeredEvent,
    GainsLifeTriggeredEvent,
    LosesLifeTriggeredEvent,
)
from benchmarks.sos.workspace.engine.game import sacrifice
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class CauldronOfEssence(Artifact):
    """Cauldron of Essence."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cauldron of Essence")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{G}"))
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: CreatureDiesTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.controller is current_controller
                and source.is_on_battlefield(g)
            )

        def _effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            for player in g.players:
                if player is not current_controller:
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
                event_type=CreatureDiesTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _target_requirement() -> TargetRequirement:
            controller = source.controller
            return TargetRequirement(
                filter_fn=lambda obj, current_controller=controller: (
                    isinstance(obj, Creature)
                    and current_controller is not None
                    and getattr(obj, "owner", None) is current_controller
                ),
                description="target creature card from your graveyard",
                zone=Zone.GRAVEYARD,
            )

        def _cost(game: GameState, artifact: Artifact) -> bool:  # noqa: ARG001
            controller = source.controller
            if controller is None or source.is_tapped or not is_sorcery_speed(game, controller):
                return False
            mana_cost = ManaCost.parse("{1}{B}{G}")
            if not controller.mana_pool.can_pay(mana_cost):
                return False
            creatures = [
                permanent
                for permanent in game.get_battlefield(controller).get_all()
                if isinstance(permanent, Creature)
            ]
            if not creatures:
                return False
            try:
                chosen = controller.choose_card(creatures, "creature to sacrifice")
            except Exception:
                chosen = creatures[0]
            if chosen not in creatures:
                return False
            controller.mana_pool.pay(mana_cost)
            source.is_tapped = True
            sacrifice(game, controller, chosen)
            return True

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            chosen_targets = list(getattr(source, "chosen_targets", []))
            target = chosen_targets[0] if chosen_targets else None
            requirement = _target_requirement()
            if target is None:
                candidates = [
                    card
                    for card in game.get_graveyard(controller).get_all()
                    if requirement.filter_fn(card)
                ]
                if not candidates:
                    return
                try:
                    target = controller.choose_target(candidates, requirement)
                except Exception:
                    target = candidates[0]
                if target not in candidates:
                    target = candidates[0]
                source.chosen_targets = [target]
            if not isinstance(target, Creature):
                return
            if not game.get_graveyard(controller).contains(target):
                return
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        ability = ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{1}{B}{G}, {T}, Sacrifice a creature: Return target creature card from your graveyard to the battlefield. Activate only as a sorcery.",
        )
        ability.target_requirements = [_target_requirement()]  # type: ignore[attr-defined]
        return [ability]
