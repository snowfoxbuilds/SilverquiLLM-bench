"""Batch 3 — Simple targeted instants & sorceries from Foundations (FDN).

Implements ~15 targeted FDN instants and sorceries: burn (deal N damage
to target), targeted removal (destroy target creature/permanent), bounce
(return target to hand), pump (+N/+N until end of turn), and fight
spells.

Each spell subclasses :class:`~engine.card.Instant` or
:class:`~engine.card.Sorcery` and overrides :meth:`get_targets` (return
a :class:`TargetRequirement`) and :meth:`on_resolve` (use
:func:`_get_chosen_target`).

All cards are real FDN set cards verified against Scryfall data.

Use :func:`register_simple_spells_batch3` to register all spells with a
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
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

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
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _get_chosen_target_idx(card: Any, game: Any, idx: int) -> Any:
    """Retrieve the *idx*-th chosen target for a spell (0-indexed)."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen and len(chosen) > idx:
        return chosen[idx]
    # Fall back to list-based test backdoor
    targets = getattr(card, "_resolve_targets", None)
    if targets and len(targets) > idx:
        return targets[idx]
    if idx == 0:
        return getattr(card, "_resolve_target", None)
    return None


# ---------------------------------------------------------------------------
# Burn spells
# ---------------------------------------------------------------------------


class JoustThrough(Instant):
    """Joust Through — {W} — Deal 3 damage to target attacking or blocking
    creature.  You gain 1 life.

    FDN collector number 19.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Joust Through")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Joust Through deals 3 damage to target attacking or blocking "
            "creature. You gain 1 life.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature on the battlefield.

        In a full implementation this would be restricted to attacking or
        blocking creatures, but we allow any creature for simplicity.
        """
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target attacking or blocking creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Deal 3 damage to the target creature; gain 1 life."""
        from engine.game import deal_damage

        target = _get_chosen_target(self, game)
        if target is None:
            return
        # Verify target is still legal; if not, spell fizzles entirely
        target_valid = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    target_valid = True
                    break
        if not target_valid:
            return
        deal_damage(game, self, target, 3)
        controller = self.controller
        if controller is not None and hasattr(controller, "life"):
            controller.life += 1


# ---------------------------------------------------------------------------
# Targeted removal spells
# ---------------------------------------------------------------------------


class LuminousRebuke(Instant):
    """Luminous Rebuke — {4}{W} — Destroy target creature.

    This spell costs {3} less to cast if it targets a tapped creature.
    (Cost reduction not implemented.)

    FDN collector number 20.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Luminous Rebuke")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{W}"))
        kwargs.setdefault(
            "rules_text",
            "This spell costs {3} less to cast if it targets a tapped "
            "creature.\nDestroy target creature.",
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
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Destroy the target creature."""
        from engine.game import destroy

        target = _get_chosen_target(self, game)
        if target is None:
            return
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    destroy(game, target)
                    return


class MakeYourMove(Instant):
    """Make Your Move — {2}{W} — Destroy target artifact, enchantment,
    or creature with power 4 or greater.

    FDN collector number 143.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Make Your Move")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Destroy target artifact, enchantment, or creature with "
            "power 4 or greater.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target artifact, enchantment, or creature with power >= 4."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                card_types = getattr(obj, "card_types", set())
                if CardType.ARTIFACT in card_types or CardType.ENCHANTMENT in card_types:
                    targets.append(obj)
                elif CardType.CREATURE in card_types:
                    power = getattr(obj, "power", getattr(obj, "base_power", 0))
                    if power >= 4:
                        targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    bool(getattr(obj, "card_types", set()) & {CardType.ARTIFACT, CardType.ENCHANTMENT})
                    or (CardType.CREATURE in getattr(obj, "card_types", set())
                        and getattr(obj, "power", getattr(obj, "base_power", 0)) >= 4)),
                description="target artifact, enchantment, or creature with power 4 or greater",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Destroy the target."""
        from engine.game import destroy

        target = _get_chosen_target(self, game)
        if target is None:
            return
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                destroy(game, target)
                return


class StrokeOfMidnight(Instant):
    """Stroke of Midnight — {2}{W} — Destroy target nonland permanent.
    Its controller creates a 1/1 white Human creature token.

    FDN collector number 148.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Stroke of Midnight")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Destroy target nonland permanent. Its controller creates a "
            "1/1 white Human creature token.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target nonland permanent on the battlefield."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                card_types = getattr(obj, "card_types", set())
                if CardType.LAND not in card_types:
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.LAND not in getattr(obj, "card_types", set()),
                description="target nonland permanent",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Destroy the target; its controller gets a 1/1 Human token."""
        from engine.game import destroy

        target = _get_chosen_target(self, game)
        if target is None:
            return

        target_controller = getattr(target, "controller", None)
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                card_types = getattr(target, "card_types", set())
                if CardType.LAND not in card_types:
                    destroy(game, target)
                    # Create a 1/1 white Human token for the controller
                    if target_controller is not None:
                        _create_human_token(game, target_controller)
                    return


def _create_human_token(game: GameState, player: Any) -> Any:
    """Create a 1/1 white Human creature token on *player*'s battlefield."""
    from engine.card import Creature
    from engine.game import create_token

    token = Creature(
        name="Human Token",
        mana_cost=ManaCost(),
        rules_text="",
    )
    token.base_power = 1
    token.base_toughness = 1
    token.card_types = {CardType.CREATURE}
    create_token(game, player, token)
    return token


