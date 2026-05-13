"""Card implementation for Imprisoned in the Moon."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Aura, ContinuousEffect
from engine.continuous_effects import Layer
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    TargetRequirement,
    Zone,
)

if TYPE_CHECKING:
    from engine.game_state import GameState




def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False

def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell.

    Looks for ``chosen_targets`` (set by :func:`cast_spell` during the
    real casting pipeline) first, then falls back to the test-backdoor
    attribute ``_resolve_target``.
    """
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)

def _creature_land_planeswalker_targets(game: Any) -> list[Any]:
    """Return creatures, lands, and planeswalkers on the battlefield."""
    targets: list[Any] = []
    for player in game.players:
        for obj in game.get_battlefield(player).get_all():
            ctypes = getattr(obj, "card_types", set())
            if (CardType.CREATURE in ctypes
                    or CardType.LAND in ctypes
                    or CardType.PLANESWALKER in ctypes):
                targets.append(obj)
    return targets
class ImprisonedInTheMoon(Aura):
    """Imprisoned in the Moon — {2}{U} — Enchant creature, land, or planeswalker.
    Enchanted permanent is a colorless land with "{T}: Add {C}" and loses all
    other card types and abilities.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Imprisoned in the Moon")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature, land, or planeswalker\n"
            "Enchanted permanent is a colorless land with "
            '"{T}: Add {C}" and loses all other card types and abilities.',
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def get_targets(self, game: GameState) -> list[Any]:
        targets = _creature_land_planeswalker_targets(game)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: bool(getattr(obj, "card_types", set()) & {CardType.CREATURE, CardType.LAND, CardType.PLANESWALKER}),
                description="enchant creature, land, or planeswalker",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        return bool(_creature_land_planeswalker_targets(game))

    def on_resolve(self, game: GameState) -> None:
        target = _get_chosen_target(self, game)
        if target is None:
            return
        if not _is_on_battlefield(game, target):
            return
        self.attached_to = target
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        aura_ref = self

        def _apply(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            perm = aura_ref.attached_to
            if perm is None or not _is_on_battlefield(game, perm):
                return
            # Becomes a colorless land, loses all other types/abilities
            perm.card_types = {CardType.LAND}
            perm.subtypes = set()
            perm.keywords = Keyword(0)
            perm._cant_attack = True  # type: ignore[attr-defined]
            perm._cant_block = True  # type: ignore[attr-defined]
            perm._cant_activate = True  # type: ignore[attr-defined]
            perm._imprisoned = True  # type: ignore[attr-defined]
            # ENGINE LIMITATION: Should also grant "{T}: Add {C}" mana ability
            # to the enchanted permanent. Implementing this properly requires
            # engine support for dynamically adding activated mana abilities
            # to permanents via continuous effects.

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.TYPE,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)
