"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}


def _instant_or_sorcery(card: Any) -> bool:
    return bool(getattr(card, "card_types", set()) & _SPELL_TYPES)


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 Legendary Avatar.

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost.  If that
    spell would be put into your graveyard, exile it instead.

    SOS collector number 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["keywords"] = (kwargs.get("keywords") or Keyword(0)) | Keyword.REACH
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery "
            "card in your graveyard.\nReach\nWhenever The Dawning Archaic "
            "attacks, you may cast target instant or sorcery card from your "
            "graveyard without paying its mana cost. If that spell would be "
            "put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """{1} less for each instant/sorcery card in your graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        return sum(
            1 for c in game.get_graveyard(controller).get_all()
            if _instant_or_sorcery(c)
        )

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger (free-cast from graveyard)."""
        from engine.triggers import TriggerRegistration
        from engine.events import AttacksTriggeredEvent

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(g: "GameState", event: Any) -> bool:
            return getattr(event, "creature", None) is source

        def _effect(g: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            graveyard = g.get_graveyard(ctrl)
            candidates = [c for c in graveyard.get_all() if _instant_or_sorcery(c)]
            if not candidates:
                return
            # "may" — optional.
            if not ctrl.choose_yes_no(
                "Cast an instant or sorcery from your graveyard for free?"
            ):
                return
            # Auto-select when there's a single legal target.
            if len(candidates) == 1:
                target = candidates[0]
            else:
                target = ctrl.choose_card(
                    candidates, "Choose an instant or sorcery to cast from your graveyard"
                )
            if target is None or not graveyard.contains(target):
                return
            _register_exile_instead(g, target)
            from engine.casting import cast_spell_free
            cast_spell_free(g, ctrl, target, Zone.GRAVEYARD)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )


def _register_exile_instead(game: "GameState", spell: Any) -> None:
    """Make *spell* exile (rather than be put into a graveyard) when it would
    next go to the graveyard from resolving."""
    from engine.events import SpellResolvesToGraveyardReplacementEvent
    from engine.replacement_effects import ReplacementEffect

    def _condition(g: "GameState", event: Any) -> bool:
        return getattr(event, "spell", None) is spell

    def _replacement(g: "GameState", event: Any) -> Any:
        event.destination = "exile"
        # One-shot: clean up so it cannot affect a later object.
        g.replacement_manager.unregister(spell)
        return event

    game.replacement_manager.register(
        ReplacementEffect(
            event_type=SpellResolvesToGraveyardReplacementEvent,
            source=spell,
            condition=_condition,
            replacement=_replacement,
            controller=getattr(spell, "controller", None),
        )
    )