class BakeIntoAPie(Instant):
    """Bake into a Pie — {2}{B}{B} — Destroy target creature.
    Create a Food token.

    FDN collector number 169.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bake into a Pie")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            'Destroy target creature. Create a Food token. (It\'s an '
            'artifact with "{2}, {T}, Sacrifice this token: You gain '
            '3 life.")',
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
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Destroy the target creature; create a Food token."""
        from engine.game import destroy

        target = _get_chosen_target(self, game)
        if target is None:
            return
        # Verify target is still legal; if not, spell fizzles entirely
        target_valid = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    target_valid = True
                    break
        if not target_valid:
            return
        destroy(game, target)
        # Create a Food token for the controller
        controller = self.controller
        if controller is not None:
            _create_food_token(game, controller)


def _create_food_token(game: GameState, player: Any) -> Any:
    """Create a Food artifact token on *player*'s battlefield."""
    from engine.card import Artifact
    from engine.game import create_token

    token = Artifact(
        name="Food Token",
        mana_cost=ManaCost(),
        rules_text='{2}, {T}, Sacrifice this token: You gain 3 life.',
    )
    token.card_types = {CardType.ARTIFACT}
    create_token(game, player, token)
    return token


class EatenAlive(Sorcery):
    """Eaten Alive — {B} — Exile target creature or planeswalker.

    As an additional cost, sacrifice a creature or pay {3}{B}.
    (Additional cost not implemented; only the exile effect.)

    FDN collector number 172.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Eaten Alive")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        kwargs.setdefault(
            "rules_text",
            "As an additional cost to cast this spell, sacrifice a "
            "creature or pay {3}{B}.\nExile target creature or "
            "planeswalker.",
        )
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
                filter_fn=lambda obj: bool(getattr(obj, "card_types", set()) & {CardType.CREATURE, CardType.PLANESWALKER}),
                description="target creature or planeswalker",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Exile the target creature or planeswalker."""
        from engine.game import exile

        target = _get_chosen_target(self, game)
        if target is None:
            return
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                card_types = getattr(target, "card_types", set())
                if CardType.CREATURE in card_types or CardType.PLANESWALKER in card_types:
                    exile(game, target)
                    return


