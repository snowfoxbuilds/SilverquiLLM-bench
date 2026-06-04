"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_SPELL_TYPES = {
    CardType.CREATURE,
    CardType.INSTANT,
    CardType.SORCERY,
    CardType.ENCHANTMENT,
    CardType.ARTIFACT,
    CardType.PLANESWALKER,
}


def _mana_value(card: Any) -> int:
    mc = getattr(card, "mana_cost", None)
    return mc.cmc if mc is not None else 0


def _is_castable(card: Any) -> bool:
    return bool(getattr(card, "card_types", set()) & _SPELL_TYPES)


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson — Paradigm.

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells from
    among them without paying their mana costs.

    Paradigm (Then exile this spell. After you first resolve a spell with
    this name, you may cast a copy of it from exile without paying its mana
    cost at the beginning of each of your first main phases.)

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
            "spells from among them without paying their mana costs.\n"
            "Paradigm (Then exile this spell. After you first resolve a spell "
            "with this name, you may cast a copy of it from exile without "
            "paying its mana cost at the beginning of each of your first main "
            "phases.)",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        from engine.zones import move_to_zone

        ctrl = self.controller
        if ctrl is None:
            return

        self._exile_and_cast(game, ctrl)

        # Paradigm: the first time a spell with this name resolves, install the
        # delayed trigger that lets you recast a copy each precombat main phase.
        self._setup_paradigm(game, ctrl)

        # Paradigm: "Exile this spell" — redirect this card's own move from
        # the stack so it goes to exile rather than the graveyard.  Doing the
        # move here (while the card is still in the stack zone) means the
        # engine's subsequent STACK->GRAVEYARD move in ``_resolve_spell``
        # finds nothing to move and is a no-op.
        move_to_zone(game, self, Zone.STACK, Zone.EXILE)

    def _exile_and_cast(self, game: "GameState", ctrl: Any) -> None:
        from engine.casting import cast_spell_free
        from engine.game import exile as exile_card

        library = game.get_library(ctrl)
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top = library.top(1)
            if not top:
                break
            card = top[0]
            total_mv += _mana_value(card)
            exile_card(game, card)
            exiled.append(card)

        for card in exiled:
            if not _is_castable(card):
                continue
            if ctrl.choose_yes_no(
                f"Cast {getattr(card, 'name', 'spell')} from exile without "
                "paying its mana cost?"
            ):
                cast_spell_free(game, ctrl, card, Zone.EXILE)

    def _setup_paradigm(self, game: "GameState", ctrl: Any) -> None:
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration
        from engine.types import Phase

        resolved = getattr(game, "_paradigm_resolved", None)
        if resolved is None:
            resolved = set()
            game._paradigm_resolved = resolved  # type: ignore[attr-defined]
        key = (id(ctrl), self.name)
        if key in resolved:
            return  # already set up by an earlier spell with this name
        resolved.add(key)

        name = self.name

        def _condition(g: "GameState", event: Any) -> bool:
            return (
                getattr(event, "phase", None) == Phase.PRECOMBAT_MAIN
                and g.active_player is ctrl
            )

        def _effect(g: "GameState") -> None:
            self._paradigm_recast(g, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=ctrl,
            )
        )

    def _paradigm_recast(self, game: "GameState", ctrl: Any) -> None:
        from engine.casting import cast_spell_free

        copy = type(self)(owner=ctrl, controller=ctrl)
        game.get_exile(ctrl).add(copy)
        if ctrl.choose_yes_no(
            f"Paradigm — cast a copy of {self.name} from exile without paying "
            "its mana cost?"
        ):
            cast_spell_free(game, ctrl, copy, Zone.EXILE)
