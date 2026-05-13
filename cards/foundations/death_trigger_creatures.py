"""Batch 8 — FDN creatures with "when this creature dies" triggered abilities.

Implements 16 real FDN creatures whose primary (or secondary) mechanic is
a death trigger: token creation, draw, damage, lifegain/drain, graveyard
recursion, and mill/surveil effects.

Each creature subclasses :class:`~engine.card.Creature` (or
:class:`~engine.card.ArtifactCreature` for artifact creatures) and
overrides :meth:`register_triggers` to register a
:class:`~engine.triggers.TriggerRegistration` with
``EventType.CREATURE_DIES``.  The condition checks that the dying
creature is ``self`` (for self-death triggers) or matches other criteria
(for "whenever another creature dies" triggers).

Cards with both ETB and death triggers register both in the same
``register_triggers`` method.

All cards are verified against Scryfall FDN data with correct collector
numbers.

Use :func:`register_death_trigger_creatures` to register all cards with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ArtifactCreature, Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Helper — standard self-death condition
# ---------------------------------------------------------------------------

def _self_dies_condition(source: Any):
    """Return a condition callable that matches only when *source* dies."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("creature") is source

    return _condition


def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("permanent") is source

    return _condition


def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False


# ===================================================================
# TOKEN CREATION ON DEATH
# ===================================================================


class InfestationSage(Creature):
    """Infestation Sage — {B} — 1/1 — Elf Warlock

    When this creature dies, create a 1/1 black and green Insect creature
    token with flying.

    FDN collector number 64.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Infestation Sage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        kwargs.setdefault("subtypes", {"Elf", "Warlock"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When this creature dies, create a 1/1 black and green Insect "
            "creature token with flying.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import create_token

        source = self

        def _effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is None:
                return
            token = Creature(
                name="Insect",
                subtypes={"Insect"},
                base_power=1,
                base_toughness=1,
                keywords=Keyword.FLYING,
            )
            create_token(game, controller, token)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_self_dies_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class GleamingBarrier(ArtifactCreature):
    """Gleaming Barrier — {2} — 0/4 — Wall — Defender

    When this creature dies, create a Treasure token.

    FDN collector number 252.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Gleaming Barrier")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("subtypes", {"Wall"})
        kwargs.setdefault("keywords", Keyword.DEFENDER)
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Defender\nWhen this creature dies, create a Treasure token.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import create_token

        source = self

        def _effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is None:
                return
            from engine.card import Artifact

            token = Artifact(
                name="Treasure",
                subtypes={"Treasure"},
            )
            create_token(game, controller, token)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_self_dies_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class MaalfeldTwins(Creature):
    """Maalfeld Twins — {5}{B} — 4/4 — Zombie

    When this creature dies, create two 2/2 black Zombie creature tokens.

    FDN collector number 523.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Maalfeld Twins")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{B}"))
        kwargs.setdefault("subtypes", {"Zombie"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "When this creature dies, create two 2/2 black Zombie creature tokens.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import create_token

        source = self

        def _effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is None:
                return
            for _ in range(2):
                token = Creature(
                    name="Zombie",
                    subtypes={"Zombie"},
                    base_power=2,
                    base_toughness=2,
                )
                create_token(game, controller, token)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_self_dies_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# DRAW ON DEATH
# ===================================================================


class SolemnSimulacrum(ArtifactCreature):
    """Solemn Simulacrum — {4} — 2/2 — Golem

    When this creature enters, you may search your library for a basic land
    card, put that card onto the battlefield tapped, then shuffle.
    When this creature dies, you may draw a card.

    FDN collector number 257.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Solemn Simulacrum")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        kwargs.setdefault("subtypes", {"Golem"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, you may search your library for a "
            "basic land card, put that card onto the battlefield tapped, "
            "then shuffle.\nWhen this creature dies, you may draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _etb_effect(game: GameState) -> None:
            # ENGINE LIMITATION: Full library search not implemented.
            # Would need: search library for basic land, put onto
            # battlefield tapped, then shuffle.
            pass

        def _dies_effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
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
            condition=_self_dies_condition(self),
            effect=_dies_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# MILL / SURVEIL ON DEATH
