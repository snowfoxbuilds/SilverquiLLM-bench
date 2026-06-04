"""Card implementation for The Dawning Archaic (SOS 1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    """Return ``True`` if *card* is an instant or sorcery card."""
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

    - This spell costs {1} less to cast for each instant and sorcery card in
      your graveyard.
    - Reach.
    - Whenever The Dawning Archaic attacks, you may cast target instant or
      sorcery card from your graveyard without paying its mana cost. If that
      spell would be put into your graveyard, exile it instead.

    SOS collector number 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.REACH)
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

    # ------------------------------------------------------------------
    # Cost reduction
    # ------------------------------------------------------------------

    def cost_reduction(self, game: "GameState") -> int:
        """Reduce generic mana by 1 for each instant/sorcery in your graveyard."""
        controller = getattr(self, "controller", None) or getattr(self, "owner", None)
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        return sum(1 for card in graveyard.get_all() if _is_instant_or_sorcery(card))

    # ------------------------------------------------------------------
    # Targeting (for the attack trigger)
    # ------------------------------------------------------------------

    def _graveyard_target_requirement(self) -> "TargetRequirement":
        """Build the attack trigger's graveyard instant/sorcery requirement."""
        return TargetRequirement(
            filter_fn=_is_instant_or_sorcery,
            description="target instant or sorcery card in your graveyard",
            zone=Zone.GRAVEYARD,
        )

    def _is_being_cast_as_creature(self, game: "GameState") -> bool:
        """Return ``True`` while this card sits in a STACK zone.

        The casting pipeline (``cast_spell`` / ``cast_spell_free``) moves the
        card into the player's STACK zone *before* it queries ``get_targets``.
        The Dawning Archaic's only targeting belongs to its attack trigger, not
        to the creature spell itself, so while the creature spell is on the
        stack we must advertise *no* targets — otherwise the cast pipeline would
        wrongly force a graveyard instant/sorcery target (and could raise
        ``CastingError`` on an empty graveyard).
        """
        for player in getattr(game, "players", []) or []:
            try:
                stack_zone = player.zones[Zone.STACK]
            except (KeyError, AttributeError):
                continue
            if stack_zone.contains(self):
                return True
        return False

    def get_targets(self, game: "GameState") -> list[Any]:
        """Targets for this object.

        The creature spell itself has no targets. The graveyard instant/sorcery
        requirement belongs to the attack trigger only; it is advertised here so
        the trigger's free-cast can reuse the standard targeting machinery, but
        it is suppressed while the creature spell is being cast (i.e. while this
        card is in the STACK zone).
        """
        if self._is_being_cast_as_creature(game):
            return []
        return [self._graveyard_target_requirement()]

    # ------------------------------------------------------------------
    # Attack trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger that free-casts from the graveyard."""
        from engine.events import AttacksTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return getattr(event, "creature", None) is source

        def _effect(game: "GameState") -> None:
            source._free_cast_from_graveyard(game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def _free_cast_from_graveyard(self, game: "GameState") -> None:
        """Cast the chosen instant/sorcery from the graveyard for free.

        The "may" is modeled by whether a legal target is available/chosen: with
        no legal target the ability does nothing. The spell, if it would be put
        into the graveyard after resolving, is exiled instead.

        Target selection precedence:

        1. If ``chosen_targets`` was pre-populated (e.g. by arbitrated tests),
           use the first legal instant/sorcery there.
        2. Otherwise actively ask the controller to choose one of the legal
           graveyard instant/sorcery cards (live play), so the ability is not a
           no-op outside of the test harness.
        """
        from engine.casting import cast_spell_free

        controller = getattr(self, "controller", None) or getattr(self, "owner", None)
        if controller is None:
            return

        graveyard = game.get_graveyard(controller)
        legal = [c for c in graveyard.get_all() if _is_instant_or_sorcery(c)]
        if not legal:
            return

        target = self._select_free_cast_target(controller, legal)
        if target is None or not graveyard.contains(target):
            return

        cast_spell_free(game, controller, target, Zone.GRAVEYARD)

        # Capture the spell's stack object directly by matching its source,
        # rather than assuming it is the very top of the stack.
        stack_obj = None
        for obj in game.stack.objects():
            if getattr(obj, "source", None) is target:
                stack_obj = obj
                break
        if stack_obj is None:
            return

        # Redirect the spell's post-resolution move from graveyard to exile.
        original_resolve = stack_obj.on_resolve

        def _resolve_then_exile(g: "GameState") -> None:
            gy = g.get_graveyard(controller)
            original_resolve(g)
            # If resolution put the spell into the graveyard, exile it.
            if gy.contains(target):
                from engine.game import exile as _exile

                _exile(g, target)

        stack_obj.on_resolve = _resolve_then_exile

    def _select_free_cast_target(self, controller: Any, legal: list[Any]) -> Any:
        """Pick the instant/sorcery to free-cast.

        Honour a pre-set ``chosen_targets`` first (tests / arbitration). If none
        is set, ask the controller to choose among the legal options so the
        ability works in live play. Returns ``None`` if the player declines or
        no legal choice is made (the trigger is a "may").
        """
        chosen = getattr(self, "chosen_targets", None)
        if chosen:
            for candidate in chosen:
                if candidate is not None and _is_instant_or_sorcery(candidate):
                    return candidate
            return None

        requirement = self._graveyard_target_requirement()
        choose_target = getattr(controller, "choose_target", None)
        if choose_target is None:
            return None
        try:
            selection = choose_target(legal, requirement)
        except Exception:
            return None
        if selection is not None and _is_instant_or_sorcery(selection):
            return selection
        return None
