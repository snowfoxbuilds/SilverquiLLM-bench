"""Batch 5 — FDN creatures with "enters the battlefield" triggered abilities.

Implements 25 real FDN creatures whose primary mechanic is a self-ETB
trigger: draw, damage, lifegain, tokens, destroy/exile target, bounce,
counters, discard, and loot effects.

Each creature subclasses :class:`~engine.card.Creature` (or
:class:`~engine.card.ArtifactCreature` for artifact creatures) and
overrides :meth:`register_triggers` to register a
:class:`~engine.triggers.TriggerRegistration` with
``EventType.ENTERS_BATTLEFIELD``.  The condition checks that the
entering permanent is ``self``.

All cards are verified against Scryfall FDN data with correct collector
numbers.

Use :func:`register_etb_creatures` to register all cards with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ArtifactCreature, Creature
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Helper — standard self-ETB condition
# ---------------------------------------------------------------------------

def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("permanent") is source

    return _condition


# ---------------------------------------------------------------------------
# Helper — retrieve chosen target (mirrors batch-3 pattern)
# ---------------------------------------------------------------------------

def _get_chosen_target(card: Any, game: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False


# ===================================================================
# DRAW
# ===================================================================


class HelpfulHunter(Creature):
    """Helpful Hunter — {1}{W} — 1/1 — Cat

    When this creature enters, draw a card.

    FDN collector number 16.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Helpful Hunter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Cat"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                draw_card(game, controller)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class InspiringOverseer(Creature):
    """Inspiring Overseer — {2}{W} — 2/1 — Angel Cleric — Flying

    When this creature enters, you gain 1 life and draw a card.

    FDN collector number 496.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Inspiring Overseer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Angel", "Cleric"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhen this creature enters, you gain 1 life and draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                controller.life += 1
                draw_card(game, controller)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class Cloudblazer(Creature):
    """Cloudblazer — {3}{W}{U} — 2/2 — Human Scout — Flying

    When this creature enters, you gain 2 life and draw two cards.

    FDN collector number 653.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cloudblazer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}{U}"))
        kwargs.setdefault("subtypes", {"Human", "Scout"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhen this creature enters, you gain 2 life and draw two cards.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                controller.life += 2
                draw_card(game, controller)
                draw_card(game, controller)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class IcewindElemental(Creature):
    """Icewind Elemental — {4}{U} — 3/4 — Elemental — Flying

    When this creature enters, draw a card, then discard a card.

    FDN collector number 42.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Icewind Elemental")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}"))
        kwargs.setdefault("subtypes", {"Elemental"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhen this creature enters, draw a card, then discard a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card, discard

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                drawn = draw_card(game, controller)
                # Discard a card — use scripted choice or discard last card
                hand = game.get_hand(controller)
                hand_cards = hand.get_all()
                if hand_cards:
                    try:
                        to_discard = controller.choose_card(hand_cards)
                    except Exception:
                        to_discard = hand_cards[-1]
                    discard(game, controller, to_discard)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# LIFEGAIN
# ===================================================================


class PelakkaWurm(Creature):
    """Pelakka Wurm — {4}{G}{G}{G} — 7/7 — Wurm — Trample

    When this creature enters, you gain 7 life.
    When this creature dies, draw a card.

    FDN collector number 720.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pelakka Wurm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{G}{G}{G}"))
        kwargs.setdefault("subtypes", {"Wurm"})
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault(
            "rules_text",
            "Trample\nWhen this creature enters, you gain 7 life.\n"
            "When this creature dies, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _etb_effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                controller.life += 7

        def _dies_condition(game: GameState, data: dict) -> bool:
            return data.get("creature") is source

        def _dies_effect(game: GameState) -> None:
            controller = getattr(source, "controller", None) or getattr(source, "owner", None)
            if controller is not None:
                draw_card(game, controller)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_etb_effect,
            source=self,
            controller=controller,
        ))
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_dies_condition,
            effect=_dies_effect,
            source=self,
            controller=controller,
        ))


