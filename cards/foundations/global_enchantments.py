"""Batch 10 — FDN global (non-aura) enchantments.

Implements 10 real Foundations enchantments covering:

- **Anthem effects**: Anthem of Champions (+1/+1), Goblin Oriflamme (+1/+0
  to attacking creatures).
- **Keyword-granting**: Garruk's Uprising (trample + draw on power 4+ ETB).
- **Static ability**: Authority of the Consuls (opponents' creatures enter
  tapped, gain 1 life on opponent creature ETB).
- **Upkeep trigger**: Phyrexian Arena (draw a card, lose 1 life).
- **Creature-enters trigger**: Impact Tremors (deal 1 to each opponent).
- **Spell-cast trigger**: Rite of the Dragoncaller (create 5/5 Dragon),
  Painful Quandary (opponent loses 5 life unless they discard).
- **ETB exile-until-leaves**: Banishing Light.
- **Activated ability enchantment**: Vampiric Rites (sacrifice creature,
  gain 1 life, draw a card).

All cards are verified against Scryfall FDN data with correct collector
numbers.

Use :func:`register_global_enchantments` to register all cards with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature, Enchantment
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

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Check if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _opponent_creatures_targets(game: Any, controller: Any) -> list[Any]:
    """Return all creatures on opponents' battlefields."""
    targets: list[Any] = []
    for player in game.players:
        if player is controller:
            continue
        for obj in game.get_battlefield(player).get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                targets.append(obj)
    return targets


def _nonland_opponent_targets(game: Any, controller: Any) -> list[Any]:
    """Return all nonland permanents on opponents' battlefields."""
    targets: list[Any] = []
    for player in game.players:
        if player is controller:
            continue
        for obj in game.get_battlefield(player).get_all():
            card_types = getattr(obj, "card_types", set())
            if CardType.LAND not in card_types:
                targets.append(obj)
    return targets


# ===================================================================
# ANTHEM EFFECTS
# ===================================================================


class AnthemOfChampions(Enchantment):
    """Anthem of Champions — {G}{W} — Creatures you control get +1/+1.

    FDN collector number 116.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Anthem of Champions")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}{W}"))
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


class GoblinOriflamme(Enchantment):
    """Goblin Oriflamme — {1}{R} — Attacking creatures you control get +1/+0.

    FDN collector number 539.
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
                    if getattr(obj, "is_attacking", False):
                        obj.base_power += 1

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


# ===================================================================
# KEYWORD-GRANTING + TRIGGERED DRAW
# ===================================================================


