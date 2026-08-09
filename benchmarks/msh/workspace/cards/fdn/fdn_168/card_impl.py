"""Card implementation for Witness Protection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Aura
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Color, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _creature_targets(game: Any) -> list[Any]:
    """Return all creatures on the battlefield."""
    targets: list[Any] = []
    for player in game.players:
        for obj in game.get_battlefield(player).get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                targets.append(obj)
    return targets


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


class WitnessProtection(Aura):
    """Witness Protection — {U}.

    Enchant creature.
    Enchanted creature loses all abilities and is a green and white Citizen
    creature with base power and toughness 1/1 named Legitimate Businessperson.
    (It loses all other colors, card types, creature types, and names.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witness Protection")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\n"
            "Enchanted creature loses all abilities and is a green and white "
            "Citizen creature with base power and toughness 1/1 named "
            "Legitimate Businessperson.",
        )
        super().__init__(**kwargs)
        self._type_effect_ref: ContinuousEffect | None = None
        self._color_effect_ref: ContinuousEffect | None = None
        self._ability_effect_ref: ContinuousEffect | None = None
        self._pt_effect_ref: ContinuousEffect | None = None

    # -- targeting --------------------------------------------------------

    def get_targets(self, game: GameState) -> list[Any]:
        targets = _creature_targets(game)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, "card_types", set()),
                description="enchant creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        return bool(_creature_targets(game))

    # -- resolution -------------------------------------------------------

    def on_resolve(self, game: GameState) -> None:
        target = _get_chosen_target(self, game)
        if target is None:
            return
        if not _is_on_battlefield(game, target):
            return
        # Revalidate that target is still a creature (type may have changed).
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return
        self.attached_to = target
        self._register_effects(game)

    # -- continuous effects -----------------------------------------------
    #
    # Layer 4 (TYPE):  Becomes a Citizen creature (loses other types/subtypes),
    #                  name becomes "Legitimate Businessperson".
    # Layer 5 (COLOR): Becomes green and white (loses other colors).
    # Layer 6 (ABILITY): Loses all abilities.
    # Layer 7b (SET_PT): Base power and toughness become 1/1.

    def apply_continuous_effect(self, game: GameState) -> None:
        """Apply all four layers of the Witness Protection effect."""
        creature = self.attached_to
        if creature is None or not _is_on_battlefield(game, creature):
            return
        if not _is_on_battlefield(game, self):
            return
        self._apply_type_change(creature)
        self._apply_color_change(creature)
        self._apply_ability_removal(creature)
        self._apply_pt_set(creature)

    def _apply_type_change(self, creature: Any) -> None:
        """Layer 4: Override name, card types, and subtypes."""
        creature.name = "Legitimate Businessperson"
        creature.card_types = {CardType.CREATURE}
        creature.subtypes = {"Citizen"}

    def _apply_color_change(self, creature: Any) -> None:
        """Layer 5: Override colors to green and white."""
        # Set colors if the permanent tracks them.
        creature.colors = {Color.GREEN, Color.WHITE}

    def _apply_ability_removal(self, creature: Any) -> None:
        """Layer 6: Remove all abilities."""
        creature.keywords = Keyword(0)

    def _apply_pt_set(self, creature: Any) -> None:
        """Layer 7b: Set base power and toughness to 1/1."""
        creature.modified_power = 1
        creature.modified_toughness = 1

    def _register_effects(self, game: GameState) -> None:
        aura_ref = self

        # Layer 4: Type-changing (includes name override)
        def _apply_type(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            creature = aura_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            aura_ref._apply_type_change(creature)

        type_effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.TYPE,
            sublayer=None,
            apply=_apply_type,
            duration=DURATION_PERMANENT,
        )
        self._type_effect_ref = game.effect_manager.add(type_effect)

        # Layer 5: Color-changing
        def _apply_color(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            creature = aura_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            aura_ref._apply_color_change(creature)

        color_effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.COLOR,
            sublayer=None,
            apply=_apply_color,
            duration=DURATION_PERMANENT,
        )
        self._color_effect_ref = game.effect_manager.add(color_effect)

        # Layer 6: Ability removal
        def _apply_ability(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            creature = aura_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            aura_ref._apply_ability_removal(creature)

        ability_effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_ability,
            duration=DURATION_PERMANENT,
        )
        self._ability_effect_ref = game.effect_manager.add(ability_effect)

        # Layer 7b: P/T setting
        def _apply_pt(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            creature = aura_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            aura_ref._apply_pt_set(creature)

        pt_effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.SET_PT,
            apply=_apply_pt,
            duration=DURATION_PERMANENT,
        )
        self._pt_effect_ref = game.effect_manager.add(pt_effect)

        # ENGINE LIMITATION: EffectManager._reset_objects() does not restore
        # the ``name``, ``subtypes``, or ``colors`` attributes.  When this aura
        # leaves the battlefield the name/subtype/color changes will persist
        # until engine-level reset support is added for these fields.  The
        # continuous effect framework's reset-and-reapply cycle handles these
        # correctly while the aura is attached, but removal is not covered.