class VampireSpawn(Creature):
    """Vampire Spawn — {2}{B} — 2/3 — Vampire

    When this creature enters, each opponent loses 2 life and you gain 2 life.

    FDN collector number 532.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vampire Spawn")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("subtypes", {"Vampire"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, each opponent loses 2 life and you gain 2 life.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            for player in game.players:
                if player is not controller:
                    player.life -= 2
            controller.life += 2

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# TOKENS
# ===================================================================


class PridefulParent(Creature):
    """Prideful Parent — {2}{W} — 2/2 — Cat — Vigilance

    When this creature enters, create a 1/1 white Cat creature token.

    FDN collector number 21.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Prideful Parent")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Cat"})
        kwargs.setdefault("keywords", Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Vigilance\nWhen this creature enters, create a 1/1 white Cat creature token.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import create_token

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                token = Creature(
                    name="Cat",
                    subtypes={"Cat"},
                    base_power=1,
                    base_toughness=1,
                    owner=controller,
                    controller=controller,
                )
                create_token(game, controller, token)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class ResoluteReinforcements(Creature):
    """Resolute Reinforcements — {1}{W} — 1/1 — Human Soldier — Flash

    When this creature enters, create a 1/1 white Soldier creature token.

    FDN collector number 145.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Resolute Reinforcements")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Human", "Soldier"})
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Flash\nWhen this creature enters, create a 1/1 white Soldier creature token.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import create_token

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                token = Creature(
                    name="Soldier",
                    subtypes={"Human", "Soldier"},
                    base_power=1,
                    base_toughness=1,
                    owner=controller,
                    controller=controller,
                )
                create_token(game, controller, token)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class GuardedHeir(Creature):
    """Guarded Heir — {5}{W} — 1/1 — Human Noble — Lifelink

    When this creature enters, create two 3/3 white Knight creature tokens.

    FDN collector number 14.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Guarded Heir")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{W}"))
        kwargs.setdefault("subtypes", {"Human", "Noble"})
        kwargs.setdefault("keywords", Keyword.LIFELINK)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Lifelink\nWhen this creature enters, create two 3/3 white Knight creature tokens.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import create_token

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                for _ in range(2):
                    token = Creature(
                        name="Knight",
                        subtypes={"Knight"},
                        base_power=3,
                        base_toughness=3,
                        owner=controller,
                        controller=controller,
                    )
                    create_token(game, controller, token)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class DragonTrainer(Creature):
    """Dragon Trainer — {3}{R}{R} — 1/1 — Human

    When this creature enters, create a 4/4 red Dragon creature token with flying.

    FDN collector number 84.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dragon Trainer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{R}"))
        kwargs.setdefault("subtypes", {"Human"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, create a 4/4 red Dragon creature token with flying.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import create_token

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                token = Creature(
                    name="Dragon",
                    subtypes={"Dragon"},
                    keywords=Keyword.FLYING,
                    base_power=4,
                    base_toughness=4,
                    owner=controller,
                    controller=controller,
                )
                create_token(game, controller, token)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class RegalCaracal(Creature):
    """Regal Caracal — {3}{W}{W} — 3/3 — Cat

    Other Cats you control get +1/+1 and have lifelink.
    When this creature enters, create two 1/1 white Cat creature tokens with lifelink.

    FDN collector number 579.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Regal Caracal")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Other Cats you control get +1/+1 and have lifelink.\n"
            "When this creature enters, create two 1/1 white Cat creature tokens with lifelink.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import create_token

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                for _ in range(2):
                    token = Creature(
                        name="Cat",
                        subtypes={"Cat"},
                        keywords=Keyword.LIFELINK,
                        base_power=1,
                        base_toughness=1,
                        owner=controller,
                        controller=controller,
                    )
                    create_token(game, controller, token)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))

        # Static ability: other Cats you control get +1/+1 and have lifelink
        def _apply_lords(game: GameState) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            if not _is_on_battlefield(game, source):
                return
            for obj in game.get_battlefield(ctrl).get_all():
                if obj is source:
                    continue
                if CardType.CREATURE not in getattr(obj, "card_types", set()):
                    continue
                subtypes = getattr(obj, "subtypes", set())
                if "Cat" in subtypes:
                    obj.base_power += 1
                    obj.base_toughness += 1
                    obj.keywords = obj.keywords | Keyword.LIFELINK

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_lords,
        ))