class BrokenWings(Instant):
    """Broken Wings — {2}{G} — Destroy target artifact, enchantment,
    or creature with flying.

    FDN collector number 214.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Broken Wings")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Destroy target artifact, enchantment, or creature with flying.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target artifact, enchantment, or creature with flying."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                card_types = getattr(obj, "card_types", set())
                if CardType.ARTIFACT in card_types or CardType.ENCHANTMENT in card_types:
                    targets.append(obj)
                elif CardType.CREATURE in card_types:
                    kw = getattr(obj, "keywords", Keyword(0))
                    if Keyword.FLYING in kw:
                        targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    bool(getattr(obj, "card_types", set()) & {CardType.ARTIFACT, CardType.ENCHANTMENT})
                    or (CardType.CREATURE in getattr(obj, "card_types", set())
                        and Keyword.FLYING in getattr(obj, "keywords", Keyword(0)))),
                description="target artifact, enchantment, or creature with flying",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Destroy the target."""
        from engine.game import destroy

        target = _get_chosen_target(self, game)
        if target is None:
            return
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                destroy(game, target)
                return


class EssenceScatter(Instant):
    """Essence Scatter — {1}{U} — Counter target creature spell.

    FDN collector number 153.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Essence Scatter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("rules_text", "Counter target creature spell.")
        super().__init__(**kwargs)

    def can_cast(self, game: GameState) -> bool:
        """Cannot cast unless a creature spell is on the stack."""
        for stack_obj in game.stack.objects():
            source = stack_obj.source
            if source is self:
                continue
            card_types = getattr(source, "card_types", set())
            if CardType.CREATURE in card_types:
                return True
        return False

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature spell on the stack."""
        targets: list[Any] = []
        for stack_obj in game.stack.objects():
            source = stack_obj.source
            if source is self:
                continue
            card_types = getattr(source, "card_types", set())
            if CardType.CREATURE in card_types:
                targets.append(stack_obj)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(getattr(obj, "source", obj), "card_types", set()),
                description="target creature spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Counter the target creature spell."""
        target = _get_chosen_target(self, game)
        if target is None:
            return
        _counter_spell(game, target)


# ---------------------------------------------------------------------------
# Bounce spells
# ---------------------------------------------------------------------------


class RunAwayTogether(Instant):
    """Run Away Together — {1}{U} — Choose two target creatures controlled
    by different players. Return those creatures to their owners' hands.

    FDN collector number 162.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Run Away Together")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Choose two target creatures controlled by different players. "
            "Return those creatures to their owners' hands.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creatures controlled by different players."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        # Each requirement accepts any creature; the "different controllers"
        # constraint is validated at target-selection time (not per-filter).
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature (first — must differ in controller from second)",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature (second — must differ in controller from first)",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Return both target creatures to their owners' hands."""
        from engine.zones import move_to_zone

        target1 = _get_chosen_target_idx(self, game, 0)
        target2 = _get_chosen_target_idx(self, game, 1)

        # Fizzle if targets don't have different controllers
        if target1 is not None and target2 is not None:
            ctrl1 = getattr(target1, "controller", None)
            ctrl2 = getattr(target2, "controller", None)
            if ctrl1 is ctrl2:
                return  # illegal — must be different controllers

        for target in [target1, target2]:
            if target is None:
                continue
            for player in game.players:
                if game.get_battlefield(player).contains(target):
                    move_to_zone(game, target, Zone.BATTLEFIELD, Zone.HAND)
                    break


# ---------------------------------------------------------------------------
# Pump spells
# ---------------------------------------------------------------------------


