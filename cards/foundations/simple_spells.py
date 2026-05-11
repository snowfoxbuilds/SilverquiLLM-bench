"""Simple instant and sorcery spell implementations from Foundations (FDN).

Implements 10 non-creature spells covering the major spell categories:

- **Damage**: Burst Lightning (2 to any target), Incinerating Blast (6 to creature).
- **Buff**: Giant Growth (+3/+3 until end of turn via layer 7c).
- **Draw**: Quick Study (draw 2).
- **Removal**: Hero's Downfall (destroy creature or planeswalker).
- **Counter**: Negate (counter noncreature), Cancel (counter any spell).
- **Utility**: Disenchant (destroy artifact/enchantment), Pilfer (hand disruption),
  Cemetery Recruitment (graveyard creature to hand).

Each spell subclasses :class:`~engine.card.Instant` or
:class:`~engine.card.Sorcery` and overrides :meth:`get_targets` and
:meth:`on_resolve`.

All cards are real FDN set cards verified against Scryfall.

Use :func:`register_simple_spells` to register all spells with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Helper — retrieve chosen target for targeted spells
# ---------------------------------------------------------------------------

def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell.

    Looks for ``chosen_targets`` (set by :func:`cast_spell` during the
    real casting pipeline) first, then falls back to the test-backdoor
    attribute ``_resolve_target``.
    """
    # Real pipeline: targets stored by cast_spell on the card
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    # Test backdoor: attribute set directly by test code
    return getattr(card, "_resolve_target", None)


# ---------------------------------------------------------------------------
# Damage spells
# ---------------------------------------------------------------------------

class BurstLightning(Instant):
    """Burst Lightning — {R} — Deal 2 damage to any target (base mode).

    Kicker {4} is not implemented; always deals 2 damage.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Burst Lightning")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        kwargs.setdefault(
            "rules_text",
            "Kicker {4}\n"
            "Burst Lightning deals 2 damage to any target. "
            "If this spell was kicked, it deals 4 damage instead.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Any target: any creature on the battlefield or any player."""
        targets: list[Any] = []
        for player in game.players:
            targets.append(player)
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="any target",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Deal 2 damage to the chosen target (base, unkicked)."""
        from engine.game import deal_damage

        target = _get_chosen_target(self, game)
        if target is not None:
            deal_damage(game, self, target, 2)


class IncineratingBlast(Sorcery):
    """Incinerating Blast — {4}{R} — Deal 6 damage to target creature.

    The optional loot effect (discard/draw) is not implemented.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Incinerating Blast")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Incinerating Blast deals 6 damage to target creature.\n"
            "You may discard a card. If you do, draw a card.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature on the battlefield."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        """Cannot cast if no creature on the battlefield."""
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    return True
        return False

    def on_resolve(self, game: GameState) -> None:
        """Deal 6 damage to the chosen creature."""
        from engine.game import deal_damage

        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Verify target is still a creature on the battlefield.
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    deal_damage(game, self, target, 6)
                    return


# ---------------------------------------------------------------------------
# Buff spells
# ---------------------------------------------------------------------------

class GiantGrowth(Instant):
    """Giant Growth — {G} — Target creature gets +3/+3 until end of turn."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Giant Growth")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        kwargs.setdefault(
            "rules_text", "Target creature gets +3/+3 until end of turn."
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature on the battlefield."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Apply +3/+3 until end of turn as a continuous effect in layer 7c."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Verify target is still a legal creature on the battlefield.
        still_valid = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    still_valid = True
                    break
        if not still_valid:
            return

        # Create a continuous effect that gives +3/+3 in layer 7c.
        creature_ref = target

        def _apply_buff(game: GameState) -> None:
            # Only apply if the creature is still on the battlefield.
            for p in game.players:
                if game.get_battlefield(p).contains(creature_ref):
                    creature_ref.base_power += 3
                    creature_ref.base_toughness += 3
                    return

        effect = ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_buff,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)


# ---------------------------------------------------------------------------
# Draw spells
# ---------------------------------------------------------------------------

class QuickStudy(Instant):
    """Quick Study — {2}{U} — Draw two cards."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Quick Study")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("rules_text", "Draw two cards.")
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """No targets — Quick Study doesn't target."""
        return []

    def on_resolve(self, game: GameState) -> None:
        """Draw 2 cards for the controller."""
        from engine.game import draw_card

        controller = self.controller
        if controller is not None:
            draw_card(game, controller)
            draw_card(game, controller)


# ---------------------------------------------------------------------------
# Removal spells
# ---------------------------------------------------------------------------