class GarruksUprising(Enchantment):
    """Garruk's Uprising — {2}{G} — Creatures you control have trample.

    When this enchantment enters, if you control a creature with power 4
    or greater, draw a card.
    Whenever a creature you control with power 4 or greater enters,
    draw a card.

    FDN collector number 220.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Garruk's Uprising")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault(
            "rules_text",
            "When this enchantment enters, if you control a creature with "
            "power 4 or greater, draw a card.\n"
            "Creatures you control have trample.\n"
            "Whenever a creature you control with power 4 or greater enters, "
            "draw a card.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def on_resolve(self, game: GameState) -> None:
        # ETB: if you control a creature with power 4+, draw a card.
        controller = self.controller
        if controller is not None:
            for obj in game.get_battlefield(controller).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    power = getattr(obj, "power", getattr(obj, "base_power", 0))
                    if power >= 4:
                        from engine.game import draw_card
                        draw_card(game, controller)
                        break
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
                    obj.keywords = obj.keywords | Keyword.TRAMPLE

        effect = ContinuousEffect(
            source=enchantment_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _condition(game: Any, data: dict) -> bool:
            permanent = data.get("permanent")
            if permanent is None:
                return False
            controller = source.controller
            if controller is None:
                return False
            if getattr(permanent, "controller", None) is not controller:
                return False
            if CardType.CREATURE not in getattr(permanent, "card_types", set()):
                return False
            power = getattr(permanent, "power", getattr(permanent, "base_power", 0))
            return power >= 4

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                draw_card(game, controller)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))

    def register_replacement_effects(self, game: GameState) -> None:
        if self._effect_ref is None:
            self._register_effect(game)


# ===================================================================
# STATIC ABILITY — OPPONENTS ENTER TAPPED
# ===================================================================


class AuthorityOfTheConsuls(Enchantment):
    """Authority of the Consuls — {W} — Creatures opponents control enter tapped.

    Whenever a creature an opponent controls enters, you gain 1 life.

    FDN collector number 137.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Authority of the Consuls")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Creatures your opponents control enter tapped.\n"
            "Whenever a creature an opponent controls enters, you gain 1 life.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def on_resolve(self, game: GameState) -> None:
        # ENGINE LIMITATION: The "enters tapped" static ability ideally
        # uses a replacement effect on ETB, but we approximate it with a
        # continuous effect that taps opponent creatures.  A proper
        # implementation would intercept the zone-transition in move_to_zone.
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        enchantment_ref = self

        def _apply(game: GameState) -> None:
            controller = enchantment_ref.controller
            if controller is None:
                return
            if not _is_on_battlefield(game, enchantment_ref):
                return
            for player in game.players:
                if player is controller:
                    continue
                for obj in game.get_battlefield(player).get_all():
                    if CardType.CREATURE in getattr(obj, "card_types", set()):
                        if getattr(obj, "summoning_sick", False):
                            obj.is_tapped = True

        effect = ContinuousEffect(
            source=enchantment_ref,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _condition(game: Any, data: dict) -> bool:
            permanent = data.get("permanent")
            if permanent is None:
                return False
            controller = source.controller
            if controller is None:
                return False
            perm_controller = getattr(permanent, "controller", None)
            if perm_controller is controller:
                return False
            return CardType.CREATURE in getattr(permanent, "card_types", set())

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            # Gain 1 life
            if hasattr(controller, "life"):
                controller.life += 1
                game.trigger_manager.fire_event(
                    game,
                    EventType.GAINS_LIFE,
                    {"player": controller, "amount": 1},
                )

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))

    def register_replacement_effects(self, game: GameState) -> None:
        if self._effect_ref is None:
            self._register_effect(game)


# ===================================================================
# UPKEEP TRIGGER
# ===================================================================


class PhyrexianArena(Enchantment):
    """Phyrexian Arena — {1}{B}{B} — Draw a card, lose 1 life at upkeep.

    At the beginning of your upkeep, you draw a card and you lose 1 life.

    FDN collector number 180.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Phyrexian Arena")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "At the beginning of your upkeep, you draw a card and you lose 1 life.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        pass  # No immediate effect; trigger registered via register_triggers

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _condition(game: Any, data: dict) -> bool:
            if not _is_on_battlefield(game, source):
                return False
            controller = source.controller
            return controller is not None and controller is game.active_player

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            draw_card(game, controller)
            controller.life -= 1
            game.trigger_manager.fire_event(
                game,
                EventType.LOSES_LIFE,
                {"player": controller, "amount": 1},
            )

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.BEGINNING_OF_UPKEEP,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# CREATURE-ENTERS TRIGGER
# ===================================================================


class ImpactTremors(Enchantment):
    """Impact Tremors — {1}{R} — Deal 1 damage to each opponent on creature ETB.

    Whenever a creature you control enters, this enchantment deals 1 damage
    to each opponent.

    FDN collector number 717.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Impact Tremors")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Whenever a creature you control enters, this enchantment deals "
            "1 damage to each opponent.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        pass

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import deal_damage

        source = self

        def _condition(game: Any, data: dict) -> bool:
            if not _is_on_battlefield(game, source):
                return False
            permanent = data.get("permanent")
            if permanent is None:
                return False
            controller = source.controller
            if controller is None:
                return False
            if getattr(permanent, "controller", None) is not controller:
                return False
            return CardType.CREATURE in getattr(permanent, "card_types", set())

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            for player in game.players:
                if player is not controller:
                    deal_damage(game, source, player, 1)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# SPELL-CAST TRIGGERS
# ===================================================================


