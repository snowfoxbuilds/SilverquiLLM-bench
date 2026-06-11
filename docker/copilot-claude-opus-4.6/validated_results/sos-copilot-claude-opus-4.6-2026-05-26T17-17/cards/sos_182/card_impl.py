"""Card implementation for Conciliator's Duelist."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent, EndStepTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ConciliatorsDuelist(Creature):
    """Conciliator's Duelist — {W}{W}{B}{B} — 4/3 Creature — Kor Warlock.

    When this creature enters, draw a card. Each player loses 1 life.
    Repartee — Whenever you cast an instant or sorcery spell that targets a creature,
    exile up to one target creature. Return that card to the battlefield under its
    owner's control at the beginning of the next end step.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Conciliator's Duelist")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}{W}{B}{B}"))
        kwargs.setdefault("subtypes", {"Kor", "Warlock"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: draw a card, each player loses 1 life."""
        controller = self.controller
        # Move to battlefield
        bf = game.get_battlefield(controller)
        bf.add(self)
        # Register triggers
        self.register_triggers(game)
        # ETB effect
        from engine.game import draw_card
        draw_card(game, controller)
        for player in game.players:
            player.life -= 1

    def register_triggers(self, game: "GameState") -> None:
        """Register repartee trigger — handled via on_spell_cast."""
        pass

    def on_spell_cast(self, game: "GameState", event: Any) -> None:
        """Repartee: When controller casts instant/sorcery targeting a creature,
        exile up to one target creature."""
        spell = getattr(event, "spell", None) or getattr(event, "card", None)
        if spell is None:
            return

        # Must be controller's spell
        caster = getattr(event, "player", None) or getattr(event, "controller", None)
        if caster is not self.controller:
            return

        # Must be instant or sorcery
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return

        # Must target a creature
        targets = getattr(event, "targets", None) or []
        targets_creature = False
        for t in targets:
            if CardType.CREATURE in getattr(t, "card_types", set()):
                targets_creature = True
                break

        if not targets_creature:
            return

        # Exile up to one target creature (find a creature on opponent's battlefield
        # that isn't the spell's target, or any valid creature)
        controller = self.controller
        exile_target = None
        for player in game.players:
            if player is controller:
                continue
            bf = game.get_battlefield(player)
            for obj in bf.get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    if obj not in targets:
                        exile_target = obj
                        break
            if exile_target is not None:
                break

        # If no non-target creature found, try any creature on opponent's battlefield
        if exile_target is None:
            for player in game.players:
                if player is controller:
                    continue
                bf = game.get_battlefield(player)
                for obj in bf.get_all():
                    if CardType.CREATURE in getattr(obj, "card_types", set()):
                        exile_target = obj
                        break
                if exile_target is not None:
                    break

        if exile_target is None:
            return

        # Exile the creature
        owner = getattr(exile_target, "owner", None)
        exile_controller = getattr(exile_target, "controller", None)
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(exile_target):
                bf.remove(exile_target)
                break

        # Put in owner's exile
        if owner:
            owner.zones[Zone.EXILE].add(exile_target)
        else:
            game.players[0].zones[Zone.EXILE].add(exile_target)

        # Register delayed trigger to return at next end step
        exiled_card = exile_target
        card_owner = owner or exile_controller

        def _end_step_condition(g: "GameState", evt: Any) -> bool:
            return True

        def _end_step_effect(g: "GameState") -> None:
            # Return to battlefield under owner's control
            if card_owner:
                exile_z = card_owner.zones[Zone.EXILE]
                if exile_z.contains(exiled_card):
                    exile_z.remove(exiled_card)
                    exiled_card.controller = card_owner
                    bf = g.get_battlefield(card_owner)
                    bf.add(exiled_card)
            # Unregister this trigger after firing
            g.trigger_manager.unregister(exiled_card)

        game.trigger_manager.register(TriggerRegistration(
            event_type=EndStepTriggeredEvent,
            condition=_end_step_condition,
            effect=_end_step_effect,
            source=exiled_card,
            controller=card_owner or game.players[0],
        ))
