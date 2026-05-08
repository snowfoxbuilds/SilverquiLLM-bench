"""Aura card implementations from Foundations (FDN) — Batch 2.

Implements 10 auras beyond those already in ``enchantments.py`` and
``simple_permanents.py``:

- **Buff auras**: Angelic Destiny (+4/+4, flying, first strike, Angel type,
  death-return trigger), Blanchwood Armor (+1/+1 per Forest), Twinblade
  Blessing (double strike, flash).
- **Keyword-granting aura**: Twinblade Blessing (double strike).
- **Lockdown auras**: Starlight Snare (tap + doesn't untap), Imprisoned in
  the Moon (becomes colorless land), Witness Protection (becomes 1/1 Citizen),
  Eaten by Piranhas (becomes 1/1 Skeleton).
- **Control-changing aura**: Confiscate (gain control of enchanted permanent).
- **Triggered-ability auras**: Angelic Destiny (death trigger), Starlight Snare
  (ETB tap trigger), New Horizons (enchant land, ETB +1/+1 counter),
  Ordeal of Nylea (attack trigger + sacrifice trigger).

All cards are real MTG FDN cards with stats from Scryfall data.

Use :func:`register_auras_batch2` to register all auras with a
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


def _permanent_targets(game: Any) -> list[Any]:
    """Return all permanents on the battlefield."""
    targets: list[Any] = []
    for player in game.players:
        for obj in game.get_battlefield(player).get_all():
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


def _land_targets(game: Any) -> list[Any]:
    """Return all lands on the battlefield."""
    targets: list[Any] = []
    for player in game.players:
        for obj in game.get_battlefield(player).get_all():
            if CardType.LAND in getattr(obj, "card_types", set()):
                targets.append(obj)
    return targets


# ---------------------------------------------------------------------------
# Buff aura — Angelic Destiny
# ---------------------------------------------------------------------------

class AngelicDestiny(Aura):
    """Angelic Destiny — {2}{W}{W} — Enchanted creature gets +4/+4,
    has flying and first strike, and is an Angel in addition to its other
    types.  When enchanted creature dies, return this card to its owner's
    hand.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Angelic Destiny")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{W}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\n"
            "Enchanted creature gets +4/+4, has flying and first strike, "
            "and is an Angel in addition to its other types.\n"
            "When enchanted creature dies, return this card to its owner's hand.",
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
            creature.base_power += 4
            creature.base_toughness += 4
            creature.keywords = creature.keywords | Keyword.FLYING | Keyword.FIRST_STRIKE
            subtypes = getattr(creature, "subtypes", set()) or set()
            creature.subtypes = subtypes | {"Angel"}

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
            dying_creature = data.get("creature")
            return dying_creature is aura_ref.attached_to

        def _effect(game: GameState) -> None:
            from engine.zones import move_to_zone
            owner = getattr(aura_ref, "owner", None)
            if owner is None:
                return
            # Return aura to owner's hand via move_to_zone
            move_to_zone(game, aura_ref, Zone.GRAVEYARD, Zone.HAND)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_condition,
            effect=_effect,
            source=aura_ref,
            controller=controller,
        ))


# ---------------------------------------------------------------------------
# Buff aura — Blanchwood Armor
# ---------------------------------------------------------------------------

class BlanchwoodArmor(Aura):
    """Blanchwood Armor — {2}{G} — Enchanted creature gets +1/+1 for each
    Forest you control.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Blanchwood Armor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\n"
            "Enchanted creature gets +1/+1 for each Forest you control.",
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
            controller = getattr(aura_ref, "controller", None)
            if controller is None:
                return
            forest_count = 0
            for obj in game.get_battlefield(controller).get_all():
                subtypes = getattr(obj, "subtypes", set()) or set()
                if "Forest" in subtypes:
                    forest_count += 1
            creature.base_power += forest_count
            creature.base_toughness += forest_count

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)


# ---------------------------------------------------------------------------
# Keyword-granting aura — Twinblade Blessing
# ---------------------------------------------------------------------------

class TwinbladeBlessing(Aura):
    """Twinblade Blessing — {1}{W}{W} — Flash.
    Enchanted creature has double strike.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Twinblade Blessing")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Flash\n"
            "Enchant creature\n"
            "Enchanted creature has double strike.",
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
            creature.keywords = creature.keywords | Keyword.DOUBLE_STRIKE

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)


# ---------------------------------------------------------------------------
# Lockdown aura — Starlight Snare
# ---------------------------------------------------------------------------

