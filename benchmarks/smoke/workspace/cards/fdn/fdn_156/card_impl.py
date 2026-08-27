"""Card implementation for Imprisoned in the Moon."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Aura
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Check if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _get_chosen_target(card: Any, game: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return None


def _creature_land_planeswalker_targets(game: Any) -> list[Any]:
    """Return creatures, lands, and planeswalkers on the battlefield."""
    targets: list[Any] = []
    for player in game.players:
        for obj in game.get_battlefield(player).get_all():
            ctypes = getattr(obj, "card_types", set())
            if (
                CardType.CREATURE in ctypes
                or CardType.LAND in ctypes
                or CardType.PLANESWALKER in ctypes
            ):
                targets.append(obj)
    return targets


class ImprisonedInTheMoon(Aura):
    """Imprisoned in the Moon — {2}{U}.

    Enchant creature, land, or planeswalker.
    Enchanted permanent is a colorless land with "{T}: Add {C}" and loses
    all other card types and abilities.
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
        self._type_effect_ref: ContinuousEffect | None = None
        self._color_effect_ref: ContinuousEffect | None = None
        self._ability_effect_ref: ContinuousEffect | None = None

    # -- targeting --------------------------------------------------------

    def get_targets(self, game: GameState) -> list[Any]:
        targets = _creature_land_planeswalker_targets(game)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: bool(
                    getattr(obj, "card_types", set())
                    & {CardType.CREATURE, CardType.LAND, CardType.PLANESWALKER}
                ),
                description="enchant creature, land, or planeswalker",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        return bool(_creature_land_planeswalker_targets(game))

    # -- resolution -------------------------------------------------------

    def on_resolve(self, game: GameState) -> None:
        target = _get_chosen_target(self, game)
        if target is None:
            return
        if not _is_on_battlefield(game, target):
            return
        # Revalidate that target is still a creature, land, or planeswalker.
        ctypes = getattr(target, "card_types", set())
        if not (ctypes & {CardType.CREATURE, CardType.LAND, CardType.PLANESWALKER}):
            return
        self.attached_to = target
        self._register_effects(game)

    # -- continuous effects -----------------------------------------------
    #
    # Layer 4 (TYPE): The permanent becomes a land, losing all other card
    #   types and subtypes.
    # Layer 5 (COLOR): The permanent becomes colorless.
    # Layer 6 (ABILITY): The permanent loses all abilities.
    #
    # The card also grants "{T}: Add {C}" — see ENGINE LIMITATION below.

    def apply_continuous_effect(self, game: GameState) -> None:
        """Apply type-changing, color, and ability-removal effects."""
        perm = self.attached_to
        if perm is None or not _is_on_battlefield(game, perm):
            return
        if not _is_on_battlefield(game, self):
            return
        self._apply_type_change(perm)
        self._apply_color_change(perm)
        self._apply_ability_removal(perm)

    def _apply_type_change(self, perm: Any) -> None:
        """Layer 4: Becomes a land, loses other card types."""
        perm.card_types = {CardType.LAND}
        perm.subtypes = set()

    def _apply_color_change(self, perm: Any) -> None:
        """Layer 5: Becomes colorless."""
        if hasattr(perm, "colors"):
            perm.colors = set()

    def _apply_ability_removal(self, perm: Any) -> None:
        """Layer 6: Loses all abilities."""
        perm.keywords = Keyword(0)
        # Mark permanent as having lost abilities for combat/activation checks.
        # Guard behind type checks — only creatures can attack/block.
        if CardType.CREATURE in getattr(perm, "card_types", set()):
            perm._cant_attack = True  # type: ignore[attr-defined]
            perm._cant_block = True  # type: ignore[attr-defined]
        if hasattr(perm, "_cant_activate"):
            perm._cant_activate = True  # type: ignore[attr-defined]
        perm._imprisoned = True  # type: ignore[attr-defined]

    def _register_effects(self, game: GameState) -> None:
        aura_ref = self

        # Layer 4: Type-changing effect
        def _apply_type(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            perm = aura_ref.attached_to
            if perm is None or not _is_on_battlefield(game, perm):
                return
            aura_ref._apply_type_change(perm)

        type_effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.TYPE,
            sublayer=None,
            apply=_apply_type,
            duration=DURATION_PERMANENT,
        )
        self._type_effect_ref = game.effect_manager.add(type_effect)

        # Layer 5: Color-changing effect (colorless)
        def _apply_color(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            perm = aura_ref.attached_to
            if perm is None or not _is_on_battlefield(game, perm):
                return
            aura_ref._apply_color_change(perm)

        color_effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.COLOR,
            sublayer=None,
            apply=_apply_color,
            duration=DURATION_PERMANENT,
        )
        self._color_effect_ref = game.effect_manager.add(color_effect)

        # Layer 6: Ability-removal effect
        def _apply_ability(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            perm = aura_ref.attached_to
            if perm is None or not _is_on_battlefield(game, perm):
                return
            aura_ref._apply_ability_removal(perm)

        ability_effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_ability,
            duration=DURATION_PERMANENT,
        )
        self._ability_effect_ref = game.effect_manager.add(ability_effect)

        # ENGINE LIMITATION: The enchanted permanent should gain the mana
        # ability "{T}: Add {C}".  Implementing this properly requires engine
        # support for dynamically granting activated mana abilities to
        # permanents via continuous effects.  Currently the engine has no
        # mechanism to inject a ManaAbility into an arbitrary permanent at
        # the continuous-effect layer.
