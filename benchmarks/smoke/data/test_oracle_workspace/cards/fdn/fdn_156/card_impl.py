"""Card implementation for Imprisoned in the Moon."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from engine.abilities import tap_cost
from engine.card import Aura, ManaAbility
from engine.continuous_effects import (
    DURATION_PERMANENT,
    ContinuousEffect,
    Layer,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class ImprisonedInTheMoonAbility1:
    text = 'Enchant creature, land, or planeswalker'


class ImprisonedInTheMoonAbility2:
    text = 'Enchanted permanent is a colorless land with "{T}: Add {C}" and loses all other card types and abilities.'


# endregion Printed abilities


_ABILITY_GETTERS = ("get_activated_abilities", "get_mana_abilities", "get_loyalty_abilities")


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


def _imprisoned(game: Any, perm: Any) -> bool:
    """Whether an Imprisoned in the Moon on the battlefield enchants *perm*."""
    return _is_on_battlefield(game, perm) and any(
        isinstance(obj, ImprisonedInTheMoon) and obj.attached_to is perm
        for player in game.players
        for obj in game.get_battlefield(player).get_all()
    )


def _colorless_mana_ability(perm: Any) -> ManaAbility:
    """The "{T}: Add {C}" the enchanted permanent has."""

    def _effect(game: GameState) -> None:
        controller = perm.controller
        if controller is not None:
            controller.mana_pool.add(ManaType.COLORLESS, 1)

    return ManaAbility(
        cost=tap_cost,
        mana_produced=_effect,
        description="{T}: Add {C}.",
        printed=ImprisonedInTheMoonAbility2,
    )


def _imprisonable(game: Any, perm: Any, name: str) -> Any:
    """*perm*'s ability getter *name*, answering what an imprisoned permanent
    has while an Imprisoned in the Moon enchants it, and otherwise what it
    answered before."""
    before = perm.__dict__.get(name)
    colorless = _colorless_mana_ability(perm)

    def getter(*_: Any) -> list[Any]:
        if _imprisoned(game, perm):
            return [colorless] if name == "get_mana_abilities" else []
        # Resolved now, not at install: the permanent may have become a copy.
        own = before if before is not None else getattr(type(perm), name, None)
        if own is None:
            return []
        if before is None:
            own = own.__get__(perm)
        return list(own(game) if inspect.signature(own).parameters else own())

    getter.imprisonable = True  # type: ignore[attr-defined]
    return getter


def _remove_abilities(game: Any, perm: Any) -> None:
    """Layer 6: *perm* loses its keywords and its activated, mana and loyalty
    abilities, and has "{T}: Add {C}".

    Abilities live as getters on the object, so they are routed through
    :func:`_imprisonable` once and answer by whether the permanent is still
    imprisoned when asked; ``_reset_characteristics`` never has to undo them.
    """
    perm.keywords = Keyword(0)
    for name in _ABILITY_GETTERS:
        has_getter = name == "get_mana_abilities" or hasattr(perm, name)
        if has_getter and not getattr(perm.__dict__.get(name), "imprisonable", False):
            setattr(perm, name, _imprisonable(game, perm, name))


def _change_type(perm: Any) -> None:
    """Layer 4: *perm* is a land with no other card types or subtypes."""
    perm.__dict__.setdefault("_subtypes_before_effects", set(perm.subtypes))
    perm.card_types = {CardType.LAND}
    perm.subtypes = set()


def _make_colorless(perm: Any) -> None:
    """Layer 5: *perm* is colorless."""
    perm.__dict__.setdefault("_colors_before_effects", getattr(perm, "colors", None))
    perm.colors = set()


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
        self._register_effects(game, target)

    # -- continuous effects -----------------------------------------------
    #
    # Layer 4 (TYPE): The permanent becomes a land, losing all other card
    #   types and subtypes.
    # Layer 5 (COLOR): The permanent becomes colorless.
    # Layer 6 (ABILITY): The permanent loses its keywords and its activated,
    #   mana and loyalty abilities, and has "{T}: Add {C}".
    #
    # ENGINE LIMITATION: triggered and static abilities are registered by the
    # card itself rather than read from its characteristics, so the engine
    # cannot take them away; an imprisoned permanent keeps them.

    def _imprisons(self, game: GameState, perm: Any) -> bool:
        return (
            self.attached_to is perm
            and _is_on_battlefield(game, self)
            and _is_on_battlefield(game, perm)
        )

    def _register_effects(self, game: GameState, perm: Any) -> None:
        aura_ref = self

        def _apply_type(game: GameState) -> None:
            if aura_ref._imprisons(game, perm):
                _change_type(perm)

        def _apply_color(game: GameState) -> None:
            if aura_ref._imprisons(game, perm):
                _make_colorless(perm)

        def _apply_ability(game: GameState) -> None:
            if aura_ref._imprisons(game, perm):
                _remove_abilities(game, perm)

        for layer, apply in ((Layer.TYPE, _apply_type), (Layer.COLOR, _apply_color), (Layer.ABILITY, _apply_ability)):
            game.effect_manager.add(ContinuousEffect(
                source=aura_ref,
                layer=layer,
                sublayer=None,
                apply=apply,
                duration=DURATION_PERMANENT,
            ))
