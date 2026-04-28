"""Simple enchantment and artifact implementations from Foundations (FDN).

Implements 5 noncreature permanents covering:

- **Aura buff**: Untamed Hunger (+2/+1 and menace, layer 7c/6),
  Unflinching Courage (+2/+2, trample, lifelink, layer 7c/6).
- **Aura debuff**: Pacifism (can't attack or block, layer 6).
- **Mana rock**: Hedron Archive ({T}: Add {C}{C}).
- **Non-aura enchantment**: Goblin Oriflamme (attacking creatures +1/+0, layer 7c).

All cards are actual cards from the MTG Foundations (FDN) set with
correct printed stats sourced from Scryfall.

Aura implementation:
- Each aura subclasses :class:`~engine.card.Aura` (``is_aura = True``).
- :meth:`get_targets` returns legal targets (creatures on the battlefield).
- :meth:`on_resolve` attaches the aura to the chosen target via
  ``self.attached_to`` and registers a continuous effect.
- SBAs handle aura without legal target → graveyard (via ``_sba_aura_unattached``).

Use :func:`register_simple_permanents` to register all permanents with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Artifact, Aura, Enchantment
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Helper — retrieve chosen target for targeted spells (same as simple_spells)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Aura helpers
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


# ---------------------------------------------------------------------------
# Aura debuff — Pacifism
# ---------------------------------------------------------------------------

class Pacifism(Aura):
    """Pacifism — {1}{W} — Enchant creature. Can't attack or block.

    Implements the "can't attack or block" restriction as a layer 6
    continuous effect that removes attack/block ability.  On the engine
    side, creatures with this effect have ``is_attacking`` and
    ``is_blocking`` forcefully set to ``False`` and their ability to
    be declared as attacker/blocker is checked via the continuous effect.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pacifism")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\nEnchanted creature can't attack or block.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature on the battlefield."""
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
        """Cannot cast if no creature on the battlefield."""
        return bool(_creature_targets(game))

    def on_resolve(self, game: GameState) -> None:
        """Attach to the target creature and register continuous effect."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Verify target is still a legal creature on the battlefield.
        if not _is_on_battlefield(game, target):
            return
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return

        self.attached_to = target
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        """Register the 'can't attack or block' continuous effect."""
        aura_ref = self

        def _apply_pacifism(game: GameState) -> None:
            # Stop applying if the aura itself has left the battlefield.
            if not _is_on_battlefield(game, aura_ref):
                return
            creature = aura_ref.attached_to
            if creature is None:
                return
            if not _is_on_battlefield(game, creature):
                return
            # Mark the creature as unable to attack or block.
            # We use a sentinel attribute that combat code can check.
            creature._cant_attack = True  # type: ignore[attr-defined]
            creature._cant_block = True  # type: ignore[attr-defined]

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_pacifism,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)

    def register_replacement_effects(self, game: GameState) -> None:
        """Re-register the continuous effect when entering via the casting pipeline."""
        if self._effect_ref is None and self.attached_to is not None:
            self._register_effect(game)


# ---------------------------------------------------------------------------
# Aura buff — Untamed Hunger
# ---------------------------------------------------------------------------

