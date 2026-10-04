"""Card implementation for Nine-Lives Familiar."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ArtifactCreature, Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from engine.events import CreatureDiesTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState
    from cards.registry import CardRegistry


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class NineLivesFamiliarAbility1:
    text = 'This creature enters with eight revival counters on it if you cast it.'


class NineLivesFamiliarAbility2:
    text = 'When this creature dies, if it had a revival counter on it, return it to the battlefield with one fewer revival counter on it at the beginning of the next end step.'


# endregion Printed abilities


class NineLivesFamiliar(Creature):
    """Nine-Lives Familiar — {1}{B}{B} — 1/1 — Cat

    This creature enters with eight revival counters on it if you cast it.
    When this creature dies, if it had a revival counter on it, return it
    to the battlefield with one fewer revival counter on it at the
    beginning of the next end step.

    FDN collector number 66.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Nine-Lives Familiar')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{B}{B}'))
        kwargs.setdefault('subtypes', {'Cat'})
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 1)
        kwargs.setdefault('rules_text', 'This creature enters with eight revival counters on it if you cast it.\nWhen this creature dies, if it had a revival counter on it, return it to the battlefield with one fewer revival counter on it at the beginning of the next end step.')
        super().__init__(**kwargs)

    def enters_battlefield_with(self, game: GameState, event: Any) -> None:
        """Enters with eight revival counters if you cast it (rule 614.1c).

        "If you cast it" — the creature entering from the stack, i.e. a resolved
        cast. A return via the dies-trigger enters from the graveyard and gets
        no fresh revival counters (it keeps the one-fewer count it left with),
        so the ``from_zone`` check replaces the old ``_returning_from_graveyard``
        flag. Revival counters live in the engine counter system (readable via
        ``.counters``), not a card-private attribute.
        """
        if event.from_zone == Zone.STACK:
            event.counters['revival'] = event.counters.get('revival', 0) + 8

    def register_triggers(self, game: GameState) -> None:
        from engine.events import EndStepTriggeredEvent
        from engine.stack import object_stint_id
        from engine.triggers import TriggerRegistration, register_delayed_trigger
        from engine.zones import move_to_zone
        source = self

        def _revival(event: Any) -> int:
            # It "had" a revival counter as it last existed (rule 603.10a).
            lki = event.last_known
            return lki.counters.get('revival', 0) if lki is not None else 0

        def _dies_condition(game: Any, event: Any) -> bool:
            return event.creature is source and _revival(event) > 0

        def _capture(game: Any, event: Any, controller: Any) -> tuple[int, int | None]:
            # The card that died is the graveyard object of this stint; if it
            # leaves the graveyard it is not returned (rule 603.7c).
            return _revival(event), object_stint_id(game, source)

        def _dies_effect(game: GameState, controller: Any, state: tuple[int, int | None]) -> None:
            revival, stint = state

            def _return(game: GameState) -> None:
                owner = source.owner
                if owner is None or not owner.zones[Zone.GRAVEYARD].contains(source):
                    return
                if object_stint_id(game, source) != stint:
                    return
                move_to_zone(
                    game, source, Zone.GRAVEYARD, Zone.BATTLEFIELD,
                    with_counters={'revival': revival - 1} if revival > 1 else None,
                )

            # "at the beginning of the next end step" (rule 603.7a).
            register_delayed_trigger(
                game, EndStepTriggeredEvent, controller, _return,
                name='Nine-Lives Familiar return',
            )

        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=CreatureDiesTriggeredEvent, condition=_dies_condition, effect=_dies_effect, source=self, controller=controller, capture=_capture))