class SureStrike(Instant):
    """Sure Strike — {1}{R} — Target creature gets +3/+0 and gains
    first strike until end of turn.

    FDN collector number 209.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sure Strike")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Target creature gets +3/+0 and gains first strike until "
            "end of turn.",
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
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Apply +3/+0 and first strike until end of turn."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        still_valid = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    still_valid = True
                    break
        if not still_valid:
            return

        creature_ref = target

        def _apply_buff(game: GameState) -> None:
            for p in game.players:
                if game.get_battlefield(p).contains(creature_ref):
                    creature_ref.base_power += 3
                    creature_ref.keywords = getattr(
                        creature_ref, "keywords", Keyword(0)
                    ) | Keyword.FIRST_STRIKE
                    return

        effect = ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_buff,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)


class SnakeskinVeil(Instant):
    """Snakeskin Veil — {G} — Put a +1/+1 counter on target creature you
    control. It gains hexproof until end of turn.

    FDN collector number 233.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Snakeskin Veil")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        kwargs.setdefault(
            "rules_text",
            "Put a +1/+1 counter on target creature you control. It "
            "gains hexproof until end of turn.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature you control."""
        controller = self.controller
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    if getattr(obj, "controller", None) is controller:
                        targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "controller", None) is _c
                ),
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Put a +1/+1 counter on the target; grant hexproof until EOT."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        still_valid = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    still_valid = True
                    break
        if not still_valid:
            return

        # +1/+1 counter via plus_one_counters (not base_power mutation)
        if hasattr(target, "plus_one_counters"):
            target.plus_one_counters += 1
            target._original_plus_one_counters = target.plus_one_counters  # type: ignore[attr-defined]

        creature_ref = target

        def _apply_hexproof(game: GameState) -> None:
            for p in game.players:
                if game.get_battlefield(p).contains(creature_ref):
                    creature_ref.keywords = getattr(
                        creature_ref, "keywords", Keyword(0)
                    ) | Keyword.HEXPROOF
                    return

        effect = ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_hexproof,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)


class FleetingDistraction(Instant):
    """Fleeting Distraction — {U} — Target creature gets -1/-0 until end
    of turn. Draw a card.

    FDN collector number 155.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fleeting Distraction")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault(
            "rules_text",
            "Target creature gets -1/-0 until end of turn.\nDraw a card.",
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
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Give target creature -1/-0 until EOT; draw a card."""
        from engine.game import draw_card

        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Verify target is still legal; if not, spell fizzles entirely
        still_valid = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    still_valid = True
                    break
        if not still_valid:
            return

        creature_ref = target

        def _apply_debuff(game: GameState) -> None:
            for p in game.players:
                if game.get_battlefield(p).contains(creature_ref):
                    creature_ref.base_power -= 1
                    return

        effect = ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_debuff,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)

        # Draw a card as part of the spell's effect
        controller = self.controller
        if controller is not None:
            draw_card(game, controller)


class DivineResilience(Instant):
    """Divine Resilience — {W} — Target creature you control gains
    indestructible until end of turn.

    Kicker {2}{W} not implemented.

    FDN collector number 10.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Divine Resilience")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Kicker {2}{W}\nTarget creature you control gains "
            "indestructible until end of turn. If this spell was kicked, "
            "also put two +1/+1 counters on it.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature you control."""
        controller = self.controller
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    if getattr(obj, "controller", None) is controller:
                        targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "controller", None) is _c
                ),
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Grant indestructible until end of turn."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        still_valid = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    still_valid = True
                    break
        if not still_valid:
            return

        creature_ref = target

        def _apply_indestructible(game: GameState) -> None:
            for p in game.players:
                if game.get_battlefield(p).contains(creature_ref):
                    creature_ref.keywords = getattr(
                        creature_ref, "keywords", Keyword(0)
                    ) | Keyword.INDESTRUCTIBLE
                    return

        effect = ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_indestructible,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)


# ---------------------------------------------------------------------------
# Fight spells
# ---------------------------------------------------------------------------


