"""Card implementation for Akroma's Memorial."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import (
    ActivatedAbility,
    Artifact,
    Creature,
    Enchantment,
    Instant,
    ManaAbility,
    Sorcery,
)
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import CardType, Color, HybridManaSymbol, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

    from benchmarks.sos.workspace.cards.registry import CardRegistry

def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False

class AkromasMemorial(Artifact):
    """Akroma's Memorial — {7} — Legendary Artifact

    Creatures you control have flying, first strike, vigilance, trample,
    haste, and protection from black and from red.

    SPG collector number 81.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Akroma's Memorial")
        kwargs.setdefault("mana_cost", ManaCost.parse("{7}"))
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault(
            "rules_text",
            "Creatures you control have flying, first strike, vigilance, "
            "trample, haste, and protection from black and from red.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: Any) -> None:
        """Register a continuous effect granting keywords and protection."""
        from benchmarks.sos.workspace.engine.protection import ProtectionAbility

        source = self

        _KEYWORDS = (
            Keyword.FLYING
            | Keyword.FIRST_STRIKE
            | Keyword.VIGILANCE
            | Keyword.TRAMPLE
            | Keyword.HASTE
        )

        pro_black = ProtectionAbility(quality=Color.BLACK)
        pro_red = ProtectionAbility(quality=Color.RED)

        def _apply(g: Any) -> None:
            if not _is_on_battlefield(g, source):
                return
            controller = source.controller or source.owner
            if controller is None:
                return
            bf = g.get_battlefield(controller)
            for perm in bf.get_all():
                if CardType.CREATURE not in getattr(perm, "card_types", set()):
                    continue
                perm.keywords = perm.keywords | _KEYWORDS
                # Add protection abilities
                if not hasattr(perm, "protections"):
                    perm.protections = []
                # Avoid duplicates by checking quality
                existing_qualities = {
                    p.quality for p in perm.protections
                }
                if Color.BLACK not in existing_qualities:
                    perm.protections.append(pro_black)
                if Color.RED not in existing_qualities:
                    perm.protections.append(pro_red)

        game.effect_manager.add(ContinuousEffect(
            source=source,
            layer=Layer.ABILITY,
            apply=_apply,
            duration=DURATION_PERMANENT,
        ))
