"""Card implementation for Kaito, Cunning Infiltrator."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature, LoyaltyAbility, Planeswalker
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from benchmarks.sos.workspace.engine.events import DealsDamageTriggeredEvent, SpellCastTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.engine.player import Player
    from benchmarks.sos.workspace.cards.registry import CardRegistry

class KaitoCunningInfiltrator(Planeswalker):
    """Kaito, Cunning Infiltrator — {1}{U}{U} — 3 loyalty.

    Whenever a creature you control deals combat damage to a player, put a
    loyalty counter on Kaito.
    +1: Up to one target creature you control can't be blocked this turn.
        Draw a card, then discard a card.
    −2: Create a 2/1 blue Ninja creature token.
    −9: You get an emblem with "Whenever a player casts a spell, you create
        a 2/1 blue Ninja creature token."
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Kaito, Cunning Infiltrator')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{U}{U}'))
        kwargs.setdefault('starting_loyalty', 3)
        kwargs.setdefault('supertypes', set())
        kwargs['supertypes'] = (kwargs.get('supertypes') or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault('subtypes', set())
        kwargs['subtypes'] = (kwargs.get('subtypes') or set()) | {'Kaito'}
        kwargs.setdefault('rules_text', 'Whenever a creature you control deals combat damage to a player, put a loyalty counter on Kaito.\n+1: Up to one target creature you control can\'t be blocked this turn. Draw a card, then discard a card.\n−2: Create a 2/1 blue Ninja creature token.\n−9: You get an emblem with "Whenever a player casts a spell, you create a 2/1 blue Ninja creature token."')
        super().__init__(**kwargs)

    def register_triggers(self, game: Any) -> None:
        """Register passive: combat damage to a player → loyalty counter."""
        from benchmarks.sos.workspace.engine.game import add_counter
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        pw = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _combat_damage_condition(game: Any, event: dict) -> bool:
            """Fire when a creature controlled by Kaito's controller deals damage to a player."""
            source = event.source
            target = event.target
            if not event.combat:
                return False
            if source is None or target is None:
                return False
            source_types = getattr(source, 'card_types', set())
            if CardType.CREATURE not in source_types:
                return False
            if getattr(source, 'controller', None) is not pw.controller:
                return False
            if not hasattr(target, 'life'):
                return False
            return True

        def _combat_damage_effect(game: Any) -> None:
            """Put a loyalty counter on Kaito."""
            add_counter(game, pw, 'loyalty', 1)
        game.trigger_manager.register(TriggerRegistration(event_type=DealsDamageTriggeredEvent, condition=_combat_damage_condition, effect=_combat_damage_effect, source=self, controller=controller))

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """Up to one target creature can't be blocked. Draw then discard."""
            from benchmarks.sos.workspace.engine.game import discard, draw_card
            target = getattr(pw, '_resolve_target', None)
            if target is not None:
                target._cant_be_blocked = True
            controller = pw.controller
            if controller is not None:
                drawn = draw_card(game, controller)
                hand = controller.zones[Zone.HAND]
                cards_in_hand = hand.get_all()
                if cards_in_hand:
                    card_to_discard = cards_in_hand[-1]
                    discard(game, controller, card_to_discard)

        def _minus2(game: Any) -> None:
            """Create a 2/1 blue Ninja creature token."""
            from benchmarks.sos.workspace.engine.game import create_token
            controller = pw.controller
            if controller is not None:
                token = Creature(name='Ninja', base_power=2, base_toughness=1, subtypes={'Ninja'})
                create_token(game, controller, token)

        def _minus9(game: Any) -> None:
            """Emblem — whenever a player casts a spell, create a 2/1 Ninja token."""
            from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
            from benchmarks.sos.workspace.engine.game import create_token
            controller = pw.controller
            if controller is None:
                return
            emblem = type('Emblem', (), {'name': 'Kaito Emblem'})()

            def _spell_cast_condition(game: Any, event: dict) -> bool:
                """Always fires when any player casts a spell."""
                return True

            def _spell_cast_effect(game: Any) -> None:
                """Create a 2/1 blue Ninja creature token."""
                token = Creature(name='Ninja', base_power=2, base_toughness=1, subtypes={'Ninja'})
                create_token(game, controller, token)
            game.trigger_manager.register(TriggerRegistration(event_type=SpellCastTriggeredEvent, condition=_spell_cast_condition, effect=_spell_cast_effect, source=emblem, controller=controller))
        return [LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Up to one target creature can't be blocked. Draw, then discard."), LoyaltyAbility(loyalty_cost=-2, effect=_minus2, description='−2: Create a 2/1 blue Ninja creature token.'), LoyaltyAbility(loyalty_cost=-9, effect=_minus9, description='−9: Emblem — whenever a player casts a spell, create 2/1 Ninja token.')]