class BiteDown(Instant):
    """Bite Down — {1}{G} — Target creature you control deals damage
    equal to its power to target creature or planeswalker you don't
    control.

    FDN collector number 212.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bite Down")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Target creature you control deals damage equal to its power "
            "to target creature or planeswalker you don't control.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Two targets: a creature you control and a creature/PW an
        opponent controls.
        """
        controller = self.controller
        my_targets: list[Any] = []
        opp_targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                card_types = getattr(obj, "card_types", set())
                obj_ctrl = getattr(obj, "controller", None)
                if obj_ctrl is controller:
                    if CardType.CREATURE in card_types:
                        my_targets.append(obj)
                else:
                    if CardType.CREATURE in card_types or CardType.PLANESWALKER in card_types:
                        opp_targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "controller", None) is _c
                ),
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: (
                    bool(getattr(obj, "card_types", set()) & {CardType.CREATURE, CardType.PLANESWALKER})
                    and getattr(obj, "controller", None) is not _c
                ),
                description="target creature or planeswalker you don't control",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Your creature deals damage equal to its power to the second target."""
        from engine.game import deal_damage

        source_creature = _get_chosen_target_idx(self, game, 0)
        fight_target = _get_chosen_target_idx(self, game, 1)

        if source_creature is None or fight_target is None:
            return

        # Verify both are still on the battlefield
        source_valid = False
        target_valid = False
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(source_creature):
                source_valid = True
            if bf.contains(fight_target):
                target_valid = True

        if source_valid and target_valid:
            power = getattr(source_creature, "power", getattr(source_creature, "base_power", 0))
            if power > 0:
                deal_damage(game, source_creature, fight_target, power)


class FellingBlow(Sorcery):
    """Felling Blow — {2}{G} — Put a +1/+1 counter on target creature
    you control. Then that creature deals damage equal to its power to
    target creature an opponent controls.

    FDN collector number 105.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Felling Blow")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Put a +1/+1 counter on target creature you control. Then "
            "that creature deals damage equal to its power to target "
            "creature an opponent controls.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Two targets: your creature and opponent's creature."""
        controller = self.controller
        my_targets: list[Any] = []
        opp_targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    obj_ctrl = getattr(obj, "controller", None)
                    if obj_ctrl is controller:
                        my_targets.append(obj)
                    else:
                        opp_targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "controller", None) is _c
                ),
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "controller", None) is not _c
                ),
                description="target creature an opponent controls",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Put +1/+1 counter, then one-way fight."""
        from engine.game import deal_damage

        source_creature = _get_chosen_target_idx(self, game, 0)
        fight_target = _get_chosen_target_idx(self, game, 1)

        if source_creature is None or fight_target is None:
            return

        # Verify both are still on the battlefield
        source_valid = False
        target_valid = False
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(source_creature):
                source_valid = True
            if bf.contains(fight_target):
                target_valid = True

        if not source_valid:
            return

        # +1/+1 counter via plus_one_counters (not base_power mutation)
        if hasattr(source_creature, "plus_one_counters"):
            source_creature.plus_one_counters += 1
            source_creature._original_plus_one_counters = source_creature.plus_one_counters  # type: ignore[attr-defined]

        if target_valid:
            power = getattr(source_creature, "power", getattr(source_creature, "base_power", 0))
            if power > 0:
                deal_damage(game, source_creature, fight_target, power)


# ---------------------------------------------------------------------------
# Additional targeted spells
# ---------------------------------------------------------------------------


class FleetingFlight(Instant):
    """Fleeting Flight — {W} — Put a +1/+1 counter on target creature.
    It gains flying until end of turn. Prevent all combat damage that
    would be dealt to it this turn.

    (Prevention shield not fully implemented.)

    FDN collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fleeting Flight")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Put a +1/+1 counter on target creature. It gains flying "
            "until end of turn. Prevent all combat damage that would be "
            "dealt to it this turn.",
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
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Put +1/+1 counter; grant flying until EOT."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        still_valid = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    still_valid = True
                    break
        if not still_valid:
            return

        # +1/+1 counter via plus_one_counters (not base_power mutation)
        if hasattr(target, "plus_one_counters"):
            target.plus_one_counters += 1
            target._original_plus_one_counters = target.plus_one_counters  # type: ignore[attr-defined]

        creature_ref = target

        def _apply_flying(game: GameState) -> None:
            for p in game.players:
                if game.get_battlefield(p).contains(creature_ref):
                    creature_ref.keywords = getattr(
                        creature_ref, "keywords", Keyword(0)
                    ) | Keyword.FLYING
                    return

        effect = ContinuousEffect(
            source=self,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply_flying,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)


