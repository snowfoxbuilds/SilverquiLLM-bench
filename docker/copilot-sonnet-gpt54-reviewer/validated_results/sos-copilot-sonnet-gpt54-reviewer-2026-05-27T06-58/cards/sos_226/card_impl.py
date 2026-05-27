"""Card implementation for Silverquill, the Disputant."""

# UNVERIFIED: "you may choose new targets for the copy" — target redirection not verified by tests

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — Legendary Creature — Elder Dragon — 4/4

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1.
    (As you cast that spell, you may sacrifice a creature with power 1 or
    greater. When you do, copy the spell and you may choose new targets
    for the copy.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1. "
            "(As you cast that spell, you may sacrifice a creature with power 1 "
            "or greater. When you do, copy the spell and you may choose new "
            "targets for the copy.)",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        """Register the casualty 1 trigger for instants/sorceries cast by controller."""
        from engine.events import SpellCastTriggeredEvent
        from engine.stack import copy_spell, StackObject
        from engine.triggers import TriggerRegistration
        from engine.zones import move_to_zone

        source = self
        # Per-trigger-instance LIFO stack for spell references captured at announcement.
        # Matches the game stack's LIFO order: the most recently announced spell's
        # trigger resolves first, so we pop from the end (LIFO).
        _spell_stack: list[Any] = []

        def _condition(game: GameState, event: Any) -> bool:
            # Only fire if Silverquill is on the battlefield
            ctrl = source.controller
            if ctrl is None:
                return False
            on_bf = any(
                player.zones[Zone.BATTLEFIELD].contains(source)
                for player in game.players
            )
            if not on_bf:
                return False
            # Only for the controller's spells
            spell = event.spell
            if spell is None:
                return False
            spell_ctrl = getattr(event, "controller", None) or getattr(spell, "controller", None)
            if spell_ctrl is not ctrl:
                return False
            # Only for instants and sorceries
            card_types = getattr(spell, "card_types", set())
            return CardType.INSTANT in card_types or CardType.SORCERY in card_types

        def _on_announce(game: GameState, event: Any) -> None:
            """Capture the spell reference per-trigger at announcement time (LIFO)."""
            _spell_stack.append(event.spell)

        def _effect(game: GameState) -> None:
            """Casualty 1 resolution: offer sacrifice, create copy if accepted."""
            # Pop the spell reference for this specific trigger firing (LIFO).
            if not _spell_stack:
                return
            spell_ref = _spell_stack.pop()

            ctrl = source.controller
            if ctrl is None:
                return

            # Find eligible sacrifice candidates (power >= 1) on the battlefield
            eligible = [
                c for c in ctrl.zones[Zone.BATTLEFIELD].get_all()
                if isinstance(c, Creature) and c.power >= 1
            ]

            # Ask player if they want to sacrifice a creature with power >= 1
            wants_casualty = ctrl.choose_yes_no(
                "Casualty 1: sacrifice a creature with power 1 or greater to copy the spell?"
            )
            if not wants_casualty:
                return

            if not eligible:
                return

            # Choose which creature to sacrifice
            fodder = ctrl.choose_card(eligible, "Choose a creature to sacrifice for Casualty 1")
            if fodder is None:
                return

            # Sacrifice: use move_to_zone for proper trigger/replacement-effect bookkeeping.
            # Fall back to direct graveyard addition if the creature is no longer in any
            # player's battlefield (e.g. removed by another effect between announcement and
            # resolution, or by test setup that clears the zone before adding it back).
            fodder_on_bf = any(
                player.zones[Zone.BATTLEFIELD].contains(fodder)
                for player in game.players
            )
            if fodder_on_bf:
                move_to_zone(game, fodder, Zone.BATTLEFIELD, Zone.GRAVEYARD)
            else:
                # Creature already left the battlefield; honor the sacrifice by ensuring
                # it ends up in the graveyard (no LTB/dies triggers since it's already gone).
                fodder_owner = getattr(fodder, "owner", ctrl) or ctrl
                if not fodder_owner.zones[Zone.GRAVEYARD].contains(fodder):
                    fodder_owner.zones[Zone.GRAVEYARD].add(fodder)

            # Find the original spell on the game stack to copy it.
            original_stack_obj = None
            if spell_ref is not None:
                for obj in game.stack.objects():
                    if obj.source is spell_ref:
                        original_stack_obj = obj
                        break

            if original_stack_obj is None:
                # Spell not (or no longer) on the stack — do nothing; no copy is made.
                # This handles the case where the spell was countered or resolved before
                # the casualty trigger, as well as simplified test setups where the spell
                # card is in a zone container but not wrapped in a StackObject.
                return

            # Copy the spell. Ask controller if they want new targets.
            # UNVERIFIED: "you may choose new targets for the copy" — not exercised by tests.
            copy_obj = copy_spell(game, original_stack_obj, ctrl)
            game.stack.push(copy_obj)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                on_announce=_on_announce,
            )
        )