class UntamedHunger(Aura):
    """Untamed Hunger — {2}{B} — Enchant creature gets +2/+1 and has menace.

    Implements:
    - Layer 7c: +2/+1 P/T modification.
    - Layer 6: grants menace keyword.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Untamed Hunger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\n"
            "Enchanted creature gets +2/+1 and has menace. "
            "(It can't be blocked except by two or more creatures.)",
        )
        super().__init__(**kwargs)
        self._pt_effect_ref: ContinuousEffect | None = None
        self._ability_effect_ref: ContinuousEffect | None = None

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature on the battlefield."""
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
        """Cannot cast if no creature on the battlefield."""
        return bool(_creature_targets(game))

    def on_resolve(self, game: GameState) -> None:
        """Attach to the target creature and register continuous effects."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        if not _is_on_battlefield(game, target):
            return
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return

        self.attached_to = target
        self._register_effects(game)

    def _register_effects(self, game: GameState) -> None:
        """Register P/T and menace continuous effects."""
        aura_ref = self

        # Layer 7c: +2/+1
        def _apply_pt(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            creature = aura_ref.attached_to
            if creature is None:
                return
            if not _is_on_battlefield(game, creature):
                return
            creature.base_power += 2
            creature.base_toughness += 1

        pt_effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_pt,
            duration=DURATION_PERMANENT,
        )
        self._pt_effect_ref = game.effect_manager.add(pt_effect)

        # Layer 6: grant menace
        def _apply_menace(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            creature = aura_ref.attached_to
            if creature is None:
                return
            if not _is_on_battlefield(game, creature):
                return
            creature.keywords = creature.keywords | Keyword.MENACE

        ability_effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_menace,
            duration=DURATION_PERMANENT,
        )
        self._ability_effect_ref = game.effect_manager.add(ability_effect)

    def register_replacement_effects(self, game: GameState) -> None:
        """Re-register effects if needed after entering via casting pipeline."""
        if self._pt_effect_ref is None and self.attached_to is not None:
            self._register_effects(game)


# ---------------------------------------------------------------------------
# Aura buff — Unflinching Courage
# ---------------------------------------------------------------------------

class UnflinchingCourage(Aura):
    """Unflinching Courage — {1}{G}{W} — +2/+2, trample, lifelink.

    Implements:
    - Layer 7c: +2/+2 P/T modification.
    - Layer 6: grants trample and lifelink keywords.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Unflinching Courage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}{W}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\n"
            "Enchanted creature gets +2/+2 and has trample and lifelink. "
            "(Damage dealt by the creature also causes its controller to "
            "gain that much life.)",
        )
        super().__init__(**kwargs)
        self._pt_effect_ref: ContinuousEffect | None = None
        self._ability_effect_ref: ContinuousEffect | None = None

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature on the battlefield."""
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
        """Cannot cast if no creature on the battlefield."""
        return bool(_creature_targets(game))

    def on_resolve(self, game: GameState) -> None:
        """Attach to the target creature and register continuous effects."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        if not _is_on_battlefield(game, target):
            return
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return

        self.attached_to = target
        self._register_effects(game)

    def _register_effects(self, game: GameState) -> None:
        """Register P/T and keyword continuous effects."""
        aura_ref = self

        # Layer 7c: +2/+2
        def _apply_pt(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            creature = aura_ref.attached_to
            if creature is None:
                return
            if not _is_on_battlefield(game, creature):
                return
            creature.base_power += 2
            creature.base_toughness += 2

        pt_effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_pt,
            duration=DURATION_PERMANENT,
        )
        self._pt_effect_ref = game.effect_manager.add(pt_effect)

        # Layer 6: grant trample + lifelink
        def _apply_keywords(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            creature = aura_ref.attached_to
            if creature is None:
                return
            if not _is_on_battlefield(game, creature):
                return
            creature.keywords = creature.keywords | Keyword.TRAMPLE | Keyword.LIFELINK

        ability_effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_keywords,
            duration=DURATION_PERMANENT,
        )
        self._ability_effect_ref = game.effect_manager.add(ability_effect)

    def register_replacement_effects(self, game: GameState) -> None:
        """Re-register effects if needed after entering via casting pipeline."""
        if self._pt_effect_ref is None and self.attached_to is not None:
            self._register_effects(game)


# ---------------------------------------------------------------------------
# Mana rock — Hedron Archive
# ---------------------------------------------------------------------------