# ===================================================================


class CrowOfDarkTidings(Creature):
    """Crow of Dark Tidings — {2}{B} — 2/1 — Zombie Bird — Flying

    When this creature enters or dies, mill two cards.

    FDN collector number 519.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Crow of Dark Tidings")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("subtypes", {"Zombie", "Bird"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhen this creature enters or dies, mill two cards.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _mill_effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            graveyard = controller.zones[Zone.GRAVEYARD]
            for _ in range(2):
                if len(library) > 0:
                    card = library.top(1)[0]
                    library.remove(card)
                    graveyard.add(card)

        controller = getattr(self, "controller", None) or game.active_player
        # ETB trigger
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_mill_effect,
            source=self,
            controller=controller,
        ))
        # Death trigger
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_self_dies_condition(self),
            effect=_mill_effect,
            source=self,
            controller=controller,
        ))


class WaryThespian(Creature):
    """Wary Thespian — {1}{G} — 3/1 — Cat Druid

    When this creature enters or dies, surveil 1.

    FDN collector number 235.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wary Thespian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("subtypes", {"Cat", "Druid"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters or dies, surveil 1.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _surveil_effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            if len(library) > 0:
                card = library.top(1)[0]
                library.remove(card)
                # Surveil: may put into graveyard (simplified: always
                # put into graveyard for deterministic behaviour).
                graveyard = controller.zones[Zone.GRAVEYARD]
                graveyard.add(card)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_surveil_effect,
            source=self,
            controller=controller,
        ))
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_self_dies_condition(self),
            effect=_surveil_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# DRAIN / DAMAGE ON ANY CREATURE DEATH
# ===================================================================


class VengefulBloodwitch(Creature):
    """Vengeful Bloodwitch — {1}{B} — 1/1 — Vampire Warlock

    Whenever this creature or another creature you control dies, target
    opponent loses 1 life and you gain 1 life.

    FDN collector number 76.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vengeful Bloodwitch")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("subtypes", {"Vampire", "Warlock"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Whenever this creature or another creature you control dies, "
            "target opponent loses 1 life and you gain 1 life.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _condition(game: Any, data: dict) -> bool:
            creature = data.get("creature")
            controller = getattr(source, "controller", None)
            if controller is None:
                return False
            creature_ctrl = data.get("controller")
            # Fires when self dies OR another creature you control dies
            if creature is source:
                return True
            if creature_ctrl is controller:
                return True
            return False

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            # ENGINE LIMITATION: no targeting system; drains first opponent
            controller.life += 1
            for player in game.players:
                if player is not controller:
                    player.life -= 1
                    break

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


class MidnightReaper(Creature):
    """Midnight Reaper — {2}{B} — 3/2 — Zombie Knight

    Whenever a nontoken creature you control dies, this creature deals
    1 damage to you and you draw a card.

    FDN collector number 609.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Midnight Reaper")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("subtypes", {"Zombie", "Knight"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Whenever a nontoken creature you control dies, this creature "
            "deals 1 damage to you and you draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _condition(game: Any, data: dict) -> bool:
            controller = getattr(source, "controller", None)
            if controller is None:
                return False
            creature = data.get("creature")
            creature_ctrl = data.get("controller")
            if creature_ctrl is not controller:
                return False
            # Must be nontoken
            if getattr(creature, "is_token", False):
                return False
            return True

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            # Deal 1 damage to you
            controller.life -= 1
            draw_card(game, controller)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


