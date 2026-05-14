"""Card implementation for Chandra, Flameshaper."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player

    from cards.registry import CardRegistry

class ChandraFlameshaper(Planeswalker):
    """Chandra, Flameshaper — {5}{R}{R} — 6 loyalty.

    +2: Add {R}{R}{R}. Exile top three cards. May play one this turn.
    +1: Create a token copy of target creature you control (has haste,
        sacrifice at end step).
    −4: Chandra deals 8 damage divided among any number of target
        creatures and/or planeswalkers.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Chandra, Flameshaper")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("starting_loyalty", 6)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Chandra"}
        kwargs.setdefault(
            "rules_text",
            "+2: Add {R}{R}{R}. Exile the top three cards of your library. "
            "Choose one. You may play that card this turn.\n"
            "+1: Create a token that's a copy of target creature you control, "
            "except it has haste and \"At the beginning of the end step, "
            "sacrifice this token.\"\n"
            "−4: Chandra deals 8 damage divided as you choose among any number "
            "of target creatures and/or planeswalkers.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus2(game: Any) -> None:
            """Add {R}{R}{R}. Exile top 3, may play one."""
            controller = pw.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.RED, 3)
                # Exile top 3 cards (simplified: just exile them)
                # ENGINE LIMITATION: "play until end of turn" from exile not implemented — cards are exiled but cannot be played
                from engine.types import Zone
                library = controller.zones[Zone.LIBRARY]
                for _ in range(min(3, len(library))):
                    cards = library.get_all()
                    if cards:
                        card = cards[-1]  # top of library
                        library.remove(card)
                        exile_zone = controller.zones[Zone.EXILE]
                        exile_zone.add(card)

        def _plus1(game: Any) -> None:
            """Create a token copy of target creature (with haste)."""
            # ENGINE LIMITATION: full copy effect not implemented — token copies basic stats only, missing types/abilities/delayed sacrifice
            from engine.game import create_token
            target = getattr(pw, "_resolve_target", None)
            controller = pw.controller
            if target is not None and controller is not None:
                token = Creature(
                    name=getattr(target, "name", "Token"),
                    base_power=getattr(target, "base_power", 0),
                    base_toughness=getattr(target, "base_toughness", 0),
                    keywords=getattr(target, "keywords", Keyword(0)) | Keyword.HASTE,
                )
                create_token(game, controller, token)

        def _minus4(game: Any) -> None:
            """Deal 8 damage divided among targets."""
            from engine.game import deal_damage
            targets = getattr(pw, "_resolve_targets", None)
            if targets and len(targets) > 0:
                # Divide 8 damage among targets
                damage_per = 8 // len(targets)
                remainder = 8 % len(targets)
                for i, t in enumerate(targets):
                    dmg = damage_per + (1 if i < remainder else 0)
                    deal_damage(game, pw, t, dmg)
            else:
                # Single target fallback
                target = getattr(pw, "_resolve_target", None)
                if target is not None:
                    deal_damage(game, pw, target, 8)

        return [
            LoyaltyAbility(
                loyalty_cost=+2,
                effect=_plus2,
                description="+2: Add {R}{R}{R}. Exile top 3, may play one.",
            ),
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                description="+1: Create a hasty token copy of target creature.",
            ),
            LoyaltyAbility(
                loyalty_cost=-4,
                effect=_minus4,
                description="−4: Deal 8 damage divided among targets.",
            ),
        ]
