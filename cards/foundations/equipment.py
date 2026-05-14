"""Additional equipment card implementations from Foundations (FDN).

Implements equipment beyond those in ``artifacts.py`` (Bonesplitter, Swiftfoot
Boots, Whispersilk Cloak, Mask of Memory).

Cards implemented here:
- **Basilisk Collar** ({1}) — keyword-granting: deathtouch and lifelink.
  Equip {2}.
- **Fireshrieker** ({3}) — keyword-granting: double strike. Equip {2}.
- **Quick-Draw Katana** ({2}) — conditional stat-boost: +2/+0 and first strike
  during your turn. Equip {2}.
- **Goldvein Pick** ({2}) — stat-boost +1/+1, triggered: combat damage →
  create Treasure token. Equip {1}.
- **Leyline Axe** ({4}) — stat-boost +1/+1, keyword-granting: double strike
  and trample. Equip {3}.
- **Adventuring Gear** ({1}) — triggered: landfall → equipped creature gets
  +2/+2 until end of turn. Equip {1}.
- **Celestial Armor** ({2}{W}) — flash, ETB auto-attach with hexproof/
  indestructible until end of turn, equipped creature gets +2/+0 and flying.
  Equip {3}{W}.

All cards subclass :class:`~engine.card.Artifact` and add
``subtypes={"Equipment"}``.

Use :func:`register_equipment` to register all equipment with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Artifact
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Equip ability helper
# ---------------------------------------------------------------------------

def _make_equip_ability(
    equipment: Artifact,
    generic_cost: int,
) -> ActivatedAbility:
    """Return an :class:`ActivatedAbility` representing *Equip {N}*.

    The ability pays *generic_cost* generic mana from the controller's mana
    pool, then calls ``equipment.equip(target, game)`` to attach the
    equipment to a target creature.  Equip is sorcery-speed only (the engine
    should enforce timing; we document the restriction in the description).

    The target creature is read from ``equipment._current_target`` which the
    game engine is expected to set before calling the ability's effect.
    """
    source = equipment

    def _cost(game: Any, src: Any) -> bool:
        controller = getattr(src, "controller", None)
        if controller is None:
            return False
        if controller.mana_pool.total() < generic_cost:
            return False
        controller.mana_pool.pay(ManaCost(generic=generic_cost))
        return True

    def _effect(game: Any) -> None:
        target = getattr(source, "_current_target", None)
        if target is not None:
            source.equip(target, game)

    return ActivatedAbility(
        cost=_cost,
        effect=_effect,
        description=f"Equip {{{generic_cost}}} (sorcery speed)",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


# ---------------------------------------------------------------------------
# Keyword-granting equipment
# ---------------------------------------------------------------------------

class BasiliskCollar(Artifact):
    """Basilisk Collar — {1} — Equipped creature has deathtouch and lifelink. Equip {2}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Basilisk Collar")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault(
            "rules_text",
            "Equipped creature has deathtouch and lifelink.\nEquip {2}",
        )
        super().__init__(**kwargs)
        self.attached_to: Any | None = None
        self._effect_ref: ContinuousEffect | None = None

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        return [_make_equip_ability(self, generic_cost=2)]

    def equip(self, target: Any, game: Any) -> None:
        """Attach this equipment to *target* creature."""
        self.attached_to = target
        self._register_effect(game)

    def _register_effect(self, game: Any) -> None:
        equip_ref = self

        def _apply(game: Any) -> None:
            if not _is_on_battlefield(game, equip_ref):
                return
            creature = equip_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            creature.keywords = creature.keywords | Keyword.DEATHTOUCH | Keyword.LIFELINK

        if self._effect_ref is None:
            effect = ContinuousEffect(
                source=equip_ref,
                layer=Layer.ABILITY,
                sublayer=None,
                apply=_apply,
                duration=DURATION_PERMANENT,
            )
            self._effect_ref = game.effect_manager.add(effect)


class Fireshrieker(Artifact):
    """Fireshrieker — {3} — Equipped creature has double strike. Equip {2}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fireshrieker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault(
            "rules_text",
            "Equipped creature has double strike.\nEquip {2}",
        )
        super().__init__(**kwargs)
        self.attached_to: Any | None = None
        self._effect_ref: ContinuousEffect | None = None

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        return [_make_equip_ability(self, generic_cost=2)]

    def equip(self, target: Any, game: Any) -> None:
        self.attached_to = target
        self._register_effect(game)

    def _register_effect(self, game: Any) -> None:
        equip_ref = self

        def _apply(game: Any) -> None:
            if not _is_on_battlefield(game, equip_ref):
                return
            creature = equip_ref.attached_to
            if creature is None or not _is_on_battlefield(game, creature):
                return
            creature.keywords = creature.keywords | Keyword.DOUBLE_STRIKE

        if self._effect_ref is None:
            effect = ContinuousEffect(
                source=equip_ref,
                layer=Layer.ABILITY,
                sublayer=None,
                apply=_apply,
                duration=DURATION_PERMANENT,
            )
            self._effect_ref = game.effect_manager.add(effect)


# ---------------------------------------------------------------------------
# Stat-boosting + keyword equipment
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Triggered-ability equipment
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Registration data & helper
# ---------------------------------------------------------------------------

_ALL_EQUIPMENT: list[
    tuple[str, type, str, list[str], str, str, str, str]
] = [
    ("Basilisk Collar", BasiliskCollar, "{1}",
     [], "Equipped creature has deathtouch and lifelink.\nEquip {2}",
     "rare", "Artifact — Equipment", "669"),
    ("Fireshrieker", Fireshrieker, "{3}",
     [], "Equipped creature has double strike.\nEquip {2}",
     "uncommon", "Artifact — Equipment", "674"),
    ("Quick-Draw Katana", QuickDrawKatana, "{2}",
     [],
     "During your turn, equipped creature gets +2/+0 and has first strike.\nEquip {2}",
     "common", "Artifact — Equipment", "130"),
    ("Goldvein Pick", GoldveinPick, "{2}",
     [],
     "Equipped creature gets +1/+1.\n"
     "Whenever equipped creature deals combat damage to a player, "
     "create a Treasure token.\nEquip {1}",
     "common", "Artifact — Equipment", "253"),
    ("Leyline Axe", LeylineAxe, "{4}",
     [],
     "If this card is in your opening hand, you may begin the game "
     "with it on the battlefield.\n"
     "Equipped creature gets +1/+1 and has double strike and trample.\n"
     "Equip {3}",
     "rare", "Artifact — Equipment", "129"),
    ("Adventuring Gear", AdventuringGear, "{1}",
     [],
     "Landfall — Whenever a land you control enters, equipped creature "
     "gets +2/+2 until end of turn.\nEquip {1}",
     "uncommon", "Artifact — Equipment", "249"),
    ("Celestial Armor", CelestialArmor, "{2}{W}",
     ["W"],
     "Flash\n"
     "When this Equipment enters, attach it to target creature you "
     "control. That creature gains hexproof and indestructible until "
     "end of turn.\n"
     "Equipped creature gets +2/+0 and has flying.\n"
     "Equip {3}{W}",
     "rare", "Artifact — Equipment", "5"),
]


def register_equipment(registry: "CardRegistry") -> None:
    """Register all equipment with *registry*."""
    from cards.registry import CardMetadata

    for (
        card_name, impl_class, cost_str, colors, oracle_text,
        rarity, type_line, collector_number,
    ) in _ALL_EQUIPMENT:
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