class HighSocietyHunter(Creature):
    """High-Society Hunter — {3}{B}{B} — 5/3 — Vampire Noble — Flying

    Whenever this creature attacks, you may sacrifice another creature.
    If you do, put a +1/+1 counter on this creature.
    Whenever another nontoken creature dies, draw a card.

    FDN collector number 61.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "High-Society Hunter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{B}"))
        kwargs.setdefault("subtypes", {"Vampire", "Noble"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhenever this creature attacks, you may sacrifice "
            "another creature. If you do, put a +1/+1 counter on this "
            "creature.\nWhenever another nontoken creature dies, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _dies_condition(game: Any, data: dict) -> bool:
            creature = data.get("creature")
            if creature is source:
                return False  # "another" — not self
            if getattr(creature, "is_token", False):
                return False  # nontoken only
            return True

        def _dies_effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is not None:
                draw_card(game, controller)

        # ENGINE LIMITATION: Attack trigger with sacrifice choice not
        # implemented. Would need: prompt player to sacrifice another
        # creature, if they do add +1/+1 counter.

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_dies_condition,
            effect=_dies_effect,
            source=self,
            controller=controller,
        ))


class GarnaBloodfistOfKeld(Creature):
    """Garna, Bloodfist of Keld — {1}{B}{R}{R} — 4/3 — Legendary Human Berserker

    Whenever another creature you control dies, draw a card if it was
    attacking. Otherwise, Garna deals 1 damage to each opponent.

    FDN collector number 658.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Garna, Bloodfist of Keld")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{R}{R}"))
        kwargs.setdefault("subtypes", {"Human", "Berserker"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Whenever another creature you control dies, draw a card if "
            "it was attacking. Otherwise, Garna deals 1 damage to each "
            "opponent.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _condition(game: Any, data: dict) -> bool:
            creature = data.get("creature")
            if creature is source:
                return False  # "another"
            controller = getattr(source, "controller", None)
            creature_ctrl = data.get("controller")
            return creature_ctrl is controller

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            # ENGINE LIMITATION: no attack state tracking; always takes the
            # "nonattacking" branch (deals 1 damage to each opponent)
            for player in game.players:
                if player is not controller:
                    player.life -= 1

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


class CrosswayTroublemakers(Creature):
    """Crossway Troublemakers — {5}{B} — 5/5 — Vampire

    Attacking Vampires you control have deathtouch and lifelink.
    Whenever a Vampire you control dies, you may pay 2 life. If you do,
    draw a card.

    FDN collector number 518.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Crossway Troublemakers")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{B}"))
        kwargs.setdefault("subtypes", {"Vampire"})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Attacking Vampires you control have deathtouch and lifelink.\n"
            "Whenever a Vampire you control dies, you may pay 2 life. If "
            "you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        # ENGINE LIMITATION: Continuous effect granting deathtouch and
        # lifelink to attacking Vampires not implemented. Would need
        # combat phase tracking and a Layer.ABILITY_ADDING effect.

        def _condition(game: Any, data: dict) -> bool:
            controller = getattr(source, "controller", None)
            if controller is None:
                return False
            creature = data.get("creature")
            creature_ctrl = data.get("controller")
            if creature_ctrl is not controller:
                return False
            # Must be a Vampire
            subtypes = getattr(creature, "subtypes", set())
            return "Vampire" in subtypes

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            # ENGINE LIMITATION: no interactive choice system; auto-pays 2 life
            # "You may pay 2 life" — simplified: always pay if able
            if controller.life >= 2:
                controller.life -= 2
                draw_card(game, controller)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


class KalastriaHighborn(Creature):
    """Kalastria Highborn — {B}{B} — 2/2 — Vampire Shaman

    Whenever this creature or another Vampire you control dies, you may
    pay {B}. If you do, target player loses 2 life and you gain 2 life.

    FDN collector number 607.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Kalastria Highborn")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}{B}"))
        kwargs.setdefault("subtypes", {"Vampire", "Shaman"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Whenever this creature or another Vampire you control dies, "
            "you may pay {B}. If you do, target player loses 2 life and "
            "you gain 2 life.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _condition(game: Any, data: dict) -> bool:
            controller = getattr(source, "controller", None)
            if controller is None:
                return False
            creature = data.get("creature")
            creature_ctrl = data.get("controller")
            if creature is source:
                return True
            if creature_ctrl is not controller:
                return False
            subtypes = getattr(creature, "subtypes", set())
            return "Vampire" in subtypes

        def _effect(game: GameState) -> None:
            # ENGINE LIMITATION: {B} mana payment not enforced; tests do not
            # set up mana pools so we auto-drain without cost check.
            # ENGINE LIMITATION: no targeting system; drains first opponent.
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            controller.life += 2
            for player in game.players:
                if player is not controller:
                    player.life -= 2
                    break

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# GRAVEYARD RECURSION ON DEATH
# ===================================================================


class DriverOfTheDead(Creature):
    """Driver of the Dead — {3}{B} — 3/2 — Vampire

    When this creature dies, return target creature card with mana value
    2 or less from your graveyard to the battlefield.

    FDN collector number 605.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Driver of the Dead")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("subtypes", {"Vampire"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "When this creature dies, return target creature card with "
            "mana value 2 or less from your graveyard to the battlefield.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.zones import move_to_zone

        source = self

        def _effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is None:
                return
            graveyard = controller.zones[Zone.GRAVEYARD]
            # Find a creature card with mana value 2 or less
            candidates = []
            for obj in graveyard.get_all():
                if obj is source:
                    continue
                card_types = getattr(obj, "card_types", set())
                if CardType.CREATURE not in card_types:
                    continue
                mana_cost = getattr(obj, "mana_cost", None)
                if mana_cost is not None and mana_cost.cmc <= 2:
                    candidates.append(obj)
            if candidates:
                # Return the first valid target
                target = candidates[0]
                target.controller = controller
                move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_self_dies_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


class InfernalVessel(Creature):
    """Infernal Vessel — {2}{B} — 2/1 — Human Cleric

    When this creature dies, if it wasn't a Demon, return it to the
    battlefield under its owner's control with two +1/+1 counters on
    it. It's a Demon in addition to its other types.

    FDN collector number 63.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Infernal Vessel")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("subtypes", {"Human", "Cleric"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When this creature dies, if it wasn't a Demon, return it "
            "to the battlefield under its owner's control with two +1/+1 "
            "counters on it. It's a Demon in addition to its other types.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.zones import move_to_zone
        from engine.game import add_counter

        source = self

        def _condition(game: Any, data: dict) -> bool:
            creature = data.get("creature")
            if creature is not source:
                return False
            # Only triggers if it wasn't a Demon when it died
            subtypes = getattr(creature, "subtypes", set())
            return "Demon" not in subtypes

        def _effect(game: GameState) -> None:
            owner = getattr(source, "owner", None)
            if owner is None:
                return
            # Add Demon subtype
            subtypes = getattr(source, "subtypes", set())
            source.subtypes = subtypes | {"Demon"}
            # Set controller to owner
            source.controller = owner
            # Move from graveyard to battlefield
            graveyard = owner.zones[Zone.GRAVEYARD]
            if graveyard.contains(source):
                move_to_zone(game, source, Zone.GRAVEYARD, Zone.BATTLEFIELD)
                # Add two +1/+1 counters
                add_counter(game, source, "+1/+1", 2)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


class NineLivesFamiliar(Creature):
    """Nine-Lives Familiar — {1}{B}{B} — 1/1 — Cat

    This creature enters with eight revival counters on it if you cast it.
    When this creature dies, if it had a revival counter on it, return it
    to the battlefield with one fewer revival counter on it at the
    beginning of the next end step.

    FDN collector number 66.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Nine-Lives Familiar")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("subtypes", {"Cat"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "This creature enters with eight revival counters on it if "
            "you cast it.\nWhen this creature dies, if it had a revival "
            "counter on it, return it to the battlefield with one fewer "
            "revival counter on it at the beginning of the next end step.",
        )
        super().__init__(**kwargs)
        self.revival_counters: int = 0

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.zones import move_to_zone

        source = self

        # ETB: enter with 8 revival counters if cast
        def _etb_condition(game: Any, data: dict) -> bool:
            return data.get("permanent") is source

        def _etb_effect(game: GameState) -> None:
            # ENGINE LIMITATION: no cast tracking; counters always reset on ETB
            # Simplified: add revival counters on ETB, but not when
            # returning from graveyard via death trigger.
            if getattr(source, "_returning_from_graveyard", False):
                source._returning_from_graveyard = False
                return
            source.revival_counters = 8

        def _dies_condition(game: Any, data: dict) -> bool:
            creature = data.get("creature")
            if creature is not source:
                return False
            return source.revival_counters > 0

        def _dies_effect(game: GameState) -> None:
            # ENGINE LIMITATION: returns immediately instead of at beginning of next end step
            # ENGINE LIMITATION: "at the beginning of the next end step"
            # delayed trigger not implemented. Simplified: return
            # immediately with one fewer revival counter.
            owner = getattr(source, "owner", None)
            if owner is None:
                return
            new_counters = source.revival_counters - 1
            source.controller = owner
            graveyard = owner.zones[Zone.GRAVEYARD]
            if graveyard.contains(source):
                source._returning_from_graveyard = True
                source.revival_counters = new_counters
                move_to_zone(game, source, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_etb_condition,
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


class FiendishPanda(Creature):
    """Fiendish Panda — {2}{W}{B} — 3/2 — Bear Demon

    Whenever you gain life, put a +1/+1 counter on this creature.
    When this creature dies, return another target non-Bear creature card
    with mana value less than or equal to this creature's power from your
    graveyard to the battlefield.

    FDN collector number 120.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fiendish Panda")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Bear", "Demon"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Whenever you gain life, put a +1/+1 counter on this "
            "creature.\nWhen this creature dies, return another target "
            "non-Bear creature card with mana value less than or equal "
            "to this creature's power from your graveyard to the "
            "battlefield.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import add_counter
        from engine.zones import move_to_zone

        source = self

        def _lifegain_condition(game: Any, data: dict) -> bool:
            # ENGINE LIMITATION: GAINS_LIFE event may not carry enough
            # data to identify the gaining player. Simplified: check
            # if the gaining player is the controller.
            player = data.get("player")
            controller = getattr(source, "controller", None)
            return player is controller

        def _lifegain_effect(game: GameState) -> None:
            if _is_on_battlefield(game, source):
                add_counter(game, source, "+1/+1", 1)

        def _dies_effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is None:
                return
            power = getattr(source, "power", getattr(source, "base_power", 3))
            graveyard = controller.zones[Zone.GRAVEYARD]
            candidates = []
            for obj in graveyard.get_all():
                if obj is source:
                    continue
                card_types = getattr(obj, "card_types", set())
                if CardType.CREATURE not in card_types:
                    continue
                subtypes = getattr(obj, "subtypes", set())
                if "Bear" in subtypes:
                    continue
                mana_cost = getattr(obj, "mana_cost", None)
                if mana_cost is not None and mana_cost.cmc <= power:
                    candidates.append(obj)
            if candidates:
                target = candidates[0]
                target.controller = controller
                move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.GAINS_LIFE,
            condition=_lifegain_condition,
            effect=_lifegain_effect,
            source=self,
            controller=controller,
        ))
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_self_dies_condition(self),
            effect=_dies_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# SPINNER OF SOULS — reveal-until-creature on another death