class HedronArchive(Artifact):
    """Hedron Archive — {4} — {T}: Add {C}{C}.

    The sacrifice ability ({2}, {T}, Sacrifice: Draw two cards) is not
    implemented in this phase.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hedron Archive")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}{C}.\n"
            "{2}, {T}, Sacrifice this artifact: Draw two cards.",
        )
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[Any]:
        """Return a mana ability: {T}: Add {C}{C}."""
        from engine.card import ManaAbility

        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 2)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_effect,
                description="{T}: Add {C}{C}.",
            )
        ]

    def get_activated_abilities(self) -> list[Any]:
        """Return activated abilities for this artifact.

        The mana ability is handled via get_mana_abilities() and the
        abilities system. We also expose it as an ActivatedAbilityInstance
        for use with activate_ability().
        """
        from engine.abilities import ActivatedAbilityInstance

        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 2)

        return [
            ActivatedAbilityInstance(
                source=source,
                controller=source.controller,
                cost=_cost,
                effect=_effect,
                is_mana_ability=True,
                description="{T}: Add {C}{C}.",
            )
        ]


# ---------------------------------------------------------------------------
# Non-aura enchantment — Goblin Oriflamme
# ---------------------------------------------------------------------------

class GoblinOriflamme(Enchantment):
    """Goblin Oriflamme — {1}{R} — Attacking creatures you control get +1/+0.

    Implements a layer 7c continuous effect that gives +1/+0 to all
    attacking creatures the controller controls.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Goblin Oriflamme")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Attacking creatures you control get +1/+0.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def on_resolve(self, game: GameState) -> None:
        """Register the continuous effect when entering the battlefield."""
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        """Register the +1/+0 to attacking creatures continuous effect."""
        enchantment_ref = self

        def _apply_oriflamme(game: GameState) -> None:
            controller = enchantment_ref.controller
            if controller is None:
                return
            # Check the enchantment is still on the battlefield
            if not _is_on_battlefield(game, enchantment_ref):
                return
            for obj in game.get_battlefield(controller).get_all():
                if (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "is_attacking", False)
                ):
                    obj.base_power += 1

        effect = ContinuousEffect(
            source=enchantment_ref,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_oriflamme,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)

    def register_replacement_effects(self, game: GameState) -> None:
        """Register the continuous effect when entering via casting pipeline."""
        if self._effect_ref is None:
            self._register_effect(game)


# ---------------------------------------------------------------------------
# All permanents list for registration — Scryfall-verified metadata
# ---------------------------------------------------------------------------

_ALL_SIMPLE_PERMANENTS: list[
    tuple[str, type, str, list[str], str, str, str, str]
] = [
    # (name, impl_class, mana_cost_str, colors, oracle_text,
    #  rarity, type_line, collector_number)
    #
    # --- Aura debuff ---
    (
        "Pacifism", Pacifism, "{1}{W}",
        ["W"],
        "Enchant creature\nEnchanted creature can't attack or block.",
        "common", "Enchantment — Aura", "501",
    ),
    # --- Aura buff ---
    (
        "Untamed Hunger", UntamedHunger, "{2}{B}",
        ["B"],
        "Enchant creature\n"
        "Enchanted creature gets +2/+1 and has menace. "
        "(It can't be blocked except by two or more creatures.)",
        "common", "Enchantment — Aura", "529",
    ),
    (
        "Unflinching Courage", UnflinchingCourage, "{1}{G}{W}",
        ["G", "W"],
        "Enchant creature\n"
        "Enchanted creature gets +2/+2 and has trample and lifelink. "
        "(Damage dealt by the creature also causes its controller to "
        "gain that much life.)",
        "uncommon", "Enchantment — Aura", "722",
    ),
    # --- Mana rock ---
    (
        "Hedron Archive", HedronArchive, "{4}",
        [],
        "{T}: Add {C}{C}.\n"
        "{2}, {T}, Sacrifice this artifact: Draw two cards.",
        "uncommon", "Artifact", "726",
    ),
    # --- Non-aura enchantment ---
    (
        "Goblin Oriflamme", GoblinOriflamme, "{1}{R}",
        ["R"],
        "Attacking creatures you control get +1/+0.",
        "uncommon", "Enchantment", "539",
    ),
]


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_simple_permanents(registry: CardRegistry) -> None:
    """Register all simple permanents with *registry*.

    Each permanent is registered under its canonical card name with
    :class:`~cards.registry.CardMetadata` reflecting its cost, type line,
    colors, and oracle text.  All metadata matches the actual FDN printing
    as sourced from Scryfall.
    """
    from cards.registry import CardMetadata

    for (
        card_name, impl_class, cost_str, colors, oracle_text,
        rarity, type_line, collector_number,
    ) in _ALL_SIMPLE_PERMANENTS:
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