class HerosDownfall(Instant):
    """Hero's Downfall — {1}{B}{B} — Destroy target creature or planeswalker."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hero's Downfall")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("rules_text", "Destroy target creature or planeswalker.")
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature or planeswalker on the battlefield."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                card_types = getattr(obj, "card_types", set())
                if CardType.CREATURE in card_types or CardType.PLANESWALKER in card_types:
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="target creature or planeswalker",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Destroy the target creature or planeswalker."""
        from engine.game import destroy

        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Verify target is still a legal creature or planeswalker on the battlefield.
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                card_types = getattr(target, "card_types", set())
                if CardType.CREATURE in card_types or CardType.PLANESWALKER in card_types:
                    destroy(game, target)
                    return


# ---------------------------------------------------------------------------
# Counter spells
# ---------------------------------------------------------------------------

class Negate(Instant):
    """Negate — {1}{U} — Counter target noncreature spell."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Negate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("rules_text", "Counter target noncreature spell.")
        super().__init__(**kwargs)

    def can_cast(self, game: GameState) -> bool:
        """Cannot cast Negate unless a noncreature spell is on the stack."""
        for stack_obj in game.stack.objects():
            source = stack_obj.source
            if source is self:
                continue
            card_types = getattr(source, "card_types", set())
            if CardType.CREATURE not in card_types:
                return True
        return False

    def get_targets(self, game: GameState) -> list[Any]:
        """Target noncreature spell on the stack."""
        targets: list[Any] = []
        for stack_obj in game.stack.objects():
            source = stack_obj.source
            if source is self:
                continue
            card_types = getattr(source, "card_types", set())
            if CardType.CREATURE not in card_types:
                targets.append(stack_obj)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="target noncreature spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Counter the target spell — remove from stack, move to graveyard."""
        target = _get_chosen_target(self, game)
        if target is None:
            return
        _counter_spell(game, target)


class Cancel(Instant):
    """Cancel — {1}{U}{U} — Counter target spell."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cancel")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault("rules_text", "Counter target spell.")
        super().__init__(**kwargs)

    def can_cast(self, game: GameState) -> bool:
        """Cannot cast Cancel unless there is a spell on the stack to counter."""
        for stack_obj in game.stack.objects():
            if stack_obj.source is not self:
                return True
        return False

    def get_targets(self, game: GameState) -> list[Any]:
        """Target any spell on the stack."""
        targets: list[Any] = []
        for stack_obj in game.stack.objects():
            # Don't target self (Cancel can't counter itself).
            if stack_obj.source is not self:
                targets.append(stack_obj)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Counter the target spell — remove from stack, move to graveyard."""
        target = _get_chosen_target(self, game)
        if target is None:
            return
        _counter_spell(game, target)


def _counter_spell(game: GameState, stack_obj: Any) -> None:
    """Counter a spell — remove it from the stack and move the card to its owner's graveyard.

    Args:
        game: The current game state.
        stack_obj: The :class:`~engine.stack.StackObject` to counter.
    """
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return

    card = stack_obj.source

    # Remove the stack object from the stack.
    # The stack stores items internally; we need to find and remove it.
    stack_items = game.stack._items  # noqa: SLF001 — internal access needed
    found = False
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            found = True
            break

    # If the target was not on the stack, fizzle — do nothing.
    if not found:
        return

    # Move the card from the stack zone to the owner's graveyard.
    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)

    # Remove from the controller's stack zone.
    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)

    # Add to owner's graveyard.
    if owner is not None:
        graveyard = owner.zones[Zone.GRAVEYARD]
        graveyard.add(card)


# ---------------------------------------------------------------------------
# Utility spells
# ---------------------------------------------------------------------------

class Disenchant(Instant):
    """Disenchant — {1}{W} — Destroy target artifact or enchantment."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Disenchant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("rules_text", "Destroy target artifact or enchantment.")
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target artifact or enchantment on the battlefield."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                card_types = getattr(obj, "card_types", set())
                if CardType.ARTIFACT in card_types or CardType.ENCHANTMENT in card_types:
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="target artifact or enchantment",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Destroy the target artifact or enchantment."""
        from engine.game import destroy

        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Verify target is still on the battlefield and is an artifact/enchantment.
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                card_types = getattr(target, "card_types", set())
                if CardType.ARTIFACT in card_types or CardType.ENCHANTMENT in card_types:
                    destroy(game, target)
                    return