class FakeYourOwnDeath(Instant):
    """Fake Your Own Death — {1}{B} — Until end of turn, target creature
    gets +2/+0 and gains "When this creature dies, return it to the
    battlefield tapped under its owner's control."

    (Death trigger not fully implemented — only the +2/+0 buff.)

    FDN collector number 174.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fake Your Own Death")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault(
            "rules_text",
            'Until end of turn, target creature gets +2/+0 and gains '
            '"When this creature dies, return it to the battlefield '
            "tapped under its owner's control.\"",
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
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Apply +2/+0 until end of turn."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        still_valid = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    still_valid = True
                    break
        if not still_valid:
            return

        creature_ref = target

        def _apply_buff(game: GameState) -> None:
            for p in game.players:
                if game.get_battlefield(p).contains(creature_ref):
                    creature_ref.base_power += 2
                    return

        effect = ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_buff,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)


class Zombify(Sorcery):
    """Zombify — {3}{B} — Return target creature card from your graveyard
    to the battlefield.

    FDN collector number 187.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zombify")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Return target creature card from your graveyard to the "
            "battlefield.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature card in your graveyard."""
        controller = self.controller
        targets: list[Any] = []
        if controller is not None:
            for obj in controller.zones[Zone.GRAVEYARD].get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "owner", None) is _c
                ),
                description="target creature card in your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ] if targets else []

    def on_resolve(self, game: GameState) -> None:
        """Return the target creature card from graveyard to battlefield."""
        from engine.zones import move_to_zone

        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Verify target is still in a graveyard
        for player in game.players:
            gy = player.zones[Zone.GRAVEYARD]
            if gy.contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)
                    return


# ---------------------------------------------------------------------------
# Counter-spell helper (shared with simple_spells.py pattern)
# ---------------------------------------------------------------------------

def _counter_spell(game: GameState, stack_obj: Any) -> None:
    """Counter a spell — remove it from the stack and move the card to
    its owner's graveyard.
    """
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return

    card = stack_obj.source

    # Check if the stack object is actually on the stack; if not, fizzle.
    stack_items = game.stack._items  # noqa: SLF001
    found = False
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            found = True
            break

    if not found:
        return

    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)

    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)

    if owner is not None:
        graveyard = owner.zones[Zone.GRAVEYARD]
        graveyard.add(card)


# ---------------------------------------------------------------------------
# Card data table
# ---------------------------------------------------------------------------

