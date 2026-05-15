"""Card implementation for Kaito, Cunning Infiltrator."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player

    from cards.registry import CardRegistry


class KaitoCunningInfiltrator(Planeswalker):
    """Kaito, Cunning Infiltrator — {1}{U}{U} — 3 loyalty.

    Whenever a creature you control deals combat damage to a player, put a
    loyalty counter on Kaito.
    +1: Up to one target creature you control can't be blocked this turn.
        Draw a card, then discard a card.
    −2: Create a 2/1 blue Ninja creature token.
    −9: You get an emblem with "Whenever a player casts a spell, you create
        a 2/1 blue Ninja creature token."
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Kaito, Cunning Infiltrator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Kaito"}
        kwargs.setdefault(
            "rules_text",
            "Whenever a creature you control deals combat damage to a player, "
            "put a loyalty counter on Kaito.\n"
            "+1: Up to one target creature you control can't be blocked this turn. "
            "Draw a card, then discard a card.\n"
            "−2: Create a 2/1 blue Ninja creature token.\n"
            "−9: You get an emblem with \"Whenever a player casts a spell, you "
            "create a 2/1 blue Ninja creature token.\"",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: Any) -> None:
        """Register passive: combat damage to a player → loyalty counter."""
        from engine.game import add_counter
        from engine.triggers import EventType, TriggerRegistration

        pw = self
        controller = getattr(self, "controller", None) or game.active_player

        def _combat_damage_condition(game: Any, data: dict) -> bool:
            """Fire when a creature controlled by Kaito's controller deals damage to a player."""
            source = data.get("source")
            target = data.get("target")
            # Must be combat damage
            if not data.get("combat", False):
                return False
            if source is None or target is None:
                return False
            # Source must be a creature we control
            source_types = getattr(source, "card_types", set())
            if CardType.CREATURE not in source_types:
                return False
            if getattr(source, "controller", None) is not pw.controller:
                return False
            # Target must be a player (has 'life')
            if not hasattr(target, "life"):
                return False
            return True

        def _combat_damage_effect(game: Any) -> None:
            """Put a loyalty counter on Kaito."""
            add_counter(game, pw, "loyalty", 1)

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.DEALS_DAMAGE,
            condition=_combat_damage_condition,
            effect=_combat_damage_effect,
            source=self,
            controller=controller,
        ))

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """Up to one target creature can't be blocked. Draw then discard."""
            from engine.game import discard, draw_card

            # "Up to one" — target is optional
            target = getattr(pw, "_resolve_target", None)
            if target is not None:
                target._cant_be_blocked = True  # type: ignore[attr-defined]
            controller = pw.controller
            if controller is not None:
                # Draw a card
                drawn = draw_card(game, controller)
                # Then discard a card (controller chooses; simplified: discard last)
                hand = controller.zones[Zone.HAND]
                cards_in_hand = hand.get_all()
                if cards_in_hand:
                    card_to_discard = cards_in_hand[-1]
                    discard(game, controller, card_to_discard)

        def _minus2(game: Any) -> None:
            """Create a 2/1 blue Ninja creature token."""
            from engine.game import create_token

            controller = pw.controller
            if controller is not None:
                token = Creature(
                    name="Ninja",
                    base_power=2,
                    base_toughness=1,
                    subtypes={"Ninja"},
                )
                create_token(game, controller, token)

        def _minus9(game: Any) -> None:
            """Emblem — whenever a player casts a spell, create a 2/1 Ninja token."""
            from engine.triggers import EventType, TriggerRegistration
            from engine.game import create_token

            controller = pw.controller
            if controller is None:
                return

            # Create a sentinel object to act as the emblem source
            emblem = type("Emblem", (), {"name": "Kaito Emblem"})()

            def _spell_cast_condition(game: Any, data: dict) -> bool:
                """Always fires when any player casts a spell."""
                return True

            def _spell_cast_effect(game: Any) -> None:
                """Create a 2/1 blue Ninja creature token."""
                token = Creature(
                    name="Ninja",
                    base_power=2,
                    base_toughness=1,
                    subtypes={"Ninja"},
                )
                create_token(game, controller, token)

            game.trigger_manager.register(TriggerRegistration(
                event_type=EventType.SPELL_CAST,
                condition=_spell_cast_condition,
                effect=_spell_cast_effect,
                source=emblem,
                controller=controller,
            ))

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                description="+1: Up to one target creature can't be blocked. Draw, then discard.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description="−2: Create a 2/1 blue Ninja creature token.",
            ),
            LoyaltyAbility(
                loyalty_cost=-9,
                effect=_minus9,
                description="−9: Emblem — whenever a player casts a spell, create 2/1 Ninja token.",
            ),
        ]
