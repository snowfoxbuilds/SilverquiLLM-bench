"""Card implementation for Improvisation Capstone (SOS #120)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson (Mythic).

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
        kw = kwargs.get("keywords", Keyword(0))
        kwargs["keywords"] = kw
        # Store non-evergreen keyword names in a separate set.
        self.keyword_names: set[str] = {"Paradigm"}
        # Track whether the recurring Paradigm trigger has been registered.
        self._paradigm_registered: bool = False
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Resolve the main effect then apply Paradigm."""
        controller = getattr(self, "controller", None)
        owner = getattr(self, "owner", controller)
        if controller is None:
            controller = owner
        if controller is None:
            return

        # --- Main effect: exile until total MV ≥ 4 ---
        exiled: list[Any] = []
        total_mv = 0
        library = game.get_library(controller)
        while total_mv < 4:
            all_cards = library.get_all()
            if not all_cards:
                break
            top_card = all_cards[-1]
            library.remove(top_card)
            exile_zone = game.get_exile(controller)
            exile_zone.add(top_card)
            exiled.append(top_card)
            mc = getattr(top_card, "mana_cost", None)
            mv = mc.cmc if mc is not None else 0
            total_mv += mv

        # --- Let the player cast any number from exiled cards for free ---
        from engine.casting import cast_spell_free
        from engine.player import ScriptExhaustedError

        castable = [
            c for c in exiled
            if CardType.LAND not in getattr(c, "card_types", set())
        ]
        for card in castable:
            try:
                want_cast = controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} without paying its mana cost?"
                )
            except ScriptExhaustedError:
                want_cast = False
            if want_cast:
                try:
                    cast_spell_free(game, controller, card, Zone.EXILE)
                except Exception:
                    pass

        # --- Paradigm: exile this spell instead of going to graveyard ---
        _paradigm_exile_self(game, self, controller, owner)

        # --- Paradigm: register recurring trigger on first resolution ---
        if not self._paradigm_registered:
            self._paradigm_registered = True
            _register_paradigm_trigger(game, self, controller)


# ---------------------------------------------------------------------------
# Paradigm helper functions
# ---------------------------------------------------------------------------

def _paradigm_exile_self(
    game: "GameState",
    card: Any,
    controller: Any,
    owner: Any,
) -> None:
    """Move *card* from the stack zone to exile (Paradigm self-exile)."""
    stack_zone: Any = None
    for player in game.players:
        if player.zones[Zone.STACK].contains(card):
            stack_zone = player.zones[Zone.STACK]
            break
    if stack_zone is not None:
        stack_zone.remove(card)
        exile_player = owner if owner is not None else controller
        game.get_exile(exile_player).add(card)


def _register_paradigm_trigger(
    game: "GameState",
    source_card: Any,
    controller: Any,
) -> None:
    """Register a recurring trigger to offer a free copy cast each first main phase."""
    from engine.events import BeginningOfMainPhaseTriggeredEvent
    from engine.triggers import TriggerRegistration
    from engine.types import Phase

    def _condition(game: Any, event: Any) -> bool:
        return (
            game.active_player is controller
            and game.phase == Phase.PRECOMBAT_MAIN
        )

    def _effect(game: Any) -> None:
        from engine.casting import cast_spell_free
        from engine.player import ScriptExhaustedError

        try:
            want_cast = controller.choose_yes_no(
                "Cast a copy of Improvisation Capstone without paying its mana cost?"
            )
        except ScriptExhaustedError:
            want_cast = False

        if not want_cast:
            return

        # Create a fresh copy (already marked so it won't re-register).
        copy = ImprovisationCapstone(owner=controller, controller=controller)
        copy._paradigm_registered = True

        exile_zone = game.get_exile(controller)
        exile_zone.add(copy)

        try:
            cast_spell_free(game, controller, copy, Zone.EXILE)
        except Exception:
            exile_zone.remove(copy)

    reg = TriggerRegistration(
        event_type=BeginningOfMainPhaseTriggeredEvent,
        condition=_condition,
        effect=_effect,
        source=source_card,
        controller=controller,
    )
    game.trigger_manager.register(reg)