_ALL_BATCH3_SPELLS: list[tuple[str, type, str, list[str], str, str, str, str]] = [
    # --- Burn ---
    (
        "Joust Through", JoustThrough, "{W}",
        ["W"],
        "Joust Through deals 3 damage to target attacking or blocking "
        "creature. You gain 1 life.",
        "common", "Instant", "19",
    ),
    # --- Targeted removal ---
    (
        "Luminous Rebuke", LuminousRebuke, "{4}{W}",
        ["W"],
        "This spell costs {3} less to cast if it targets a tapped "
        "creature.\nDestroy target creature.",
        "common", "Instant", "20",
    ),
    (
        "Make Your Move", MakeYourMove, "{2}{W}",
        ["W"],
        "Destroy target artifact, enchantment, or creature with power "
        "4 or greater.",
        "uncommon", "Instant", "143",
    ),
    (
        "Stroke of Midnight", StrokeOfMidnight, "{2}{W}",
        ["W"],
        "Destroy target nonland permanent. Its controller creates a "
        "1/1 white Human creature token.",
        "uncommon", "Instant", "148",
    ),
    (
        "Bake into a Pie", BakeIntoAPie, "{2}{B}{B}",
        ["B"],
        'Destroy target creature. Create a Food token. (It\'s an '
        'artifact with "{2}, {T}, Sacrifice this token: You gain '
        '3 life.")',
        "common", "Instant", "169",
    ),
    (
        "Eaten Alive", EatenAlive, "{B}",
        ["B"],
        "As an additional cost to cast this spell, sacrifice a "
        "creature or pay {3}{B}.\nExile target creature or "
        "planeswalker.",
        "common", "Sorcery", "172",
    ),
    (
        "Broken Wings", BrokenWings, "{2}{G}",
        ["G"],
        "Destroy target artifact, enchantment, or creature with flying.",
        "common", "Instant", "214",
    ),
    # --- Counter ---
    (
        "Essence Scatter", EssenceScatter, "{1}{U}",
        ["U"],
        "Counter target creature spell.",
        "common", "Instant", "153",
    ),
    # --- Bounce ---
    (
        "Run Away Together", RunAwayTogether, "{1}{U}",
        ["U"],
        "Choose two target creatures controlled by different players. "
        "Return those creatures to their owners' hands.",
        "common", "Instant", "162",
    ),
    # --- Pump ---
    (
        "Sure Strike", SureStrike, "{1}{R}",
        ["R"],
        "Target creature gets +3/+0 and gains first strike until end "
        "of turn.",
        "common", "Instant", "209",
    ),
    (
        "Snakeskin Veil", SnakeskinVeil, "{G}",
        ["G"],
        "Put a +1/+1 counter on target creature you control. It gains "
        "hexproof until end of turn.",
        "common", "Instant", "233",
    ),
    (
        "Fleeting Distraction", FleetingDistraction, "{U}",
        ["U"],
        "Target creature gets -1/-0 until end of turn.\nDraw a card.",
        "common", "Instant", "155",
    ),
    (
        "Divine Resilience", DivineResilience, "{W}",
        ["W"],
        "Kicker {2}{W}\nTarget creature you control gains indestructible "
        "until end of turn. If this spell was kicked, also put two +1/+1 "
        "counters on it.",
        "uncommon", "Instant", "10",
    ),
    (
        "Fleeting Flight", FleetingFlight, "{W}",
        ["W"],
        "Put a +1/+1 counter on target creature. It gains flying until "
        "end of turn. Prevent all combat damage that would be dealt to "
        "it this turn.",
        "common", "Instant", "13",
    ),
    (
        "Fake Your Own Death", FakeYourOwnDeath, "{1}{B}",
        ["B"],
        'Until end of turn, target creature gets +2/+0 and gains '
        '"When this creature dies, return it to the battlefield '
        "tapped under its owner's control.\"",
        "common", "Instant", "174",
    ),
    # --- Fight ---
    (
        "Bite Down", BiteDown, "{1}{G}",
        ["G"],
        "Target creature you control deals damage equal to its power "
        "to target creature or planeswalker you don't control.",
        "common", "Instant", "212",
    ),
    (
        "Felling Blow", FellingBlow, "{2}{G}",
        ["G"],
        "Put a +1/+1 counter on target creature you control. Then "
        "that creature deals damage equal to its power to target "
        "creature an opponent controls.",
        "uncommon", "Sorcery", "105",
    ),
    # --- Reanimation ---
    (
        "Zombify", Zombify, "{3}{B}",
        ["B"],
        "Return target creature card from your graveyard to the "
        "battlefield.",
        "uncommon", "Sorcery", "187",
    ),
]


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_simple_spells_batch3(registry: CardRegistry) -> None:
    """Register all batch 3 targeted spells with *registry*.

    Each spell is registered under its canonical card name with
    :class:`~cards.registry.CardMetadata` reflecting its cost, type line,
    colors, and oracle text.  All metadata matches the actual FDN printing
    as sourced from Scryfall.
    """
    from cards.registry import CardMetadata

    for (
        card_name, impl_class, cost_str, colors, oracle_text,
        rarity, type_line, collector_number,
    ) in _ALL_BATCH3_SPELLS:
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
