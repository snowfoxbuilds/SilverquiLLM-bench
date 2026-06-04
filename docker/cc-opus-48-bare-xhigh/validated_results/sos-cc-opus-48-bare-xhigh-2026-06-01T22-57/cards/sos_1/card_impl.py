"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


def _instant_sorcery_in_graveyard(player: Any) -> list[Any]:
    if player is None:
        return []
    gy = player.zones[Zone.GRAVEYARD]
    return [c for c in gy.get_all() if _is_instant_or_sorcery(c)]


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Avatar.

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.
    Reach.
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost. If that
    spell would be put into your graveyard, exile it instead.

    SOS collector number 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Avatar"}
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery "
            "card in your graveyard.\nReach\n"
            "Whenever The Dawning Archaic attacks, you may cast target "
            "instant or sorcery card from your graveyard without paying its "
            "mana cost. If that spell would be put into your graveyard, "
            "exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """{1} less for each instant/sorcery card in your graveyard."""
        return len(_instant_sorcery_in_graveyard(self.controller))

    def register_triggers(self, game: "GameState") -> None:
        """On attack, may free-cast an instant/sorcery from the graveyard."""
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: "GameState", event: AttacksTriggeredEvent) -> bool:
            return getattr(event, "creature", None) is source

        def _effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free

            controller = source.controller
            if controller is None:
                return
            candidates = _instant_sorcery_in_graveyard(controller)
            if not candidates:
                return
            if not controller.choose_yes_no(
                "Cast an instant or sorcery from your graveyard for free?"
            ):
                return
            chosen = controller.choose_card(
                candidates, "Choose an instant or sorcery to cast from your graveyard"
            )
            if chosen is None or chosen not in candidates:
                return
            # If this spell would hit the graveyard, exile it instead.
            chosen._replace_graveyard_with_exile = True
            try:
                cast_spell_free(game, controller, chosen, Zone.GRAVEYARD)
            except Exception:
                # Casting failed (e.g. no legal targets) — clear the flag.
                chosen._replace_graveyard_with_exile = False

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