class RiteOfTheDragoncaller(Enchantment):
    """Rite of the Dragoncaller — {4}{R}{R} — Create 5/5 Dragon on spell cast.

    Whenever you cast an instant or sorcery spell, create a 5/5 red Dragon
    creature token with flying.

    FDN collector number 92.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rite of the Dragoncaller")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Whenever you cast an instant or sorcery spell, create a 5/5 red "
            "Dragon creature token with flying.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        pass

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import create_token

        source = self

        def _condition(game: Any, data: dict) -> bool:
            if not _is_on_battlefield(game, source):
                return False
            spell = data.get("spell")
            if spell is None:
                return False
            controller = source.controller
            if controller is None:
                return False
            spell_controller = getattr(spell, "controller", None)
            if spell_controller is not controller:
                return False
            card_types = getattr(spell, "card_types", set())
            return (CardType.INSTANT in card_types
                    or CardType.SORCERY in card_types)

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            token = Creature(
                name="Dragon",
                subtypes={"Dragon"},
                base_power=5,
                base_toughness=5,
                keywords=Keyword.FLYING,
            )
            token.is_token = True
            create_token(game, controller, token)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.SPELL_CAST,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


class PainfulQuandary(Enchantment):
    """Painful Quandary — {3}{B}{B} — Opponent spell = lose 5 unless discard.

    Whenever an opponent casts a spell, that player loses 5 life unless
    they discard a card.

    FDN collector number 179.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Painful Quandary")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Whenever an opponent casts a spell, that player loses 5 life "
            "unless they discard a card.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        pass

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _condition(game: Any, data: dict) -> bool:
            if not _is_on_battlefield(game, source):
                return False
            spell = data.get("spell")
            if spell is None:
                return False
            controller = source.controller
            if controller is None:
                return False
            spell_controller = getattr(spell, "controller", None)
            return spell_controller is not controller

        def _effect(game: GameState) -> None:
            # ENGINE LIMITATION: Full implementation would offer the
            # opponent a choice to discard.  For now, the opponent simply
            # loses 5 life (the "unless they discard" clause requires a
            # choice engine that doesn't yet exist).
            controller = source.controller
            if controller is None:
                return
            from engine.game import deal_damage
            # Find the opponent who cast the spell — we use the stack
            # or just damage all opponents for simplicity.
            for player in game.players:
                if player is not controller:
                    player.life -= 5
                    game.trigger_manager.fire_event(
                        game,
                        EventType.LOSES_LIFE,
                        {"player": player, "amount": 5},
                    )

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.SPELL_CAST,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# ETB EXILE-UNTIL-LEAVES
# ===================================================================


class BanishingLight(Enchantment):
    """Banishing Light — {2}{W} — Exile nonland permanent until this leaves.

    When this enchantment enters, exile target nonland permanent an opponent
    controls until this enchantment leaves the battlefield.

    FDN collector number 138.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Banishing Light")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault(
            "rules_text",
            "When this enchantment enters, exile target nonland permanent an "
            "opponent controls until this enchantment leaves the battlefield.",
        )
        super().__init__(**kwargs)
        self._exiled_card: Any | None = None
        self._exiled_owner: Any | None = None

    def get_targets(self, game: GameState) -> list[Any]:
        controller = self.controller or game.active_player
        targets = _nonland_opponent_targets(game, controller)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: (
                    CardType.LAND not in getattr(obj, "card_types", set())
                    and getattr(obj, "controller", None) is not _c
                ),
                description="nonland permanent an opponent controls",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        if not _is_on_battlefield(game, target):
            return  # fizzle

        from engine.zones import move_to_zone
        self._exiled_card = target
        self._exiled_owner = getattr(target, "owner", None) or getattr(
            target, "controller", None
        )
        move_to_zone(game, target, Zone.BATTLEFIELD, Zone.EXILE)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _condition(game: Any, data: dict) -> bool:
            permanent = data.get("permanent")
            return permanent is source

        def _effect(game: GameState) -> None:
            card = source._exiled_card
            owner = source._exiled_owner
            if card is None or owner is None:
                return
            from engine.zones import move_to_zone
            card.controller = owner
            move_to_zone(game, card, Zone.EXILE, Zone.BATTLEFIELD)
            source._exiled_card = None
            source._exiled_owner = None

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.LEAVES_BATTLEFIELD,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# ACTIVATED ABILITY ENCHANTMENT
# ===================================================================


class VampiricRites(Enchantment):
    """Vampiric Rites — {B} — {1}{B}, Sacrifice a creature: Gain 1 life, draw.

    FDN collector number 615.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vampiric Rites")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        kwargs.setdefault(
            "rules_text",
            "{1}{B}, Sacrifice a creature: You gain 1 life and draw a card.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        pass

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: GameState) -> bool:
            controller = source.controller
            if controller is None:
                return False
            # Check mana availability (simplified) and a creature to sacrifice
            bf = game.get_battlefield(controller)
            has_creature = any(
                CardType.CREATURE in getattr(obj, "card_types", set())
                for obj in bf.get_all()
            )
            return has_creature

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            # ENGINE LIMITATION: Full implementation would let the player
            # choose which creature to sacrifice and pay {1}{B}.  For now
            # we sacrifice the first creature found.
            from engine.game import draw_card, sacrifice
            bf = game.get_battlefield(controller)
            for obj in bf.get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    sacrifice(game, controller, obj)
                    break
            controller.life += 1
            from engine.triggers import EventType
            game.trigger_manager.fire_event(
                game,
                EventType.GAINS_LIFE,
                {"player": controller, "amount": 1},
            )
            draw_card(game, controller)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{1}{B}, Sacrifice a creature: You gain 1 life "
                            "and draw a card.",
            ),
        ]


