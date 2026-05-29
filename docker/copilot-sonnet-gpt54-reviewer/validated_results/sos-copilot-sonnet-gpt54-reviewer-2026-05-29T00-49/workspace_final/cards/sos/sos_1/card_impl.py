"""Card implementation for sos_1 — The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent, MoveToGraveyardReplacementEvent
from engine.replacement_effects import ReplacementEffect
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _register_floating_exile_replacement(
    game: "GameState", spell_card: Any
) -> None:
    """Register a one-shot replacement effect that exiles *spell_card* instead
    of the graveyard when it resolves.

    Uses a per-cast sentinel object as the source so the effect is *not*
    unregistered when The Dawning Archaic leaves the battlefield — it stays
    active until the tagged spell would move to the graveyard, at which point
    it redirects to exile and self-unregisters.
    """

    class _Sentinel:
        """Unique sentinel acting as source for this floating replacement."""

    sentinel = _Sentinel()

    def _condition(g: "GameState", event: Any) -> bool:
        card_obj = getattr(event, "card_obj", None) or getattr(event, "card", None)
        return bool(
            card_obj is spell_card
            and getattr(card_obj, "cast_from_graveyard_by_dawning_archaic", False)
        )

    def _replacement(g: "GameState", event: Any) -> Any:
        card_obj = getattr(event, "card_obj", None) or getattr(event, "card", None)
        # Clean up the tag so the replacement fires only once.
        if card_obj is not None and hasattr(
            card_obj, "cast_from_graveyard_by_dawning_archaic"
        ):
            del card_obj.cast_from_graveyard_by_dawning_archaic  # type: ignore[attr-defined]
        # Self-unregister this one-shot floating effect.
        g.replacement_manager.unregister(sentinel)
        # Redirect to exile (move_to_zone handles the actual zone move).
        event.destination = "exile"
        return event

    game.replacement_manager.register(
        ReplacementEffect(
            event_type=MoveToGraveyardReplacementEvent,
            source=sentinel,
            condition=_condition,
            replacement=_replacement,
            controller=getattr(spell_card, "controller", None),
        )
    )


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — Legendary Creature — Avatar — 7/7.

    This spell costs {1} less to cast for each instant and sorcery card
    in your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost. If that
    spell would be put into your graveyard, exile it instead.
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
            "This spell costs {1} less to cast for each instant and sorcery card "
            "in your graveyard.\n"
            "Reach\n"
            "Whenever The Dawning Archaic attacks, you may cast target instant or "
            "sorcery card from your graveyard without paying its mana cost. If that "
            "spell would be put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Cost reduction
    # ------------------------------------------------------------------

    def cost_reduction(self, game: "GameState") -> int:
        """Return 1 per instant/sorcery in controller's graveyard, capped at 10."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        count = sum(
            1
            for obj in graveyard.get_all()
            if CardType.INSTANT in getattr(obj, "card_types", set())
            or CardType.SORCERY in getattr(obj, "card_types", set())
        )
        # Cap at the total mana value (10) so reduction never drives cost negative.
        return min(count, 10)

    # ------------------------------------------------------------------
    # Triggered ability
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger: cast instant/sorcery from graveyard."""
        source = self

        def _condition(game: "GameState", event: AttacksTriggeredEvent) -> bool:
            return event.creature is source or event.attacker is source

        def _effect(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return
            graveyard = game.get_graveyard(controller)
            target: Any = None
            for obj in graveyard.get_all():
                if (
                    CardType.INSTANT in getattr(obj, "card_types", set())
                    or CardType.SORCERY in getattr(obj, "card_types", set())
                ):
                    target = obj
                    break
            if target is None:
                # No valid target — no-op.
                return
            # Mark the card so the exile replacement can identify it.
            target.cast_from_graveyard_by_dawning_archaic = True  # type: ignore[attr-defined]
            # Register a floating replacement effect tied to the spell (not to
            # The Dawning Archaic), so it persists even if Archaic leaves the
            # battlefield before the spell resolves.
            _register_floating_exile_replacement(game, target)
            # Use the proper casting pipeline — moves card from graveyard to
            # stack zone, chooses targets, calls on_cast, and pushes a
            # StackObject whose on_resolve runs the full resolution flow.
            from engine.casting import cast_spell_free

            try:
                cast_spell_free(game, controller, target, Zone.GRAVEYARD)
            except Exception:
                # Cast failed — clean up the tag so the floating replacement
                # doesn't linger indefinitely.
                if hasattr(target, "cast_from_graveyard_by_dawning_archaic"):
                    del target.cast_from_graveyard_by_dawning_archaic  # type: ignore[attr-defined]

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=self.controller,
            )
        )

    # ------------------------------------------------------------------
    # Replacement effect
    # ------------------------------------------------------------------

    def register_replacement_effects(self, game: "GameState") -> None:
        """Register the exile-instead-of-graveyard replacement effect.

        This registration is tied to The Dawning Archaic as source and is
        active while Archaic is on the battlefield.  A separate floating
        replacement (registered per-cast by the attack trigger) provides
        coverage for cases where Archaic leaves the battlefield before the
        triggered spell resolves.
        """
        source = self

        def _condition(game: "GameState", event: MoveToGraveyardReplacementEvent) -> bool:
            card_obj = getattr(event, "card_obj", None)
            if card_obj is None:
                card_obj = getattr(event, "card", None)
            return bool(
                card_obj is not None
                and getattr(card_obj, "cast_from_graveyard_by_dawning_archaic", False)
            )

        def _replacement(
            game: "GameState", event: MoveToGraveyardReplacementEvent
        ) -> MoveToGraveyardReplacementEvent:
            # Redirect to exile; move_to_zone handles the actual zone change.
            event.destination = "exile"
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=self,
                condition=_condition,
                replacement=_replacement,
                controller=self.controller,
            )
        )