class Pilfer(Sorcery):
    """Pilfer — {1}{B} — Target opponent reveals hand; you choose a nonland card to discard."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pilfer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Target opponent reveals their hand. You choose a nonland card "
            "from it. That player discards that card.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target opponent."""
        controller = self.controller
        targets: list[Any] = [
            p for p in game.players if p is not controller
        ]
        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="target opponent",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Target opponent reveals hand; controller chooses a nonland card to discard."""
        from engine.game import discard

        target = _get_chosen_target(self, game)
        if target is None:
            return

        controller = self.controller
        if controller is None:
            return

        # Reveal hand and pick a nonland card.
        hand = game.get_hand(target)
        nonland_cards = [
            c for c in hand.get_all()
            if CardType.LAND not in getattr(c, "card_types", set())
        ]
        if not nonland_cards:
            return

        chosen = controller.choose_card(nonland_cards, "Choose a nonland card to discard")
        if chosen is not None:
            discard(game, target, chosen)


class CemeteryRecruitment(Sorcery):
    """Cemetery Recruitment — {1}{B} — Return target creature card from graveyard to hand.

    The Zombie bonus draw is not implemented.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cemetery Recruitment")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Return target creature card from your graveyard to your hand. "
            "If it's a Zombie card, draw a card.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: GameState) -> bool:
        """Cannot cast if no creature cards in controller's graveyard."""
        controller = self.controller
        if controller is None:
            return False
        graveyard = game.get_graveyard(controller)
        for obj in graveyard.get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                return True
        return False

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature card in your graveyard."""
        controller = self.controller
        if controller is None:
            return []

        targets: list[Any] = []
        graveyard = game.get_graveyard(controller)
        for obj in graveyard.get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                targets.append(obj)

        if not targets:
            return []

        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="target creature card in your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Return the target creature card from graveyard to hand."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        controller = self.controller
        if controller is None:
            return

        graveyard = game.get_graveyard(controller)
        hand = game.get_hand(controller)

        if graveyard.contains(target):
            graveyard.remove(target)
            hand.add(target)




# ---------------------------------------------------------------------------
# All spells list for registration — Scryfall-verified metadata
# ---------------------------------------------------------------------------

_ALL_SIMPLE_SPELLS: list[
    tuple[str, type, str, list[str], str, str, str, str]
] = [
    # (name, impl_class, mana_cost_str, colors, oracle_text,
    #  rarity, type_line, collector_number)
    #
    # --- Damage ---
    (
        "Burst Lightning", BurstLightning, "{R}",
        ["R"],
        "Kicker {4}\n"
        "Burst Lightning deals 2 damage to any target. "
        "If this spell was kicked, it deals 4 damage instead.",
        "common", "Instant", "192",
    ),
    (
        "Incinerating Blast", IncineratingBlast, "{4}{R}",
        ["R"],
        "Incinerating Blast deals 6 damage to target creature.\n"
        "You may discard a card. If you do, draw a card.",
        "common", "Sorcery", "90",
    ),
    # --- Buff ---
    (
        "Giant Growth", GiantGrowth, "{G}",
        ["G"],
        "Target creature gets +3/+3 until end of turn.",
        "common", "Instant", "223",
    ),
    # --- Draw ---
    (
        "Quick Study", QuickStudy, "{2}{U}",
        ["U"],
        "Draw two cards.",
        "common", "Instant", "513",
    ),
    # --- Removal ---
    (
        "Hero's Downfall", HerosDownfall, "{1}{B}{B}",
        ["B"],
        "Destroy target creature or planeswalker.",
        "uncommon", "Instant", "175",
    ),
    # --- Counter ---
    (
        "Negate", Negate, "{1}{U}",
        ["U"],
        "Counter target noncreature spell.",
        "common", "Instant", "710",
    ),
    (
        "Cancel", Cancel, "{1}{U}{U}",
        ["U"],
        "Counter target spell.",
        "common", "Instant", "505",
    ),
    # --- Utility ---
    (
        "Disenchant", Disenchant, "{1}{W}",
        ["W"],
        "Destroy target artifact or enchantment.",
        "common", "Instant", "572",
    ),
    (
        "Pilfer", Pilfer, "{1}{B}",
        ["B"],
        "Target opponent reveals their hand. You choose a nonland card "
        "from it. That player discards that card.",
        "common", "Sorcery", "181",
    ),
    (
        "Cemetery Recruitment", CemeteryRecruitment, "{1}{B}",
        ["B"],
        "Return target creature card from your graveyard to your hand. "
        "If it's a Zombie card, draw a card.",
        "common", "Sorcery", "517",
    ),
]


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_simple_spells(registry: CardRegistry) -> None:
    """Register all simple spells with *registry*.

    Each spell is registered under its canonical card name with
    :class:`~cards.registry.CardMetadata` reflecting its cost, type line,
    colors, and oracle text.  All metadata matches the actual FDN printing
    as sourced from Scryfall.
    """
    from cards.registry import CardMetadata

    for (
        card_name, impl_class, cost_str, colors, oracle_text,
        rarity, type_line, collector_number,
    ) in _ALL_SIMPLE_SPELLS:
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