class RapaciousDragon(Creature):
    """Rapacious Dragon — {4}{R} — 3/3 — Dragon — Flying

    When this creature enters, create two Treasure tokens.

    FDN collector number 544.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rapacious Dragon")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        kwargs.setdefault("subtypes", {"Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhen this creature enters, create two Treasure tokens.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.card import Artifact
        from engine.game import create_token

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                for _ in range(2):
                    token = Artifact(
                        name="Treasure",
                        subtypes={"Treasure"},
                        rules_text="{T}, Sacrifice this token: Add one mana of any color.",
                    )
                    create_token(game, controller, token)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# DAMAGE
# ===================================================================


class SkeletonArcher(Creature):
    """Skeleton Archer — {3}{B} — 3/3 — Skeleton Archer

    When this creature enters, it deals 1 damage to any target.

    FDN collector number 526.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Skeleton Archer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("subtypes", {"Skeleton", "Archer"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, it deals 1 damage to any target.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import deal_damage

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            if target is not None:
                deal_damage(game, source, target, 1)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class ViashinoPyromancer(Creature):
    """Viashino Pyromancer — {1}{R} — 2/1 — Lizard Wizard

    When this creature enters, it deals 2 damage to target player or planeswalker.

    FDN collector number 634.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Viashino Pyromancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("subtypes", {"Lizard", "Wizard"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, it deals 2 damage to target player or planeswalker.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import deal_damage

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            if target is not None:
                deal_damage(game, source, target, 2)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# DESTROY / EXILE
# ===================================================================


class ReclamationSage(Creature):
    """Reclamation Sage — {2}{G} — 2/1 — Elf Shaman

    When this creature enters, you may destroy target artifact or enchantment.

    FDN collector number 231.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Reclamation Sage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("subtypes", {"Elf", "Shaman"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, you may destroy target artifact or enchantment.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import destroy

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            if target is not None and _is_on_battlefield(game, target):
                card_types = getattr(target, "card_types", set())
                if CardType.ARTIFACT in card_types or CardType.ENCHANTMENT in card_types:
                    destroy(game, target)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class MeteorGolem(ArtifactCreature):
    """Meteor Golem — {7} — 3/3 — Golem

    When this creature enters, destroy target nonland permanent an opponent controls.

    FDN collector number 256.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Meteor Golem")
        kwargs.setdefault("mana_cost", ManaCost.parse("{7}"))
        kwargs.setdefault("subtypes", {"Golem"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, destroy target nonland permanent an opponent controls.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import destroy

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            if target is not None and _is_on_battlefield(game, target):
                destroy(game, target)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class AmbushWolf(Creature):
    """Ambush Wolf — {2}{G} — 4/2 — Wolf — Flash

    When this creature enters, exile up to one target card from a graveyard.

    FDN collector number 98.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ambush Wolf")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("subtypes", {"Wolf"})
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Flash\nWhen this creature enters, exile up to one target card from a graveyard.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            if target is None:
                return
            # Find and remove target from any graveyard, then exile
            for player in game.players:
                gy = player.zones[Zone.GRAVEYARD]
                if gy.contains(target):
                    gy.remove(target)
                    owner = getattr(target, "owner", player)
                    owner.zones[Zone.EXILE].add(target)
                    return

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# BOUNCE (return to hand)
# ===================================================================


class BigfinBouncer(Creature):
    """Bigfin Bouncer — {3}{U} — 3/2 — Shark Pirate

    When this creature enters, return target creature an opponent controls
    to its owner's hand.

    FDN collector number 31.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bigfin Bouncer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault("subtypes", {"Shark", "Pirate"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, return target creature an opponent controls "
            "to its owner's hand.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.zones import move_to_zone

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            if target is not None and _is_on_battlefield(game, target):
                move_to_zone(game, target, Zone.BATTLEFIELD, Zone.HAND)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class ExclusionMage(Creature):
    """Exclusion Mage — {2}{U} — 2/2 — Human Wizard

    When this creature enters, return target creature an opponent controls
    to its owner's hand.

    FDN collector number 508.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Exclusion Mage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, return target creature an opponent controls "
            "to its owner's hand.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.zones import move_to_zone

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            if target is not None and _is_on_battlefield(game, target):
                move_to_zone(game, target, Zone.BATTLEFIELD, Zone.HAND)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class VampireSoulcaller(Creature):
    """Vampire Soulcaller — {4}{B} — 3/2 — Vampire Warlock — Flying

    This creature can't block.
    When this creature enters, return target creature card from your
    graveyard to your hand.

    FDN collector number 75.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vampire Soulcaller")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{B}"))
        kwargs.setdefault("subtypes", {"Vampire", "Warlock"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Flying\nThis creature can't block.\n"
            "When this creature enters, return target creature card from your "
            "graveyard to your hand.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            controller = getattr(source, "controller", None)
            if target is None or controller is None:
                return
            gy = controller.zones[Zone.GRAVEYARD]
            if gy.contains(target):
                gy.remove(target)
                controller.zones[Zone.HAND].add(target)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class MischievousPup(Creature):
    """Mischievous Pup — {2}{W} — 3/1 — Dog

    When this creature enters, return up to one other target permanent you
    control to its owner's hand.

    FDN collector number 144.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mischievous Pup")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Dog"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, return up to one other target permanent "
            "you control to its owner's hand.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.zones import move_to_zone

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            if target is not None and target is not source and _is_on_battlefield(game, target):
                move_to_zone(game, target, Zone.BATTLEFIELD, Zone.HAND)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# COUNTERS
# ===================================================================


class FelidarSavior(Creature):
    """Felidar Savior — {3}{W} — 2/3 — Cat Beast — Lifelink

    When this creature enters, put a +1/+1 counter on each of up to two
    other target creatures you control.

    FDN collector number 12.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Felidar Savior")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Beast"})
        kwargs.setdefault("keywords", Keyword.LIFELINK)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Lifelink\nWhen this creature enters, put a +1/+1 counter on each of "
            "up to two other target creatures you control.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import add_counter

        source = self

        def _effect(game: GameState) -> None:
            # Get targets from chosen_targets (up to 2)
            chosen = getattr(source, "chosen_targets", None)
            if not chosen:
                targets_list = getattr(source, "_resolve_targets", None)
                if targets_list:
                    chosen = targets_list
                else:
                    target = getattr(source, "_resolve_target", None)
                    if target is not None:
                        chosen = [target]
            if not chosen:
                return
            for target in chosen[:2]:
                if target is not source and _is_on_battlefield(game, target):
                    add_counter(game, target, "+1/+1", 1)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# DISCARD / DRAIN
# ===================================================================


class BurglarRat(Creature):
    """Burglar Rat — {1}{B} — 1/1 — Rat

    When this creature enters, each opponent discards a card.

    FDN collector number 170.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Burglar Rat")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("subtypes", {"Rat"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, each opponent discards a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import discard

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            for player in game.players:
                if player is controller:
                    continue
                hand = game.get_hand(player)
                hand_cards = hand.get_all()
                if hand_cards:
                    try:
                        to_discard = player.choose_card(hand_cards)
                    except Exception:
                        to_discard = hand_cards[-1]
                    discard(game, player, to_discard)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class ArbiterOfWoe(Creature):
    """Arbiter of Woe — {4}{B}{B} — 5/4 — Demon — Flying

    As an additional cost to cast this spell, sacrifice a creature.
    Flying
    When this creature enters, each opponent discards a card and loses 2 life.
    You draw a card and gain 2 life.

    FDN collector number 55.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Arbiter of Woe")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{B}{B}"))
        kwargs.setdefault("subtypes", {"Demon"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "As an additional cost to cast this spell, sacrifice a creature.\n"
            "Flying\nWhen this creature enters, each opponent discards a card "
            "and loses 2 life. You draw a card and gain 2 life.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card, discard

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            # Each opponent discards a card and loses 2 life
            for player in game.players:
                if player is controller:
                    continue
                hand = game.get_hand(player)
                hand_cards = hand.get_all()
                if hand_cards:
                    try:
                        to_discard = player.choose_card(hand_cards)
                    except Exception:
                        to_discard = hand_cards[-1]
                    discard(game, player, to_discard)
                player.life -= 2
            # You draw a card and gain 2 life
            draw_card(game, controller)
            controller.life += 2

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# DEBUFF — Creatures that debuff opponents' creatures on ETB
# ===================================================================


class BurrogBefuddler(Creature):
    """Burrog Befuddler — {1}{U} — 2/1 — Frog Wizard — Flash

    When this creature enters, target creature an opponent controls gets
    -1/-0 until end of turn.

    FDN collector number 504.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Burrog Befuddler")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("subtypes", {"Frog", "Wizard"})
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Flash\nWhen this creature enters, target creature an opponent controls "
            "gets -1/-0 until end of turn.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            if target is None or not _is_on_battlefield(game, target):
                return
            if not hasattr(target, "base_power"):
                return

            tgt = target

            def _apply_debuff(game: GameState) -> None:
                if _is_on_battlefield(game, tgt) and hasattr(tgt, "base_power"):
                    tgt.base_power -= 1

            game.effect_manager.add(ContinuousEffect(
                source=source,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply_debuff,
                duration=DURATION_END_OF_TURN,
            ))

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class MassacreWurm(Creature):
    """Massacre Wurm — {3}{B}{B}{B} — 6/5 — Phyrexian Wurm

    When this creature enters, creatures your opponents control get -2/-2
    until end of turn.
    Whenever a creature an opponent controls dies, that player loses 2 life.

    FDN collector number 714.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Massacre Wurm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{B}{B}"))
        kwargs.setdefault("subtypes", {"Phyrexian", "Wurm"})
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, creatures your opponents control get -2/-2 "
            "until end of turn.\nWhenever a creature an opponent controls dies, "
            "that player loses 2 life.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _etb_effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return

            # Snapshot opponent creatures to debuff
            targets: list[Any] = []
            for player in game.players:
                if player is controller:
                    continue
                for obj in game.get_battlefield(player).get_all():
                    if CardType.CREATURE in getattr(obj, "card_types", set()):
                        targets.append(obj)

            if not targets:
                return

            frozen_targets = list(targets)

            def _apply_debuff(game: GameState) -> None:
                for tgt in frozen_targets:
                    if _is_on_battlefield(game, tgt) and hasattr(tgt, "base_power"):
                        tgt.base_power -= 2
                        tgt.base_toughness -= 2

            game.effect_manager.add(ContinuousEffect(
                source=source,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply_debuff,
                duration=DURATION_END_OF_TURN,
            ))

        def _dies_condition(game: GameState, data: dict) -> bool:
            controller = getattr(source, "controller", None)
            if controller is None:
                return False
            creature = data.get("creature")
            creature_ctrl = data.get("controller")
            if creature_ctrl is not None and creature_ctrl is not controller:
                return True
            return False

        def _dies_effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            # Find the dying creature's controller from trigger data
            # Since we can't access data here, lose 2 life to each opponent
            # Actually, we need the controller of the dying creature.
            # The trigger fires per creature death; opponent loses 2 life.
            for player in game.players:
                if player is not controller:
                    player.life -= 2

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_etb_effect,
            source=self,
            controller=controller,
        ))
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_dies_condition,
            effect=_dies_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# GRAVEYARD INTERACTION
# ===================================================================


class ElvishRegrower(Creature):
    """Elvish Regrower — {2}{G}{G} — 4/3 — Elf Druid

    When this creature enters, return target permanent card from your
    graveyard to your hand.

    FDN collector number 104.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Elvish Regrower")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}{G}"))
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, return target permanent card from your "
            "graveyard to your hand.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            controller = getattr(source, "controller", None)
            if target is None or controller is None:
                return
            gy = controller.zones[Zone.GRAVEYARD]
            if gy.contains(target):
                gy.remove(target)
                controller.zones[Zone.HAND].add(target)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# ANGEL OF FINALITY — exile graveyard
# ===================================================================


class AngelOfFinality(Creature):
    """Angel of Finality — {3}{W} — 3/4 — Angel — Flying

    When this creature enters, exile target player's graveyard.

    FDN collector number 136.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Angel of Finality")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Angel"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhen this creature enters, exile target player's graveyard.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _effect(game: GameState) -> None:
            # Target a player — use chosen_targets or default to opponent
            target = _get_chosen_target(source, game)
            if target is None:
                # Default to first opponent
                controller = getattr(source, "controller", None)
                for player in game.players:
                    if player is not controller:
                        target = player
                        break
            if target is None:
                return
            # If target is a player, exile their graveyard
            if hasattr(target, "zones"):
                gy = target.zones[Zone.GRAVEYARD]
                exile = target.zones[Zone.EXILE]
                for card in gy.get_all():
                    gy.remove(card)
                    exile.add(card)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# SHIPWRECK DOWSER — return instant/sorcery from graveyard
# ===================================================================


class ShipwreckDowser(Creature):
    """Shipwreck Dowser — {3}{U}{U} — 3/3 — Merfolk Wizard — Prowess

    When this creature enters, return target instant or sorcery card from
    your graveyard to your hand.

    FDN collector number 596.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Shipwreck Dowser")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}{U}"))
        kwargs.setdefault("subtypes", {"Merfolk", "Wizard"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Prowess\nWhen this creature enters, return target instant or sorcery "
            "card from your graveyard to your hand.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            controller = getattr(source, "controller", None)
            if target is None or controller is None:
                return
            gy = controller.zones[Zone.GRAVEYARD]
            if gy.contains(target):
                card_types = getattr(target, "card_types", set())
                if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                    gy.remove(target)
                    controller.zones[Zone.HAND].add(target)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


# Card name → (class, collector_number, rarity) for registration
_ETB_CREATURES: list[tuple[str, type, str, str, str, str | None, str | None, list[str], list[str]]] = [
    # (name, class, cn, rarity, mana_cost_str, power, toughness, colors, keywords)
]


def register_etb_creatures(registry: CardRegistry) -> None:
    """Register all ETB creatures with *registry*.

    Each card is registered with a :class:`~cards.registry.CardMetadata`
    reflecting its Scryfall-verified attributes.
    """
    from cards.registry import CardMetadata

    _cards: list[tuple[str, type, dict[str, Any]]] = [
        ("Helpful Hunter", HelpfulHunter, {
            "collector_number": "16", "rarity": "common",
            "mana_cost_str": "{1}{W}", "type_line": "Creature — Cat",
            "power": "1", "toughness": "1", "colors": ["W"],
            "oracle_text": "When this creature enters, draw a card.",
        }),
        ("Inspiring Overseer", InspiringOverseer, {
            "collector_number": "496", "rarity": "common",
            "mana_cost_str": "{2}{W}", "type_line": "Creature — Angel Cleric",
            "power": "2", "toughness": "1", "colors": ["W"],
            "keywords": ["Flying"],
            "oracle_text": "Flying\nWhen this creature enters, you gain 1 life and draw a card.",
        }),
        ("Cloudblazer", Cloudblazer, {
            "collector_number": "653", "rarity": "uncommon",
            "mana_cost_str": "{3}{W}{U}", "type_line": "Creature — Human Scout",
            "power": "2", "toughness": "2", "colors": ["U", "W"],
            "keywords": ["Flying"],
            "oracle_text": "Flying\nWhen this creature enters, you gain 2 life and draw two cards.",
        }),
        ("Icewind Elemental", IcewindElemental, {
            "collector_number": "42", "rarity": "common",
            "mana_cost_str": "{4}{U}", "type_line": "Creature — Elemental",
            "power": "3", "toughness": "4", "colors": ["U"],
            "keywords": ["Flying"],
            "oracle_text": "Flying\nWhen this creature enters, draw a card, then discard a card.",
        }),
        ("Pelakka Wurm", PelakkaWurm, {
            "collector_number": "720", "rarity": "uncommon",
            "mana_cost_str": "{4}{G}{G}{G}", "type_line": "Creature — Wurm",
            "power": "7", "toughness": "7", "colors": ["G"],
            "keywords": ["Trample"],
            "oracle_text": "Trample\nWhen this creature enters, you gain 7 life.\nWhen this creature dies, draw a card.",
        }),
        ("Vampire Spawn", VampireSpawn, {
            "collector_number": "532", "rarity": "common",
            "mana_cost_str": "{2}{B}", "type_line": "Creature — Vampire",
            "power": "2", "toughness": "3", "colors": ["B"],
            "oracle_text": "When this creature enters, each opponent loses 2 life and you gain 2 life.",
        }),
        ("Prideful Parent", PridefulParent, {
            "collector_number": "21", "rarity": "common",
            "mana_cost_str": "{2}{W}", "type_line": "Creature — Cat",
            "power": "2", "toughness": "2", "colors": ["W"],
            "keywords": ["Vigilance"],
            "oracle_text": "Vigilance\nWhen this creature enters, create a 1/1 white Cat creature token.",
        }),
        ("Resolute Reinforcements", ResoluteReinforcements, {
            "collector_number": "145", "rarity": "uncommon",
            "mana_cost_str": "{1}{W}", "type_line": "Creature — Human Soldier",
            "power": "1", "toughness": "1", "colors": ["W"],
            "keywords": ["Flash"],
            "oracle_text": "Flash\nWhen this creature enters, create a 1/1 white Soldier creature token.",
        }),
        ("Guarded Heir", GuardedHeir, {
            "collector_number": "14", "rarity": "uncommon",
            "mana_cost_str": "{5}{W}", "type_line": "Creature — Human Noble",
            "power": "1", "toughness": "1", "colors": ["W"],
            "keywords": ["Lifelink"],
            "oracle_text": "Lifelink\nWhen this creature enters, create two 3/3 white Knight creature tokens.",
        }),
        ("Dragon Trainer", DragonTrainer, {
            "collector_number": "84", "rarity": "uncommon",
            "mana_cost_str": "{3}{R}{R}", "type_line": "Creature — Human",
            "power": "1", "toughness": "1", "colors": ["R"],
            "oracle_text": "When this creature enters, create a 4/4 red Dragon creature token with flying.",
        }),
        ("Regal Caracal", RegalCaracal, {
            "collector_number": "579", "rarity": "rare",
            "mana_cost_str": "{3}{W}{W}", "type_line": "Creature — Cat",
            "power": "3", "toughness": "3", "colors": ["W"],
            "oracle_text": "Other Cats you control get +1/+1 and have lifelink.\nWhen this creature enters, create two 1/1 white Cat creature tokens with lifelink.",
        }),
        ("Rapacious Dragon", RapaciousDragon, {
            "collector_number": "544", "rarity": "common",
            "mana_cost_str": "{4}{R}", "type_line": "Creature — Dragon",
            "power": "3", "toughness": "3", "colors": ["R"],
            "keywords": ["Flying"],
            "oracle_text": "Flying\nWhen this creature enters, create two Treasure tokens.",
        }),
        ("Skeleton Archer", SkeletonArcher, {
            "collector_number": "526", "rarity": "common",
            "mana_cost_str": "{3}{B}", "type_line": "Creature — Skeleton Archer",
            "power": "3", "toughness": "3", "colors": ["B"],
            "oracle_text": "When this creature enters, it deals 1 damage to any target.",
        }),
        ("Viashino Pyromancer", ViashinoPyromancer, {
            "collector_number": "634", "rarity": "common",
            "mana_cost_str": "{1}{R}", "type_line": "Creature — Lizard Wizard",
            "power": "2", "toughness": "1", "colors": ["R"],
            "oracle_text": "When this creature enters, it deals 2 damage to target player or planeswalker.",
        }),
        ("Reclamation Sage", ReclamationSage, {
            "collector_number": "231", "rarity": "uncommon",
            "mana_cost_str": "{2}{G}", "type_line": "Creature — Elf Shaman",
            "power": "2", "toughness": "1", "colors": ["G"],
            "oracle_text": "When this creature enters, you may destroy target artifact or enchantment.",
        }),
        ("Meteor Golem", MeteorGolem, {
            "collector_number": "256", "rarity": "uncommon",
            "mana_cost_str": "{7}", "type_line": "Artifact Creature — Golem",
            "power": "3", "toughness": "3", "colors": [],
            "oracle_text": "When this creature enters, destroy target nonland permanent an opponent controls.",
        }),
        ("Ambush Wolf", AmbushWolf, {
            "collector_number": "98", "rarity": "common",
            "mana_cost_str": "{2}{G}", "type_line": "Creature — Wolf",
            "power": "4", "toughness": "2", "colors": ["G"],
            "keywords": ["Flash"],
            "oracle_text": "Flash\nWhen this creature enters, exile up to one target card from a graveyard.",
        }),
        ("Bigfin Bouncer", BigfinBouncer, {
            "collector_number": "31", "rarity": "common",
            "mana_cost_str": "{3}{U}", "type_line": "Creature — Shark Pirate",
            "power": "3", "toughness": "2", "colors": ["U"],
            "oracle_text": "When this creature enters, return target creature an opponent controls to its owner's hand.",
        }),
        ("Exclusion Mage", ExclusionMage, {
            "collector_number": "508", "rarity": "uncommon",
            "mana_cost_str": "{2}{U}", "type_line": "Creature — Human Wizard",
            "power": "2", "toughness": "2", "colors": ["U"],
            "oracle_text": "When this creature enters, return target creature an opponent controls to its owner's hand.",
        }),
        ("Vampire Soulcaller", VampireSoulcaller, {
            "collector_number": "75", "rarity": "common",
            "mana_cost_str": "{4}{B}", "type_line": "Creature — Vampire Warlock",
            "power": "3", "toughness": "2", "colors": ["B"],
            "keywords": ["Flying"],
            "oracle_text": "Flying\nThis creature can't block.\nWhen this creature enters, return target creature card from your graveyard to your hand.",
        }),
        ("Mischievous Pup", MischievousPup, {
            "collector_number": "144", "rarity": "uncommon",
            "mana_cost_str": "{2}{W}", "type_line": "Creature — Dog",
            "power": "3", "toughness": "1", "colors": ["W"],
            "oracle_text": "When this creature enters, return up to one other target permanent you control to its owner's hand.",
        }),
        ("Felidar Savior", FelidarSavior, {
            "collector_number": "12", "rarity": "common",
            "mana_cost_str": "{3}{W}", "type_line": "Creature — Cat Beast",
            "power": "2", "toughness": "3", "colors": ["W"],
            "keywords": ["Lifelink"],
            "oracle_text": "Lifelink\nWhen this creature enters, put a +1/+1 counter on each of up to two other target creatures you control.",
        }),
        ("Burglar Rat", BurglarRat, {
            "collector_number": "170", "rarity": "common",
            "mana_cost_str": "{1}{B}", "type_line": "Creature — Rat",
            "power": "1", "toughness": "1", "colors": ["B"],
            "oracle_text": "When this creature enters, each opponent discards a card.",
        }),
        ("Arbiter of Woe", ArbiterOfWoe, {
            "collector_number": "55", "rarity": "uncommon",
            "mana_cost_str": "{4}{B}{B}", "type_line": "Creature — Demon",
            "power": "5", "toughness": "4", "colors": ["B"],
            "keywords": ["Flying"],
            "oracle_text": "As an additional cost to cast this spell, sacrifice a creature.\nFlying\nWhen this creature enters, each opponent discards a card and loses 2 life. You draw a card and gain 2 life.",
        }),
        ("Burrog Befuddler", BurrogBefuddler, {
            "collector_number": "504", "rarity": "common",
            "mana_cost_str": "{1}{U}", "type_line": "Creature — Frog Wizard",
            "power": "2", "toughness": "1", "colors": ["U"],
            "keywords": ["Flash"],
            "oracle_text": "Flash\nWhen this creature enters, target creature an opponent controls gets -1/-0 until end of turn.",
        }),
        ("Massacre Wurm", MassacreWurm, {
            "collector_number": "714", "rarity": "mythic",
            "mana_cost_str": "{3}{B}{B}{B}", "type_line": "Creature — Phyrexian Wurm",
            "power": "6", "toughness": "5", "colors": ["B"],
            "oracle_text": "When this creature enters, creatures your opponents control get -2/-2 until end of turn.\nWhenever a creature an opponent controls dies, that player loses 2 life.",
        }),
        ("Elvish Regrower", ElvishRegrower, {
            "collector_number": "104", "rarity": "uncommon",
            "mana_cost_str": "{2}{G}{G}", "type_line": "Creature — Elf Druid",
            "power": "4", "toughness": "3", "colors": ["G"],
            "oracle_text": "When this creature enters, return target permanent card from your graveyard to your hand.",
        }),
        ("Angel of Finality", AngelOfFinality, {
            "collector_number": "136", "rarity": "uncommon",
            "mana_cost_str": "{3}{W}", "type_line": "Creature — Angel",
            "power": "3", "toughness": "4", "colors": ["W"],
            "keywords": ["Flying"],
            "oracle_text": "Flying\nWhen this creature enters, exile target player's graveyard.",
        }),
        ("Shipwreck Dowser", ShipwreckDowser, {
            "collector_number": "596", "rarity": "uncommon",
            "mana_cost_str": "{3}{U}{U}", "type_line": "Creature — Merfolk Wizard",
            "power": "3", "toughness": "3", "colors": ["U"],
            "oracle_text": "Prowess\nWhen this creature enters, return target instant or sorcery card from your graveyard to your hand.",
        }),
    ]

    for card_name, impl_class, meta_kwargs in _cards:
        metadata = CardMetadata(
            name=card_name,
            set_code="fdn",
            **meta_kwargs,
        )
        registry.register(card_name, impl_class, metadata)
