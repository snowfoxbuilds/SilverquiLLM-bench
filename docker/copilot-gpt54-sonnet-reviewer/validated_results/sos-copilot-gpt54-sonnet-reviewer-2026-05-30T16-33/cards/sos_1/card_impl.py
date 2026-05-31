"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.casting import cast_spell_free
from engine.events import AttacksTriggeredEvent, MoveToGraveyardReplacementEvent
from engine.replacement_effects import ReplacementEffect
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery card "
            "in your graveyard.\n"
            "Reach\n"
            "Whenever The Dawning Archaic attacks, you may cast target instant or "
            "sorcery card from your graveyard without paying its mana cost. If that "
            "spell would be put into your graveyard, exile it instead.",
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
        controller = getattr(self, "controller", None) or getattr(self, "owner", None)
        if controller is None:
            return

        def _condition(game: GameState, event: AttacksTriggeredEvent) -> bool:
            return event.creature is source or event.attacker is source

        def _effect(game: GameState) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            legal_spells = [
                card
                for card in game.get_graveyard(ctrl).get_all()
                if CardType.INSTANT in getattr(card, "card_types", set())
                or CardType.SORCERY in getattr(card, "card_types", set())
            ]
            if not legal_spells:
                return

            chosen = ctrl.choose_card(
                legal_spells,
                "Choose an instant or sorcery card in your graveyard to cast",
            )
            if chosen not in legal_spells:
                return
            if not ctrl.choose_yes_no(
                f"Cast {getattr(chosen, 'name', 'that card')} without paying its mana cost?"
            ):
                return

            replacement_source = object()

            def _replacement_condition(
                game: GameState,
                event: MoveToGraveyardReplacementEvent,
            ) -> bool:
                return event.card is chosen

            def _replacement(
                game: GameState,
                event: MoveToGraveyardReplacementEvent,
            ) -> MoveToGraveyardReplacementEvent:
                event.destination = "exile"
                game.replacement_manager.unregister(replacement_source)
                return event

            game.replacement_manager.register(
                ReplacementEffect(
                    event_type=MoveToGraveyardReplacementEvent,
                    source=replacement_source,
                    condition=_replacement_condition,
                    replacement=_replacement,
                    controller=ctrl,
                )
            )

            try:
                cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)
            except Exception:
                game.replacement_manager.unregister(replacement_source)
                raise

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