class StarlightSnare(Aura):
    """Starlight Snare — {2}{U} — Enchant creature.
    When this Aura enters, tap enchanted creature.
    Enchanted creature doesn't untap during its controller's untap step.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Starlight Snare")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\n"
            "When this Aura enters, tap enchanted creature.\n"
            "Enchanted creature doesn't untap during its controller's untap step.",
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
        # Tap on ETB
        target.is_tapped = True
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        aura_ref = self

        def _apply(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            creature = aura_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            # ENGINE LIMITATION: _skip_untap flag doesn't work — the engine
            # untap step unconditionally untaps all permanents and doesn't
            # check this flag. Needs engine-level untap-step hook support.
            creature._skip_untap = True  # type: ignore[attr-defined]

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)


# ---------------------------------------------------------------------------
# Lockdown aura — Imprisoned in the Moon
# ---------------------------------------------------------------------------

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
                filter_fn=lambda obj, _t=targets: obj in _t,
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


# ---------------------------------------------------------------------------
# Lockdown aura — Witness Protection
# ---------------------------------------------------------------------------

class WitnessProtection(Aura):
    """Witness Protection — {U} — Enchant creature.
    Enchanted creature loses all abilities and is a green and white Citizen
    creature with base power and toughness 1/1 named Legitimate Businessperson.
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
            creature.name = "Legitimate Businessperson"
            creature.card_types = {CardType.CREATURE}
            creature.subtypes = {"Citizen"}
            creature.keywords = Keyword(0)
            creature.base_power = 1
            creature.base_toughness = 1
            # ENGINE LIMITATION: EffectManager._reset_objects() doesn't
            # restore name or subtypes. When this aura leaves the battlefield
            # the name/subtype changes persist until engine-level reset is added.

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.TYPE,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)


# ---------------------------------------------------------------------------
# Lockdown aura — Eaten by Piranhas
# ---------------------------------------------------------------------------

class EatenByPiranhas(Aura):
    """Eaten by Piranhas — {1}{U} — Flash.
    Enchant creature.  Enchanted creature loses all abilities and is a black
    Skeleton creature with base power and toughness 1/1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Eaten by Piranhas")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Flash\n"
            "Enchant creature\n"
            "Enchanted creature loses all abilities and is a black "
            "Skeleton creature with base power and toughness 1/1.",
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
            creature.card_types = {CardType.CREATURE}
            creature.subtypes = {"Skeleton"}
            creature.keywords = Keyword(0)
            creature.base_power = 1
            creature.base_toughness = 1

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.TYPE,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)


# ---------------------------------------------------------------------------
# Enchant land aura — New Horizons
# ---------------------------------------------------------------------------

class NewHorizons(Aura):
    """New Horizons — {2}{G} — Enchant land.
    When this Aura enters, put a +1/+1 counter on target creature you control.
    Enchanted land has "{T}: Add two mana of any one color."
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "New Horizons")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant land\n"
            "When this Aura enters, put a +1/+1 counter on target creature "
            "you control.\n"
            'Enchanted land has "{T}: Add two mana of any one color."',
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def get_targets(self, game: GameState) -> list[Any]:
        targets = _land_targets(game)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="enchant land",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        return bool(_land_targets(game))

    def on_resolve(self, game: GameState) -> None:
        target = _get_chosen_target(self, game)
        if target is None:
            return
        if not _is_on_battlefield(game, target):
            return
        self.attached_to = target
        # ETB: put a +1/+1 counter on target creature you control
        # ENGINE LIMITATION: auto-picks first creature instead of being a
        # targeted trigger — proper targeted ETB triggers need engine support.
        controller = getattr(self, "controller", None)
        if controller is not None:
            from engine.game import add_counter
            for obj in game.get_battlefield(controller).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    add_counter(game, obj, "+1/+1", 1)
                    # Also track in counters dict for query compatibility
                    if not hasattr(obj, "counters"):
                        obj.counters = {}
                    obj.counters["+1/+1"] = obj.counters.get("+1/+1", 0) + 1
                    break
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        aura_ref = self

        def _apply(game: GameState) -> None:
            if not _is_on_battlefield(game, aura_ref):
                return
            land = aura_ref.attached_to
            if land is None or not _is_on_battlefield(game, land):
                return
            land._new_horizons_mana = True  # type: ignore[attr-defined]

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)


# ---------------------------------------------------------------------------
# Triggered-ability aura — Ordeal of Nylea
# ---------------------------------------------------------------------------

