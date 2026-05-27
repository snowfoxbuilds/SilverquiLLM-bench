"""Card implementation for The Dawning Archaic (SOS 1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent, MoveToGraveyardReplacementEvent
from engine.replacement_effects import ReplacementEffect
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — Legendary Creature — Avatar — 7/7.

    This spell costs {1} less to cast for each instant and sorcery card
    in your graveyard.
    Reach.
    Whenever The Dawning Archaic attacks, you may cast target instant or
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
        """Return 1 for each instant/sorcery in the controller's graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        count = 0
        for card in graveyard.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                count += 1
        return count

    # ------------------------------------------------------------------
    # Triggered ability
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger: cast instant/sorcery from graveyard."""
        source = self
        controller = self.controller

        # Shared mutable state: target chosen at announcement time.
        # When the trigger is put onto the stack (on_announce), the
        # controller chooses the target.  When it resolves (effect), this
        # pre-chosen target is used.  If effect is called directly (tests),
        # the state is None and the choice falls back to happen in effect.
        announcement_state: dict[str, Any] = {"chosen": None}

        def _condition(g: "GameState", event: AttacksTriggeredEvent) -> bool:
            """Trigger only when this creature itself attacks."""
            attacker = getattr(event, "attacker", None) or getattr(event, "creature", None)
            return attacker is source

        def _get_valid_targets(g: "GameState") -> list[Any]:
            """Return valid instant/sorcery targets from controller's graveyard."""
            ctrl = source.controller
            if ctrl is None:
                return []
            graveyard = g.get_graveyard(ctrl)
            return [
                c for c in graveyard.get_all()
                if CardType.INSTANT in getattr(c, "card_types", set())
                or CardType.SORCERY in getattr(c, "card_types", set())
            ]

        def _on_announce(g: "GameState", event: AttacksTriggeredEvent) -> None:
            """Choose target when trigger is put onto the stack (announcement time).

            This fixes the target before opponents receive priority, which is
            the correct MTG rule for 'you may cast target X' triggered abilities.
            The controller may decline by having no valid targets or by
            choosing None (if the engine passes None from the choice).
            """
            ctrl = source.controller
            if ctrl is None:
                announcement_state["chosen"] = None
                return

            valid_targets = _get_valid_targets(g)
            if not valid_targets:
                announcement_state["chosen"] = None
                return

            # Ask the controller to choose a target (None = decline)
            chosen = ctrl.choose(valid_targets, "Choose instant or sorcery to cast from graveyard (or decline)")
            if chosen not in valid_targets:
                chosen = None
            announcement_state["chosen"] = chosen

        def _effect(g: "GameState") -> None:
            """Resolve the trigger: cast the pre-chosen spell for free; exile instead of graveyard."""
            ctrl = source.controller
            if ctrl is None:
                return

            # --- Determine the chosen spell ---
            if announcement_state["chosen"] is not None:
                # Target was fixed at announcement time (real game flow).
                chosen = announcement_state["chosen"]
                announcement_state["chosen"] = None  # consume

                # Verify the target is still in the graveyard (may have moved).
                graveyard = g.get_graveyard(ctrl)
                if chosen not in graveyard.get_all():
                    return
            else:
                # Fallback: choose now (direct effect() calls in tests).
                valid_targets = _get_valid_targets(g)
                if not valid_targets:
                    return

                chosen = ctrl.choose(
                    valid_targets,
                    "Choose an instant or sorcery to cast from graveyard",
                )
                if chosen is None or chosen not in valid_targets:
                    return

            chosen_ref = chosen

            # --- Register a scoped replacement effect ---
            # Use a unique sentinel as source so unregister only removes THIS effect.
            sentinel: object = object()

            def _replacement_condition(_g: "GameState", evt: MoveToGraveyardReplacementEvent) -> bool:
                return getattr(evt, "card", None) is chosen_ref

            def _replacement_fn(
                _g: "GameState", evt: MoveToGraveyardReplacementEvent
            ) -> MoveToGraveyardReplacementEvent:
                evt.destination = "exile"
                return evt

            replacement_effect = ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=sentinel,
                condition=_replacement_condition,
                replacement=_replacement_fn,
                controller=ctrl,
            )
            g.replacement_manager.register(replacement_effect)

            # --- Cast the chosen spell via the free-cast pipeline ---
            from engine.casting import cast_spell_free  # noqa: PLC0415

            cast_spell_free(g, ctrl, chosen_ref, Zone.GRAVEYARD)

            # --- Wrap the StackObject's on_resolve to exile instead of graveyard ---
            # cast_spell_free pushes a StackObject whose on_resolve calls
            # _resolve_spell, which moves non-permanents to the graveyard.
            # We wrap it to also move the card from graveyard to exile
            # and clean up the replacement effect afterward.
            stack_obj = g.stack.peek()
            if stack_obj is None:
                return

            original_on_resolve = stack_obj.on_resolve

            def _exile_on_resolve(game_state: "GameState") -> None:
                """Resolve the spell, then move it to exile and clean up."""
                original_on_resolve(game_state)

                # Clean up the scoped replacement effect.
                game_state.replacement_manager.unregister(sentinel)

                # The card should now be in the owner's graveyard (from _resolve_spell).
                # Move it to exile.
                owner = getattr(chosen_ref, "owner", ctrl)
                if owner is None:
                    owner = ctrl
                gy = game_state.get_graveyard(owner)
                exile_zone = owner.zones[Zone.EXILE]
                if gy.contains(chosen_ref):
                    gy.remove(chosen_ref)
                    exile_zone.add(chosen_ref)

            stack_obj.on_resolve = _exile_on_resolve

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                on_announce=_on_announce,
            )
        )
