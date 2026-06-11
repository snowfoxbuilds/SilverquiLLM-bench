"""Card implementation for Abigale, Poet Laureate // Heroic Stanza."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class HeroicStanza(Sorcery):
    """Prepared spell copy for Abigale."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Heroic Stanza")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W/B}"))
        kwargs.setdefault("rules_text", "Prepared spell copy.")
        super().__init__(**kwargs)


class AbigalePoetLaureateHeroicStanza(Creature):
    """Abigale, Poet Laureate."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Abigale, Poet Laureate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{B}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Bird", "Bard"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def create_prepared_spell_copy(self) -> Sorcery:
        return HeroicStanza(owner=self.owner, controller=self.controller)

    def register_triggers(self, game: GameState) -> None:
        if any(
            trigger.event_type is SpellCastTriggeredEvent
            for trigger in game.trigger_manager.get_triggers_for_source(self)
        ):
            return

        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and source.is_on_battlefield(g)
                and spell is not None
                and CardType.CREATURE in getattr(spell, "card_types", set())
            )

        def _effect(g: GameState) -> None:
            if source.is_on_battlefield(g):
                source.become_prepared()

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
