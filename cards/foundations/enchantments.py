"""Enchantment card implementations from Foundations (FDN).

Implements 8 enchantments covering auras and global enchantments:

- **Aura buff**: Holy Strength (+1/+2), Unholy Strength (+2/+1).
- **Aura removal**: Stab Wound (-2/-2 and life loss trigger).
- **Aura lockdown**: Arrest (can't attack, block, or activate abilities).
- **Global enchantment**: Glorious Anthem (+1/+1 to your creatures),
  Dictate of Heliod (+2/+2 to your creatures),
  Brave the Sands (your creatures have vigilance and can block extra),
  Levitation (your creatures have flying).

All cards are real MTG cards, with stats based on their actual printings.

Use :func:`register_enchantments` to register all enchantments with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Aura, Enchantment
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    return getattr(card, "_resolve_target", None)


# ---------------------------------------------------------------------------
# Aura buffs
# ---------------------------------------------------------------------------

class HolyStrength(Aura):
    """Holy Strength — {W} — Enchant creature gets +1/+2."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Holy Strength")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\nEnchanted creature gets +1/+2.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def get_targets(self, game: GameState) -> list[Any]:
        targets = _creature_targets(game)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="enchant creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        return bool(_creature_targets(game))

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
            creature = aura_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            creature.base_power += 1
            creature.base_toughness += 2

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)


class UnholyStrength(Aura):
    """Unholy Strength — {B} — Enchant creature gets +2/+1."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Unholy Strength")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\nEnchanted creature gets +2/+1.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def get_targets(self, game: GameState) -> list[Any]:
        targets = _creature_targets(game)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="enchant creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        return bool(_creature_targets(game))

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
            creature = aura_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            creature.base_power += 2
            creature.base_toughness += 1

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)


# ---------------------------------------------------------------------------
# Aura debuff — Stab Wound
# ---------------------------------------------------------------------------

class StabWound(Aura):
    """Stab Wound — {2}{B} — Enchant creature gets -2/-2.

    At the beginning of the upkeep of enchanted creature's controller,
    that player loses 2 life. (Trigger not implemented — just the P/T mod.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Stab Wound")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\n"
            "Enchanted creature gets -2/-2.\n"
            "At the beginning of the upkeep of enchanted creature's controller, "
            "that player loses 2 life.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def get_targets(self, game: GameState) -> list[Any]:
        targets = _creature_targets(game)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="enchant creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        return bool(_creature_targets(game))

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
            creature = aura_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            creature.base_power -= 2
            creature.base_toughness -= 2

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        aura_ref = self

        def _condition(game: GameState, data: dict) -> bool:
            creature = aura_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return False
            return getattr(creature, "controller", None) is game.active_player

        def _effect(game: GameState) -> None:
            creature = aura_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            controller = getattr(creature, "controller", None)
            if controller is not None:
                controller.life -= 2

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.BEGINNING_OF_UPKEEP,
            condition=_condition,
            effect=_effect,
            source=aura_ref,
            controller=controller,
        ))


# ---------------------------------------------------------------------------
# Aura lockdown — Arrest
# ---------------------------------------------------------------------------

class Arrest(Aura):
    """Arrest — {2}{W} — Enchanted creature can't attack, block, or use activated abilities."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Arrest")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\n"
            "Enchanted creature can't attack or block, "
            "and its activated abilities can't be activated.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def get_targets(self, game: GameState) -> list[Any]:
        targets = _creature_targets(game)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="enchant creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        return bool(_creature_targets(game))

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
            creature = aura_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            creature._cant_attack = True  # type: ignore[attr-defined]
            creature._cant_block = True  # type: ignore[attr-defined]
            creature._cant_activate = True  # type: ignore[attr-defined]

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)


# ---------------------------------------------------------------------------
# Global enchantments
# ---------------------------------------------------------------------------

class GloriousAnthem(Enchantment):
    """Glorious Anthem — {1}{W}{W} — Creatures you control get +1/+1."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Glorious Anthem")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Creatures you control get +1/+1.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def on_resolve(self, game: GameState) -> None:
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        enchantment_ref = self

        def _apply(game: GameState) -> None:
            controller = enchantment_ref.controller
            if controller is None:
                return
            if not _is_on_battlefield(game, enchantment_ref):
                return
            for obj in game.get_battlefield(controller).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    obj.base_power += 1
                    obj.base_toughness += 1

        effect = ContinuousEffect(
            source=enchantment_ref,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)

    def register_replacement_effects(self, game: GameState) -> None:
        if self._effect_ref is None:
            self._register_effect(game)


