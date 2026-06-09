"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import BeginningOfPrecombatMainTriggeredEvent
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _cmc(card: Any) -> int:
    cost = getattr(card, "mana_cost", None)
    return cost.cmc if cost is not None else 0


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with total
    mana value 4 or greater. You may cast any number of spells from among them
    without paying their mana costs.
    Paradigm (Then exile this spell. After you first resolve a spell with this
    name, you may cast a copy of it from exile without paying its mana cost at
    the beginning of each of your first main phases.)

    SOS collector number 120.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards "
            "with total mana value 4 or greater. You may cast any number of "
            "spells from among them without paying their mana costs.\nParadigm",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------

    def _peel_and_cast(self, game: "GameState", ctrl: Any) -> None:
        from engine.casting import cast_spell_free
        from engine.zones import move_to_zone

        lib = game.get_library(ctrl)
        exiled: list[Any] = []
        total = 0
        while total < 4 and len(lib) > 0:
            top = lib.top(1)[0]
            move_to_zone(game, top, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top)
            total += _cmc(top)

        for card in exiled:
            # Lands (and other noncastable cards) can't be cast; they stay exiled.
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            if not game.get_exile(ctrl).contains(card):
                continue
            if ctrl.choose_yes_no(f"Cast {card.name} without paying its mana cost?"):
                cast_spell_free(game, ctrl, card, Zone.EXILE)

    def on_resolve(self, game: "GameState") -> None:
        ctrl = self.controller
        if ctrl is None:
            return
        self._peel_and_cast(game, ctrl)

        # Paradigm copies only re-run the peel effect; they do not re-arm
        # Paradigm or move the original out of exile.
        if getattr(self, "_is_paradigm_copy", False):
            return

        self._setup_paradigm(game, ctrl)

    # ------------------------------------------------------------------
    # Paradigm
    # ------------------------------------------------------------------

    def _setup_paradigm(self, game: "GameState", ctrl: Any) -> None:
        from engine.triggers import TriggerRegistration
        from engine.zones import move_to_zone

        source = self
        # "Then exile this spell." (instead of going to the graveyard)
        if game.get_graveyard(ctrl).contains(self) or ctrl.zones[Zone.STACK].contains(self):
            move_to_zone(game, self, Zone.STACK, Zone.EXILE)

        def _condition(game: Any, event: Any) -> bool:
            return game.active_player is getattr(source, "controller", ctrl)

        def _effect(game: "GameState") -> None:
            from engine.stack import StackObject, copy_spell

            owner = getattr(source, "controller", ctrl)
            if owner is None or not game.get_exile(owner).contains(source):
                return
            # "you may cast a copy of it from exile"
            if not owner.choose_yes_no(
                "Cast a copy of Improvisation Capstone from exile?"
            ):
                return
            temp = StackObject(source=source, controller=owner, targets=[])
            copy_obj = copy_spell(game, temp, owner)
            copy_obj.source._is_paradigm_copy = True
            game.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=ctrl,
            )
        )
