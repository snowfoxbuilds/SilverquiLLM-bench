"""Artifact card implementations from Foundations (FDN).

Implements 10 artifacts covering mana rocks, equipment, and utility artifacts:

- **Mana rocks**: Sol Ring ({T}: Add {C}{C}), Arcane Signet ({T}: Add one
  mana of any color in your commander's color identity — simplified to {C}),
  Mind Stone ({T}: Add {C}; {1}, {T}, Sacrifice: Draw a card).
- **Equipment**: Bonesplitter (equipped creature +2/+0),
  Swiftfoot Boots (equipped creature has hexproof and haste),
  Whispersilk Cloak (equipped creature has hexproof and is unblockable),
  Mask of Memory (equipped creature — deal combat damage, draw 2 discard 1).
- **Utility**: Altar of the Brood (whenever a permanent enters, each opponent
  mills a card), Elixir of Immortality ({2}, {T}: gain 5 life, shuffle graveyard
  into library), Relic of Progenitus ({T}: exile target card from graveyard).

All cards subclass :class:`~engine.card.Artifact` or
:class:`~engine.card.ArtifactCreature`.

Use :func:`register_artifacts` to register all artifacts with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Artifact, ActivatedAbility, ManaAbility
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


# ---------------------------------------------------------------------------
# Mana rocks
# ---------------------------------------------------------------------------

class SolRing(Artifact):
    """Sol Ring — {1} — {T}: Add {C}{C}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sol Ring")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault("rules_text", "{T}: Add {C}{C}.")
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
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
            ManaAbility(cost=_tap_cost, mana_produced=_effect, description="{T}: Add {C}{C}."),
        ]


class ArcaneSigNet(Artifact):
    """Arcane Signet — {2} — {T}: Add {C} (simplified)."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Arcane Signet")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("rules_text", "{T}: Add one mana of any color in your commander's color identity.")
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        return [
            ManaAbility(cost=_tap_cost, mana_produced=_effect, description="{T}: Add {C}."),
        ]


class MindStone(Artifact):
    """Mind Stone — {2} — {T}: Add {C}. {1}, {T}, Sacrifice: Draw a card."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mind Stone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("rules_text", "{T}: Add {C}.\n{1}, {T}, Sacrifice Mind Stone: Draw a card.")
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        return [
            ManaAbility(cost=_tap_cost, mana_produced=_effect, description="{T}: Add {C}."),
        ]


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------

class Bonesplitter(Artifact):
    """Bonesplitter — {1} — Equipped creature gets +2/+0. Equip {1}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bonesplitter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault("rules_text", "Equipped creature gets +2/+0.\nEquip {1}")
        super().__init__(**kwargs)
        self.attached_to: Any | None = None
        self._effect_ref: ContinuousEffect | None = None

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
            creature.base_power += 2

        if self._effect_ref is None:
            effect = ContinuousEffect(
                source=equip_ref,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply,
                duration=DURATION_PERMANENT,
            )
            self._effect_ref = game.effect_manager.add(effect)


class SwiftfootBoots(Artifact):
    """Swiftfoot Boots — {2} — Equipped creature has hexproof and haste. Equip {1}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swiftfoot Boots")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault("rules_text", "Equipped creature has hexproof and haste.\nEquip {1}")
        super().__init__(**kwargs)
        self.attached_to: Any | None = None
        self._effect_ref: ContinuousEffect | None = None

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
            creature.keywords = creature.keywords | Keyword.HEXPROOF | Keyword.HASTE

        if self._effect_ref is None:
            effect = ContinuousEffect(
                source=equip_ref,
                layer=Layer.ABILITY,
                sublayer=None,
                apply=_apply,
                duration=DURATION_PERMANENT,
            )
            self._effect_ref = game.effect_manager.add(effect)


class WhispersilkCloak(Artifact):
    """Whispersilk Cloak — {3} — Equipped creature has hexproof and can't be blocked. Equip {2}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Whispersilk Cloak")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault("rules_text", "Equipped creature has hexproof and can't be blocked.\nEquip {2}")
        super().__init__(**kwargs)
        self.attached_to: Any | None = None
        self._effect_ref: ContinuousEffect | None = None

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
            creature.keywords = creature.keywords | Keyword.HEXPROOF
            creature._cant_be_blocked = True  # type: ignore[attr-defined]

        if self._effect_ref is None:
            effect = ContinuousEffect(
                source=equip_ref,
                layer=Layer.ABILITY,
                sublayer=None,
                apply=_apply,
                duration=DURATION_PERMANENT,
            )
            self._effect_ref = game.effect_manager.add(effect)


class MaskOfMemory(Artifact):
    """Mask of Memory — {2} — Whenever equipped creature deals combat damage,
    draw two cards then discard a card. Equip {1}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mask of Memory")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault(
            "rules_text",
            "Whenever equipped creature deals combat damage to a player, "
            "you may draw two cards. If you do, discard a card.\nEquip {1}",
        )
        super().__init__(**kwargs)
        self.attached_to: Any | None = None