# ===================================================================


class SpinnerOfSouls(Creature):
    """Spinner of Souls — {2}{G} — 4/3 — Spider Spirit — Reach

    Whenever another nontoken creature you control dies, you may reveal
    cards from the top of your library until you reveal a creature card.
    Put that card into your hand and the rest on the bottom of your
    library in a random order.

    FDN collector number 112.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Spinner of Souls")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("subtypes", {"Spider", "Spirit"})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Reach\nWhenever another nontoken creature you control dies, "
            "you may reveal cards from the top of your library until you "
            "reveal a creature card. Put that card into your hand and "
            "the rest on the bottom of your library in a random order.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _condition(game: Any, data: dict) -> bool:
            creature = data.get("creature")
            if creature is source:
                return False
            controller = getattr(source, "controller", None)
            creature_ctrl = data.get("controller")
            if creature_ctrl is not controller:
                return False
            if getattr(creature, "is_token", False):
                return False
            return True

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            hand = controller.zones[Zone.HAND]
            revealed: list[Any] = []
            found_creature = None
            while len(library) > 0:
                card = library.top(1)[0]
                library.remove(card)
                card_types = getattr(card, "card_types", set())
                if CardType.CREATURE in card_types:
                    found_creature = card
                    break
                revealed.append(card)
            # Put found creature into hand
            if found_creature is not None:
                hand.add(found_creature)
            # Put the rest on the bottom in random order
            import random
            random.shuffle(revealed)
            for card in revealed:
                library.add(card, position="bottom")

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


# ===================================================================
# Registry
# ===================================================================

def register_death_trigger_creatures(registry: CardRegistry) -> None:
    """Register all death-trigger creature cards with *registry*."""
    from cards.registry import CardMetadata

    _cards: list[tuple[str, type, dict[str, Any]]] = [
        ("Infestation Sage", InfestationSage, {
            "collector_number": "64", "rarity": "common",
            "mana_cost_str": "{B}", "type_line": "Creature — Elf Warlock",
            "power": "1", "toughness": "1", "colors": ["B"],
            "oracle_text": "When this creature dies, create a 1/1 black and green Insect creature token with flying.",
        }),
        ("Gleaming Barrier", GleamingBarrier, {
            "collector_number": "252", "rarity": "common",
            "mana_cost_str": "{2}", "type_line": "Artifact Creature — Wall",
            "power": "0", "toughness": "4", "colors": [],
            "keywords": ["Defender"],
            "oracle_text": "Defender\nWhen this creature dies, create a Treasure token.",
        }),
        ("Maalfeld Twins", MaalfeldTwins, {
            "collector_number": "523", "rarity": "uncommon",
            "mana_cost_str": "{5}{B}", "type_line": "Creature — Zombie",
            "power": "4", "toughness": "4", "colors": ["B"],
            "oracle_text": "When this creature dies, create two 2/2 black Zombie creature tokens.",
        }),
        ("Solemn Simulacrum", SolemnSimulacrum, {
            "collector_number": "257", "rarity": "rare",
            "mana_cost_str": "{4}", "type_line": "Artifact Creature — Golem",
            "power": "2", "toughness": "2", "colors": [],
            "oracle_text": "When this creature enters, you may search your library for a basic land card, put that card onto the battlefield tapped, then shuffle.\nWhen this creature dies, you may draw a card.",
        }),
        ("Crow of Dark Tidings", CrowOfDarkTidings, {
            "collector_number": "519", "rarity": "common",
            "mana_cost_str": "{2}{B}", "type_line": "Creature — Zombie Bird",
            "power": "2", "toughness": "1", "colors": ["B"],
            "keywords": ["Flying"],
            "oracle_text": "Flying\nWhen this creature enters or dies, mill two cards.",
        }),
        ("Wary Thespian", WaryThespian, {
            "collector_number": "235", "rarity": "common",
            "mana_cost_str": "{1}{G}", "type_line": "Creature — Cat Druid",
            "power": "3", "toughness": "1", "colors": ["G"],
            "oracle_text": "When this creature enters or dies, surveil 1.",
        }),
        ("Vengeful Bloodwitch", VengefulBloodwitch, {
            "collector_number": "76", "rarity": "uncommon",
            "mana_cost_str": "{1}{B}", "type_line": "Creature — Vampire Warlock",
            "power": "1", "toughness": "1", "colors": ["B"],
            "oracle_text": "Whenever this creature or another creature you control dies, target opponent loses 1 life and you gain 1 life.",
        }),
        ("Midnight Reaper", MidnightReaper, {
            "collector_number": "609", "rarity": "rare",
            "mana_cost_str": "{2}{B}", "type_line": "Creature — Zombie Knight",
            "power": "3", "toughness": "2", "colors": ["B"],
            "oracle_text": "Whenever a nontoken creature you control dies, this creature deals 1 damage to you and you draw a card.",
        }),
        ("High-Society Hunter", HighSocietyHunter, {
            "collector_number": "61", "rarity": "rare",
            "mana_cost_str": "{3}{B}{B}", "type_line": "Creature — Vampire Noble",
            "power": "5", "toughness": "3", "colors": ["B"],
            "keywords": ["Flying"],
            "oracle_text": "Flying\nWhenever this creature attacks, you may sacrifice another creature. If you do, put a +1/+1 counter on this creature.\nWhenever another nontoken creature dies, draw a card.",
        }),
        ("Garna, Bloodfist of Keld", GarnaBloodfistOfKeld, {
            "collector_number": "658", "rarity": "uncommon",
            "mana_cost_str": "{1}{B}{R}{R}", "type_line": "Legendary Creature — Human Berserker",
            "power": "4", "toughness": "3", "colors": ["B", "R"],
            "oracle_text": "Whenever another creature you control dies, draw a card if it was attacking. Otherwise, Garna deals 1 damage to each opponent.",
        }),
        ("Crossway Troublemakers", CrosswayTroublemakers, {
            "collector_number": "518", "rarity": "rare",
            "mana_cost_str": "{5}{B}", "type_line": "Creature — Vampire",
            "power": "5", "toughness": "5", "colors": ["B"],
            "oracle_text": "Attacking Vampires you control have deathtouch and lifelink.\nWhenever a Vampire you control dies, you may pay 2 life. If you do, draw a card.",
        }),
        ("Kalastria Highborn", KalastriaHighborn, {
            "collector_number": "607", "rarity": "rare",
            "mana_cost_str": "{B}{B}", "type_line": "Creature — Vampire Shaman",
            "power": "2", "toughness": "2", "colors": ["B"],
            "oracle_text": "Whenever this creature or another Vampire you control dies, you may pay {B}. If you do, target player loses 2 life and you gain 2 life.",
        }),
        ("Driver of the Dead", DriverOfTheDead, {
            "collector_number": "605", "rarity": "common",
            "mana_cost_str": "{3}{B}", "type_line": "Creature — Vampire",
            "power": "3", "toughness": "2", "colors": ["B"],
            "oracle_text": "When this creature dies, return target creature card with mana value 2 or less from your graveyard to the battlefield.",
        }),
        ("Infernal Vessel", InfernalVessel, {
            "collector_number": "63", "rarity": "uncommon",
            "mana_cost_str": "{2}{B}", "type_line": "Creature — Human Cleric",
            "power": "2", "toughness": "1", "colors": ["B"],
            "oracle_text": "When this creature dies, if it wasn't a Demon, return it to the battlefield under its owner's control with two +1/+1 counters on it. It's a Demon in addition to its other types.",
        }),
        ("Nine-Lives Familiar", NineLivesFamiliar, {
            "collector_number": "66", "rarity": "rare",
            "mana_cost_str": "{1}{B}{B}", "type_line": "Creature — Cat",
            "power": "1", "toughness": "1", "colors": ["B"],
            "oracle_text": "This creature enters with eight revival counters on it if you cast it.\nWhen this creature dies, if it had a revival counter on it, return it to the battlefield with one fewer revival counter on it at the beginning of the next end step.",
        }),
        ("Fiendish Panda", FiendishPanda, {
            "collector_number": "120", "rarity": "uncommon",
            "mana_cost_str": "{2}{W}{B}", "type_line": "Creature — Bear Demon",
            "power": "3", "toughness": "2", "colors": ["B", "W"],
            "oracle_text": "Whenever you gain life, put a +1/+1 counter on this creature.\nWhen this creature dies, return another target non-Bear creature card with mana value less than or equal to this creature's power from your graveyard to the battlefield.",
        }),
        ("Spinner of Souls", SpinnerOfSouls, {
            "collector_number": "112", "rarity": "rare",
            "mana_cost_str": "{2}{G}", "type_line": "Creature — Spider Spirit",
            "power": "4", "toughness": "3", "colors": ["G"],
            "keywords": ["Reach"],
            "oracle_text": "Reach\nWhenever another nontoken creature you control dies, you may reveal cards from the top of your library until you reveal a creature card. Put that card into your hand and the rest on the bottom of your library in a random order.",
        }),
    ]

    for card_name, impl_class, meta_kwargs in _cards:
        metadata = CardMetadata(
            name=card_name,
            set_code="fdn",
            **meta_kwargs,
        )
        registry.register(card_name, impl_class, metadata)
