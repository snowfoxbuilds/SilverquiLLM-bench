"""Card implementation for Improvisation Capstone (sos_120)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with total
    mana value 4 or greater. You may cast any number of spells from among
    them without paying their mana costs.
    Paradigm (Then exile this spell. After you first resolve a spell with
    this name, you may cast a copy of it from exile without paying its mana
    cost at the beginning of each of your first main phases.)
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
            "paying its mana cost at the beginning of each of your first "
            "main phases.)",
        )
        super().__init__(**kwargs)
        self._paradigm_resolved: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """Exile from library until MV >= 4, offer free casts, then paradigm self-exile."""
        controller = self.controller
        if controller is None:
            return

        # --- Main effect ---
        exiled_cards = _exile_until_mv_threshold(game, controller, threshold=4)

        # Offer free casts for each exiled card
        for card in list(exiled_cards):
            exile_zone = controller.zones[Zone.EXILE]
            if not exile_zone.contains(card):
                continue
            want_cast = controller.choose_yes_no(
                f"Cast {getattr(card, 'name', 'card')} for free?"
            )
            if want_cast:
                exile_zone.remove(card)
                # Push a free-cast stack object
                _push_free_cast(game, controller, card)

        # --- Paradigm: self-exile ---
        # Move this spell from wherever it is (usually stack zone) to exile
        for p in game.players:
            if p.zones[Zone.STACK].contains(self):
                p.zones[Zone.STACK].remove(self)
                break
        owner = getattr(self, "owner", controller)
        if owner is None:
            owner = controller
        owner.zones[Zone.EXILE].add(self)

        # --- Paradigm: register main-phase copy trigger (once) ---
        if not self._paradigm_resolved:
            self._paradigm_resolved = True
            _register_paradigm_trigger(game, self, controller)


def _exile_until_mv_threshold(
    game: "GameState", player: Any, threshold: int
) -> list[Any]:
    """Exile cards from top of library until cumulative MV >= threshold."""
    library = player.zones[Zone.LIBRARY]
    exile = player.zones[Zone.EXILE]
    exiled: list[Any] = []
    total_mv = 0

    while total_mv < threshold:
        top = library.top(1)
        if not top:
            break
        card = top[0]
        mc = getattr(card, "mana_cost", None)
        card_mv = mc.cmc if mc is not None else 0
        library.remove(card)
        exile.add(card)
        exiled.append(card)
        total_mv += card_mv

    return exiled


def _push_free_cast(game: "GameState", player: Any, card: Any) -> None:
    """Push a StackObject that resolves *card* for free."""
    stack_zone = player.zones[Zone.STACK]
    stack_zone.add(card)
    card.controller = player
    if card.owner is None:
        card.owner = player

    def on_resolve_free(g: "GameState") -> None:
        card.on_resolve(g)
        # Move to appropriate zone after resolution
        if stack_zone.contains(card):
            stack_zone.remove(card)
        if CardType.CREATURE in getattr(card, "card_types", set()) or \
           CardType.ENCHANTMENT in getattr(card, "card_types", set()) or \
           CardType.ARTIFACT in getattr(card, "card_types", set()) or \
           CardType.PLANESWALKER in getattr(card, "card_types", set()):
            # Permanent → battlefield
            bf = game.get_battlefield(player)
            bf.add(card)
        else:
            # Non-permanent → graveyard
            owner = getattr(card, "owner", player)
            owner.zones[Zone.GRAVEYARD].add(card)

    stack_obj = StackObject(
        source=card,
        controller=player,
        on_resolve=on_resolve_free,
    )
    game.stack.push(stack_obj)


def _register_paradigm_trigger(
    game: "GameState", source: Any, controller: Any
) -> None:
    """Register the per-main-phase copy-cast trigger."""

    def condition(g: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
        return event.player is controller

    def effect(g: "GameState") -> None:
        """Offer to cast a copy of Improvisation Capstone from exile."""
        want_cast = controller.choose_yes_no(
            "Paradigm: Cast a copy of Improvisation Capstone for free?"
        )
        if not want_cast:
            return

        # Push a copy of the Capstone effect onto the stack
        copy_capstone = ImprovisationCapstone(owner=controller, controller=controller)
        # The copy doesn't re-trigger paradigm registration (use _paradigm_resolved)
        copy_capstone._paradigm_resolved = True

        stack_zone = controller.zones[Zone.STACK]
        stack_zone.add(copy_capstone)

        def copy_resolve(g2: "GameState") -> None:
            copy_capstone.on_resolve(g2)
            # Copy just disappears (no zone move needed — paradigm self-exiles it)

        stack_obj = StackObject(
            source=copy_capstone,
            controller=controller,
            on_resolve=copy_resolve,
        )
        g.stack.push(stack_obj)

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=BeginningOfMainPhaseTriggeredEvent,
            condition=condition,
            effect=effect,
            source=source,
            controller=controller,
        )
    )