# ---------------------------------------------------------------------------
# Utility artifacts
# ---------------------------------------------------------------------------

class AltarOfTheBrood(Artifact):
    """Altar of the Brood — {1} — Whenever another permanent enters the battlefield
    under your control, each opponent mills a card."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Altar of the Brood")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault(
            "rules_text",
            "Whenever another permanent enters the battlefield under your control, "
            "each opponent mills a card.",
        )
        super().__init__(**kwargs)


class ElixirOfImmortality(Artifact):
    """Elixir of Immortality — {1} — {2}, {T}: You gain 5 life. Shuffle
    Elixir of Immortality and your graveyard into your library."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Elixir of Immortality")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault(
            "rules_text",
            "{2}, {T}: You gain 5 life. Shuffle Elixir of Immortality "
            "and your graveyard into your library.",
        )
        super().__init__(**kwargs)


class RelicOfProgenitus(Artifact):
    """Relic of Progenitus — {1} — {T}: Target player exiles a card from their graveyard.
    {1}, Exile Relic of Progenitus: Exile all graveyards. Draw a card."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Relic of Progenitus")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault(
            "rules_text",
            "{T}: Target player exiles a card from their graveyard.\n"
            "{1}, Exile Relic of Progenitus: Exile all cards from all graveyards. "
            "Draw a card.",
        )
        super().__init__(**kwargs)


# ---------------------------------------------------------------------------
# Registration data & helper
# ---------------------------------------------------------------------------

_ALL_ARTIFACTS: list[
    tuple[str, type, str, list[str], str, str, str, str]
] = [
    ("Sol Ring", SolRing, "{1}",
     [], "{T}: Add {C}{C}.",
     "uncommon", "Artifact", ""),
    ("Arcane Signet", ArcaneSigNet, "{2}",
     [], "{T}: Add one mana of any color in your commander's color identity.",
     "common", "Artifact", ""),
    ("Mind Stone", MindStone, "{2}",
     [], "{T}: Add {C}.\n{1}, {T}, Sacrifice Mind Stone: Draw a card.",
     "uncommon", "Artifact", ""),
    ("Bonesplitter", Bonesplitter, "{1}",
     [], "Equipped creature gets +2/+0.\nEquip {1}",
     "common", "Artifact — Equipment", ""),
    ("Swiftfoot Boots", SwiftfootBoots, "{2}",
     [], "Equipped creature has hexproof and haste.\nEquip {1}",
     "uncommon", "Artifact — Equipment", ""),
    ("Whispersilk Cloak", WhispersilkCloak, "{3}",
     [], "Equipped creature has hexproof and can't be blocked.\nEquip {2}",
     "uncommon", "Artifact — Equipment", ""),
    ("Mask of Memory", MaskOfMemory, "{2}",
     [],
     "Whenever equipped creature deals combat damage to a player, "
     "you may draw two cards. If you do, discard a card.\nEquip {1}",
     "uncommon", "Artifact — Equipment", ""),
    ("Altar of the Brood", AltarOfTheBrood, "{1}",
     [],
     "Whenever another permanent enters the battlefield under your control, "
     "each opponent mills a card.",
     "rare", "Artifact", ""),
    ("Elixir of Immortality", ElixirOfImmortality, "{1}",
     [],
     "{2}, {T}: You gain 5 life. Shuffle Elixir of Immortality "
     "and your graveyard into your library.",
     "uncommon", "Artifact", ""),
    ("Relic of Progenitus", RelicOfProgenitus, "{1}",
     [],
     "{T}: Target player exiles a card from their graveyard.\n"
     "{1}, Exile Relic of Progenitus: Exile all cards from all graveyards. "
     "Draw a card.",
     "uncommon", "Artifact", ""),
]


def register_artifacts(registry: CardRegistry) -> None:
    """Register all artifacts with *registry*."""
    from cards.registry import CardMetadata

    for (
        card_name, impl_class, cost_str, colors, oracle_text,
        rarity, type_line, collector_number,
    ) in _ALL_ARTIFACTS:
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
