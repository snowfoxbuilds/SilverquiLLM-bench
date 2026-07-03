"""Card implementation for Nita, Forum Conciliator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.casting import is_sorcery_speed
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter, sacrifice
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Supertype, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class NitaForumConciliator(Creature):
    """Nita, Forum Conciliator."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Nita, Forum Conciliator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{B}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Human", "Advisor"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and spell is not None
                and getattr(spell, "owner", None) is not current_controller
                and source.is_on_battlefield(g)
            )

        def _effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            for permanent in g.get_battlefield(current_controller).get_all():
                if isinstance(permanent, Creature) and getattr(permanent, "controller", None) is current_controller:
                    add_counter(g, permanent, "+1/+1")

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self
        activation_cost = ManaCost.parse("{2}")

        def _target_requirement() -> TargetRequirement:
            controller = getattr(source, "controller", None)
            return TargetRequirement(
                filter_fn=lambda card, current_controller=controller: isinstance(card, (Instant, Sorcery))
                and getattr(card, "owner", None) is not None
                and getattr(card, "owner", None) is not current_controller,
                description="target instant or sorcery card from an opponent's graveyard",
                zone=Zone.GRAVEYARD,
            )

        def _cost(game: GameState, card: Creature) -> bool:
            controller = getattr(source, "controller", None)
            if controller is None or card is not source:
                return False
            if not source.is_on_battlefield(game) or not is_sorcery_speed(game, controller):
                return False
            sacrifices = [
                permanent
                for permanent in game.get_battlefield(controller).get_all()
                if isinstance(permanent, Creature) and permanent is not source
            ]
            if not sacrifices or not controller.mana_pool.can_pay(activation_cost):
                return False
            chosen = controller.choose_card(sacrifices, "Choose another creature to sacrifice")
            if chosen not in sacrifices:
                return False
            controller.mana_pool.pay(activation_cost)
            sacrifice(game, controller, chosen)
            return True

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            target = getattr(source, "chosen_targets", [None])[0] if getattr(source, "chosen_targets", None) else None
            if controller is None or not isinstance(target, (Instant, Sorcery)):
                return
            if source.is_on_battlefield(game) and not game.trigger_manager.get_triggers_for_source(source):
                source.register_triggers(game)
            if getattr(target, "owner", None) is controller:
                return
            owner = getattr(target, "owner", None)
            if owner is None or not game.get_graveyard(owner).contains(target):
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.EXILE)
            target._cast_with_any_mana_as_any_type = True
            target._exile_after_exile_cast = True
            game.grant_exile_play_permission_until_end_of_turn(controller, target, source=source)

        ability = ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description=(
                "{2}, Sacrifice another creature: Exile target instant or sorcery card from an "
                "opponent's graveyard. You may cast it this turn, and mana of any type can be "
                "spent to cast that spell. If that spell would be put into a graveyard, exile it "
                "instead. Activate only as a sorcery."
            ),
        )
        ability.target_requirements = [_target_requirement()]  # type: ignore[attr-defined]
        return [ability]