class DictateOfHeliod(Enchantment):
    """Dictate of Heliod — {3}{W}{W} — Creatures you control get +2/+2. Flash."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dictate of Heliod")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}{W}"))
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault(
            "rules_text",
            "Flash\nCreatures you control get +2/+2.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def on_resolve(self, game: GameState) -> None:
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        enchantment_ref = self

        def _apply(game: GameState) -> None:
            controller = enchantment_ref.controller
            if controller is None:
                return
            if not _is_on_battlefield(game, enchantment_ref):
                return
            for obj in game.get_battlefield(controller).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    obj.base_power += 2
                    obj.base_toughness += 2

        effect = ContinuousEffect(
            source=enchantment_ref,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)

    def register_replacement_effects(self, game: GameState) -> None:
        if self._effect_ref is None:
            self._register_effect(game)


class BraveTheSands(Enchantment):
    """Brave the Sands — {1}{W} — Your creatures have vigilance."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Brave the Sands")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Creatures you control have vigilance and can block an additional creature each combat.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def on_resolve(self, game: GameState) -> None:
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        enchantment_ref = self

        def _apply(game: GameState) -> None:
            controller = enchantment_ref.controller
            if controller is None:
                return
            if not _is_on_battlefield(game, enchantment_ref):
                return
            for obj in game.get_battlefield(controller).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    obj.keywords = obj.keywords | Keyword.VIGILANCE
                    obj._max_attackers_blocked = 2  # type: ignore[attr-defined]

        effect = ContinuousEffect(
            source=enchantment_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)

    def register_replacement_effects(self, game: GameState) -> None:
        if self._effect_ref is None:
            self._register_effect(game)


class Levitation(Enchantment):
    """Levitation — {2}{U}{U} — Creatures you control have flying."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Levitation")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Creatures you control have flying.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def on_resolve(self, game: GameState) -> None:
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        enchantment_ref = self

        def _apply(game: GameState) -> None:
            controller = enchantment_ref.controller
            if controller is None:
                return
            if not _is_on_battlefield(game, enchantment_ref):
                return
            for obj in game.get_battlefield(controller).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    obj.keywords = obj.keywords | Keyword.FLYING

        effect = ContinuousEffect(
            source=enchantment_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)

    def register_replacement_effects(self, game: GameState) -> None:
        if self._effect_ref is None:
            self._register_effect(game)


# ---------------------------------------------------------------------------
# Registration data & helper
# ---------------------------------------------------------------------------

_ALL_ENCHANTMENTS: list[
    tuple[str, type, str, list[str], str, str, str, str]
] = [
    ("Holy Strength", HolyStrength, "{W}",
     ["W"], "Enchant creature\nEnchanted creature gets +1/+2.",
     "common", "Enchantment — Aura", ""),
    ("Unholy Strength", UnholyStrength, "{B}",
     ["B"], "Enchant creature\nEnchanted creature gets +2/+1.",
     "common", "Enchantment — Aura", ""),
    ("Stab Wound", StabWound, "{2}{B}",
     ["B"],
     "Enchant creature\nEnchanted creature gets -2/-2.\n"
     "At the beginning of the upkeep of enchanted creature's controller, "
     "that player loses 2 life.",
     "uncommon", "Enchantment — Aura", ""),
    ("Arrest", Arrest, "{2}{W}",
     ["W"],
     "Enchant creature\nEnchanted creature can't attack or block, "
     "and its activated abilities can't be activated.",
     "uncommon", "Enchantment — Aura", ""),
    ("Glorious Anthem", GloriousAnthem, "{1}{W}{W}",
     ["W"], "Creatures you control get +1/+1.",
     "rare", "Enchantment", ""),
    ("Dictate of Heliod", DictateOfHeliod, "{3}{W}{W}",
     ["W"], "Flash\nCreatures you control get +2/+2.",
     "rare", "Enchantment", ""),
    ("Brave the Sands", BraveTheSands, "{1}{W}",
     ["W"],
     "Creatures you control have vigilance and can block an additional creature each combat.",
     "uncommon", "Enchantment", ""),
    ("Levitation", Levitation, "{2}{U}{U}",
     ["U"], "Creatures you control have flying.",
     "uncommon", "Enchantment", ""),
]


def register_enchantments(registry: CardRegistry) -> None:
    """Register all enchantments with *registry*."""
    from cards.registry import CardMetadata

    for (
        card_name, impl_class, cost_str, colors, oracle_text,
        rarity, type_line, collector_number,
    ) in _ALL_ENCHANTMENTS:
        metadata = CardMetadata(
            name=card_name,
            mana_cost_str=cost_str,
            type_line=type_line,
            oracle_text=oracle_text,
            power=None,
            toughness=None,
            colors=colors,
            keywords=[],
            rarity=rarity,
            set_code="fdn",
            collector_number=collector_number,
        )
        registry.register(card_name, impl_class, metadata)