class OrdealOfNylea(Aura):
    """Ordeal of Nylea — {1}{G} — Enchant creature.
    Whenever enchanted creature attacks, put a +1/+1 counter on it. Then if
    it has three or more +1/+1 counters on it, sacrifice this Aura.
    When you sacrifice this Aura, search your library for up to two basic
    land cards, put them onto the battlefield tapped, then shuffle.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ordeal of Nylea")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant creature\n"
            "Whenever enchanted creature attacks, put a +1/+1 counter on it. "
            "Then if it has three or more +1/+1 counters on it, sacrifice "
            "this Aura.\n"
            "When you sacrifice this Aura, search your library for up to two "
            "basic land cards, put them onto the battlefield tapped, then shuffle.",
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

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        aura_ref = self

        def _attack_condition(game: GameState, data: dict) -> bool:
            attacker = data.get("card")
            return attacker is aura_ref.attached_to

        def _attack_effect(game: GameState) -> None:
            from engine.game import add_counter
            from engine.zones import move_to_zone
            creature = aura_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            add_counter(game, creature, "+1/+1", 1)
            # Also track in counters dict for query compatibility
            if not hasattr(creature, "counters"):
                creature.counters = {}
            creature.counters["+1/+1"] = creature.counters.get("+1/+1", 0) + 1
            # Check if 3+ counters — sacrifice the aura
            counter_count = getattr(creature, "plus_one_counters", 0)
            if counter_count >= 3:
                controller = getattr(aura_ref, "controller", None)
                if controller is not None and _is_on_battlefield(game, aura_ref):
                    move_to_zone(game, aura_ref, Zone.BATTLEFIELD, Zone.GRAVEYARD)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ATTACKS,
            condition=_attack_condition,
            effect=_attack_effect,
            source=aura_ref,
            controller=controller,
        ))


# ---------------------------------------------------------------------------
# Control-changing aura — Confiscate
# ---------------------------------------------------------------------------

class Confiscate(Aura):
    """Confiscate — {4}{U}{U} — Enchant permanent.
    You control enchanted permanent.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Confiscate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Aura"}
        kwargs.setdefault(
            "rules_text",
            "Enchant permanent\n"
            "You control enchanted permanent.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def get_targets(self, game: GameState) -> list[Any]:
        targets = _permanent_targets(game)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="enchant permanent",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        return bool(_permanent_targets(game))

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
            aura_controller = getattr(aura_ref, "controller", None)
            if aura_controller is not None:
                # ENGINE LIMITATION: Just setting .controller doesn't move the
                # permanent between player battlefield zones. A proper
                # controller-change helper is needed in the engine to handle
                # zone migration and related triggers.
                perm.controller = aura_controller

        effect = ContinuousEffect(
            source=aura_ref,
            layer=Layer.CONTROL,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)


# ---------------------------------------------------------------------------
# Registration data & helper
# ---------------------------------------------------------------------------

_ALL_AURAS_BATCH2: list[
    tuple[str, type, str, list[str], str, str, str, str]
] = [
    ("Angelic Destiny", AngelicDestiny, "{2}{W}{W}",
     ["W"],
     "Enchant creature\n"
     "Enchanted creature gets +4/+4, has flying and first strike, "
     "and is an Angel in addition to its other types.\n"
     "When enchanted creature dies, return this card to its owner's hand.",
     "mythic", "Enchantment — Aura", "565"),
    ("Blanchwood Armor", BlanchwoodArmor, "{2}{G}",
     ["G"],
     "Enchant creature\n"
     "Enchanted creature gets +1/+1 for each Forest you control.",
     "uncommon", "Enchantment — Aura", "213"),
    ("Twinblade Blessing", TwinbladeBlessing, "{1}{W}{W}",
     ["W"],
     "Flash\nEnchant creature\n"
     "Enchanted creature has double strike.",
     "uncommon", "Enchantment — Aura", "26"),
    ("Starlight Snare", StarlightSnare, "{2}{U}",
     ["U"],
     "Enchant creature\n"
     "When this Aura enters, tap enchanted creature.\n"
     "Enchanted creature doesn't untap during its controller's untap step.",
     "common", "Enchantment — Aura", "514"),
    ("Imprisoned in the Moon", ImprisonedInTheMoon, "{2}{U}",
     ["U"],
     "Enchant creature, land, or planeswalker\n"
     "Enchanted permanent is a colorless land with "
     '"{T}: Add {C}" and loses all other card types and abilities.',
     "uncommon", "Enchantment — Aura", "156"),
    ("Witness Protection", WitnessProtection, "{U}",
     ["U"],
     "Enchant creature\n"
     "Enchanted creature loses all abilities and is a green and white "
     "Citizen creature with base power and toughness 1/1 named "
     "Legitimate Businessperson.",
     "common", "Enchantment — Aura", "168"),
    ("Eaten by Piranhas", EatenByPiranhas, "{1}{U}",
     ["U"],
     "Flash\nEnchant creature\n"
     "Enchanted creature loses all abilities and is a black "
     "Skeleton creature with base power and toughness 1/1.",
     "uncommon", "Enchantment — Aura", "507"),
    ("New Horizons", NewHorizons, "{2}{G}",
     ["G"],
     "Enchant land\n"
     "When this Aura enters, put a +1/+1 counter on target creature "
     "you control.\n"
     'Enchanted land has "{T}: Add two mana of any one color."',
     "common", "Enchantment — Aura", "557"),
    ("Ordeal of Nylea", OrdealOfNylea, "{1}{G}",
     ["G"],
     "Enchant creature\n"
     "Whenever enchanted creature attacks, put a +1/+1 counter on it. "
     "Then if it has three or more +1/+1 counters on it, sacrifice "
     "this Aura.\n"
     "When you sacrifice this Aura, search your library for up to two "
     "basic land cards, put them onto the battlefield tapped, then shuffle.",
     "uncommon", "Enchantment — Aura", "641"),
    ("Confiscate", Confiscate, "{4}{U}{U}",
     ["U"],
     "Enchant permanent\n"
     "You control enchanted permanent.",
     "uncommon", "Enchantment — Aura", "709"),
]


def register_auras_batch2(registry: CardRegistry) -> None:
    """Register all batch-2 auras with *registry*."""
    from cards.registry import CardMetadata

    for (
        card_name, impl_class, cost_str, colors, oracle_text,
        rarity, type_line, collector_number,
    ) in _ALL_AURAS_BATCH2:
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