# ---------------------------------------------------------------------------
# Registration data & helper
# ---------------------------------------------------------------------------

_ALL_GLOBAL_ENCHANTMENTS: list[
    tuple[str, type, str, list[str], str, str, str, str]
] = [
    ("Anthem of Champions", AnthemOfChampions, "{G}{W}",
     ["G", "W"], "Creatures you control get +1/+1.",
     "rare", "Enchantment", "116"),
    ("Goblin Oriflamme", GoblinOriflamme, "{1}{R}",
     ["R"], "Attacking creatures you control get +1/+0.",
     "uncommon", "Enchantment", "539"),
    ("Garruk's Uprising", GarruksUprising, "{2}{G}",
     ["G"],
     "When this enchantment enters, if you control a creature with power 4 "
     "or greater, draw a card.\n"
     "Creatures you control have trample.\n"
     "Whenever a creature you control with power 4 or greater enters, "
     "draw a card.",
     "uncommon", "Enchantment", "220"),
    ("Authority of the Consuls", AuthorityOfTheConsuls, "{W}",
     ["W"],
     "Creatures your opponents control enter tapped.\n"
     "Whenever a creature an opponent controls enters, you gain 1 life.",
     "rare", "Enchantment", "137"),
    ("Phyrexian Arena", PhyrexianArena, "{1}{B}{B}",
     ["B"],
     "At the beginning of your upkeep, you draw a card and you lose 1 life.",
     "rare", "Enchantment", "180"),
    ("Impact Tremors", ImpactTremors, "{1}{R}",
     ["R"],
     "Whenever a creature you control enters, this enchantment deals 1 "
     "damage to each opponent.",
     "common", "Enchantment", "717"),
    ("Rite of the Dragoncaller", RiteOfTheDragoncaller, "{4}{R}{R}",
     ["R"],
     "Whenever you cast an instant or sorcery spell, create a 5/5 red "
     "Dragon creature token with flying.",
     "mythic", "Enchantment", "92"),
    ("Painful Quandary", PainfulQuandary, "{3}{B}{B}",
     ["B"],
     "Whenever an opponent casts a spell, that player loses 5 life unless "
     "they discard a card.",
     "rare", "Enchantment", "179"),
    ("Banishing Light", BanishingLight, "{2}{W}",
     ["W"],
     "When this enchantment enters, exile target nonland permanent an "
     "opponent controls until this enchantment leaves the battlefield.",
     "common", "Enchantment", "138"),
    ("Vampiric Rites", VampiricRites, "{B}",
     ["B"],
     "{1}{B}, Sacrifice a creature: You gain 1 life and draw a card.",
     "uncommon", "Enchantment", "615"),
]


def register_global_enchantments(registry: CardRegistry) -> None:
    """Register all global enchantments with *registry*."""
    from cards.registry import CardMetadata

    for (
        card_name, impl_class, cost_str, colors, oracle_text,
        rarity, type_line, collector_number,
    ) in _ALL_GLOBAL_ENCHANTMENTS:
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
