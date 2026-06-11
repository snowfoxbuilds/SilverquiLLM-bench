"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells from
    among them without paying their mana costs.
    Paradigm (Then exile this spell. After you first resolve a spell with
    this name, you may cast a copy of it from exile without paying its
    mana cost at the beginning of each of your first main phases.)

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
            "Paradigm (Then exile this spell. After you first resolve a "
            "spell with this name, you may cast a copy of it from exile "
            "without paying its mana cost at the beginning of each of your "
            "first main phases.)",
        )
        super().__init__(**kwargs)
        self._paradigm_registered: bool = False

    def on_resolve(self, game: "GameState") -> None:
        from engine.casting import CastingError, cast_spell_free
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # 1. Exile from the top of the library until total mana value >= 4
        #    (or the library runs out).
        library = controller.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total_mv = 0
        while total_mv < 4 and len(library) > 0:
            top_card = library.top(1)[0]
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.EXILE)
            exiled.append(top_card)
            total_mv += getattr(top_card, "mana_cost", ManaCost()).cmc

        # 2. May cast any number of them for free (lands are not castable
        #    and stay exiled — Etali/fdn_194 pattern).
        for card in exiled:
            if CardType.LAND in getattr(card, "card_types", set()):
                continue
            try:
                if controller.choose_yes_no(
                    f"Cast {getattr(card, 'name', 'card')} without paying its mana cost?"
                ):
                    cast_spell_free(game, controller, card, Zone.EXILE)
            except CastingError:
                continue

        # 3. Paradigm — "Then exile this spell."  Move out of the stack zone
        #    now; the engine's stack→graveyard move afterwards becomes a
        #    no-op because the card is no longer in the stack zone.
        for player in game.players:
            if player.zones[Zone.STACK].contains(self):
                move_to_zone(game, self, Zone.STACK, Zone.EXILE)
                break

        # 4. Paradigm — recurring "beginning of each of your first main
        #    phases" cast-a-copy offer, registered on first resolution only
        #    (copies inherit the flag and don't re-register).
        if not self._paradigm_registered:
            self._paradigm_registered = True
            self._register_paradigm_trigger(game, controller)

    def _register_paradigm_trigger(self, game: "GameState", controller: Any) -> None:
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: Any, event: Any) -> bool:
            return g.active_player is controller

        def _effect(g: "GameState") -> None:
            from engine.casting import CastingError, cast_spell_free

            exile_zone = controller.zones[Zone.EXILE]
            if not exile_zone.contains(source):
                return
            if not controller.choose_yes_no(
                f"Cast a copy of {source.name} from exile without paying its mana cost?"
            ):
                return
            # Cast a *copy* — the Capstone card itself stays in exile.
            spell_copy = copy.copy(source)
            spell_copy.owner = spell_copy.controller = controller
            exile_zone.add(spell_copy)
            try:
                cast_spell_free(g, controller, spell_copy, Zone.EXILE)
            except CastingError:
                exile_zone.remove(spell_copy)
                return

            # A resolved spell copy ceases to exist (rule 707.10a): after it
            # resolves, remove the copy object from whatever zone it landed in
            # (graveyard normally; exile via its own Paradigm clause).
            copy_so = g.stack.peek()
            if copy_so is None or copy_so.source is not spell_copy:
                return
            original_resolve = copy_so.on_resolve

            def _resolve_then_vanish(gg: "GameState") -> None:
                original_resolve(gg)
                for player in gg.players:
                    for zone in (Zone.GRAVEYARD, Zone.EXILE):
                        container = player.zones[zone]
                        if container.contains(spell_copy):
                            container.remove(spell_copy)
                            return

            copy_so.on_resolve = _resolve_then_vanish

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
