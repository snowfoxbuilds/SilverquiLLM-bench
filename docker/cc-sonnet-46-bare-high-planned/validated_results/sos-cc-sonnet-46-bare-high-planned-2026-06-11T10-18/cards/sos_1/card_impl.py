"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — Legendary Creature — Avatar 7/7.

    This spell costs {1} less to cast for each instant and sorcery card in your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or sorcery card
    from your graveyard without paying its mana cost. If that spell would be put into
    your graveyard, exile it instead.
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
            "This spell costs {1} less to cast for each instant and sorcery card in your graveyard.\n"
            "Reach\n"
            "Whenever The Dawning Archaic attacks, you may cast target instant or sorcery card "
            "from your graveyard without paying its mana cost. If that spell would be put into "
            "your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Costs {1} less for each instant and sorcery in controller's graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        gy = game.get_graveyard(controller)
        count = sum(
            1
            for c in gy.get_all()
            if CardType.INSTANT in getattr(c, "card_types", set())
            or CardType.SORCERY in getattr(c, "card_types", set())
        )
        return count

    def register_triggers(self, game: "GameState") -> None:
        from engine.casting import cast_spell_free
        from engine.replacement_effects import ReplacementEffect
        from engine.triggers import TriggerRegistration
        from engine.events import AttacksTriggeredEvent, MoveToGraveyardReplacementEvent

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _attack_condition(g: Any, event: Any) -> bool:
            return event.creature is source

        def _attack_effect(g: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Find instant/sorcery cards in the graveyard.
            gy = g.get_graveyard(ctrl)
            legal_targets = [
                c for c in gy.get_all()
                if CardType.INSTANT in getattr(c, "card_types", set())
                or CardType.SORCERY in getattr(c, "card_types", set())
            ]

            if not legal_targets:
                return

            # Auto-select if only one legal target; otherwise let player choose.
            if len(legal_targets) == 1:
                chosen = legal_targets[0]
            else:
                try:
                    chosen = ctrl.choose_card(legal_targets, "Cast from graveyard without paying mana cost?")
                except Exception:
                    chosen = None

            if chosen is None:
                return

            # Register exile-instead replacement effect for this spell.
            repl_registered = [False]

            def _graveyard_condition(g2: Any, ev: Any) -> bool:
                return ev.card is chosen

            def _exile_replacement(g2: Any, ev: Any) -> Any:
                owner = getattr(chosen, "owner", ctrl)
                if owner is not None:
                    exile = owner.zones[Zone.EXILE]
                    exile.add(chosen)
                ev.prevented = True
                return ev

            repl = ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=source,
                condition=_graveyard_condition,
                replacement=_exile_replacement,
                controller=ctrl,
            )
            g.replacement_manager.register(repl)

            try:
                cast_spell_free(g, ctrl, chosen, Zone.GRAVEYARD)
            except Exception:
                # If cast fails, unregister the replacement effect.
                g.replacement_manager.unregister(source)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_attack_condition,
                effect=_attack_effect,
                source=self,
                controller=controller,
            )
        )
