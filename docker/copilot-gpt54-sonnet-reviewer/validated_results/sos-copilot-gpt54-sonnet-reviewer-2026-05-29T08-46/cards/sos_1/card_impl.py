"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent, MoveToGraveyardReplacementEvent
from engine.replacement_effects import ReplacementEffect
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic."""

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

    def cost_reduction(self, game: GameState) -> int:
        controller = self.controller
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        return sum(
            1
            for card in graveyard.get_all()
            if CardType.INSTANT in getattr(card, "card_types", set())
            or CardType.SORCERY in getattr(card, "card_types", set())
        )

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: GameState, event: AttacksTriggeredEvent) -> bool:
            return event.creature is source

        def _choose_targets(game: GameState, event: AttacksTriggeredEvent, player: Any) -> list[Any] | None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return None
            legal_cards = [
                card
                for card in game.get_graveyard(ctrl).get_all()
                if CardType.INSTANT in getattr(card, "card_types", set())
                or CardType.SORCERY in getattr(card, "card_types", set())
            ]
            if not legal_cards:
                return None
            requirement = TargetRequirement(
                filter_fn=lambda obj: obj in legal_cards,
                description="target instant or sorcery card in your graveyard",
                zone=Zone.GRAVEYARD,
            )
            chosen = player.choose_target(legal_cards, requirement)
            if chosen not in legal_cards:
                return None
            return [chosen]

        def _effect(game: GameState) -> None:
            from engine.casting import cast_spell_free

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            chosen_targets = getattr(source, "chosen_targets", [])
            if not chosen_targets:
                return

            spell = chosen_targets[0]
            graveyard = game.get_graveyard(ctrl)
            if not graveyard.contains(spell):
                return

            if not ctrl.choose_yes_no(
                f"Cast {getattr(spell, 'name', 'that spell')} without paying its mana cost?"
            ):
                return

            cast_spell_free(game, ctrl, spell, Zone.GRAVEYARD)

            def _replacement(game: GameState, event: MoveToGraveyardReplacementEvent) -> MoveToGraveyardReplacementEvent:
                event.destination = "exile"
                return event

            game.replacement_manager.register(
                ReplacementEffect(
                    event_type=MoveToGraveyardReplacementEvent,
                    source=spell,
                    condition=lambda game, event: event.card is spell,
                    replacement=_replacement,
                    controller=ctrl,
                )
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                choose_targets=_choose_targets,
            )
        )
