"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _card_cmc(card: Any) -> int:
    mana_cost = getattr(card, "mana_cost", None)
    if mana_cost is None:
        return 0
    return int(getattr(mana_cost, "cmc", 0) or 0)


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

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
        self.colors = ["R"]
        # A paradigm copy only performs the dig — it does not re-exile itself
        # nor set up another recurring paradigm trigger.
        self._is_paradigm_copy: bool = False

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return
        self._run_dig(game, controller)
        if not self._is_paradigm_copy:
            # Paradigm: exile this spell instead of putting it in the
            # graveyard, then offer a free copy each first main phase.
            self._exile_instead_of_graveyard = True
            self._setup_paradigm(game, controller)

    def _run_dig(self, game: "GameState", controller: "Player") -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.player import ScriptExhaustedError

        library = controller.zones[Zone.LIBRARY]
        exile_zone = controller.zones[Zone.EXILE]

        exiled: list[Any] = []
        total = 0
        while total < 4:
            cards = list(library.get_all())
            if not cards:
                break
            top = cards[-1]
            library.remove(top)
            exile_zone.add(top)
            exiled.append(top)
            total += _card_cmc(top)

        # You may cast any number of spells from among the exiled cards.
        for card in exiled:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            if not exile_zone.contains(card):
                continue
            try:
                if not controller.choose_yes_no(
                    f"cast {getattr(card, 'name', 'card')} for free?"
                ):
                    continue
            except (ScriptExhaustedError, NotImplementedError):
                continue
            try:
                cast_spell_free(game, controller, card, Zone.EXILE)
            except CastingError:
                pass

    def _setup_paradigm(self, game: "GameState", controller: "Player") -> None:
        from engine.events import MainPhaseBeganTriggeredEvent
        from engine.triggers import TriggerRegistration
        from engine.types import Phase

        source = self

        def _condition(
            g: "GameState", event: MainPhaseBeganTriggeredEvent
        ) -> bool:
            if getattr(event, "player", None) is not controller:
                return False
            if getattr(g, "phase", None) != Phase.PRECOMBAT_MAIN:
                return False
            return controller.zones[Zone.EXILE].contains(source)

        def _effect(g: "GameState") -> None:
            from engine.player import ScriptExhaustedError

            if not controller.zones[Zone.EXILE].contains(source):
                return
            try:
                if not controller.choose_yes_no(
                    "cast a copy of Improvisation Capstone from exile?"
                ):
                    return
            except (ScriptExhaustedError, NotImplementedError):
                return
            copy = ImprovisationCapstone()
            copy.controller = controller
            copy.owner = controller
            copy._is_paradigm_copy = True
            copy.on_resolve(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=MainPhaseBeganTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
