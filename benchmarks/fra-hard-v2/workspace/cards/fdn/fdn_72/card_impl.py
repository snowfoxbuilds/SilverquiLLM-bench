"""Card implementation for Tinybones, Bauble Burglar."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.card_queries import choose_object
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class TinybonesBaubleBurglarAbility1:
    text = 'Whenever an opponent discards a card, exile it from their graveyard with a stash counter on it.'


class TinybonesBaubleBurglarAbility2:
    text = "During your turn, you may play cards you don't own with stash counters on them from exile, and mana of any type can be spent to cast those spells."


class TinybonesBaubleBurglarAbility3:
    text = '{3}{B}, {T}: Each opponent discards a card. Activate only as a sorcery.'


# endregion Printed abilities


class TinybonesBaubleBurglar(Creature):
    """Tinybones, Bauble Burglar — {1}{B} — 1/3 — Legendary Skeleton Rogue.

    Whenever an opponent discards a card, exile it from their graveyard
    with a stash counter on it.
    During your turn, you may play cards you don't own with stash counters
    on them from exile, and mana of any type can be spent to cast those spells.
    {3}{B}, {T}: Each opponent discards a card. Activate only as a sorcery.

    FDN collector number 72.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Tinybones, Bauble Burglar')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{B}'))
        kwargs.setdefault('subtypes', {'Skeleton', 'Rogue'})
        kwargs.setdefault('supertypes', {'Legendary'})
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 3)
        kwargs.setdefault('rules_text', "Whenever an opponent discards a card, exile it from their graveyard with a stash counter on it.\nDuring your turn, you may play cards you don't own with stash counters on them from exile, and mana of any type can be spent to cast those spells.\n{3}{B}, {T}: Each opponent discards a card. Activate only as a sorcery.")
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register discard exile trigger.

        Whenever an opponent discards a card, exile it from their graveyard
        with a stash counter on it.
        """
        from engine.events import DiscardsCardTriggeredEvent
        from engine.game import add_counter, exile
        from engine.stack import object_stint_id, same_stint
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _opponent_discards(game: 'GameState', event: Any) -> bool:
            ctrl = getattr(source, 'controller', None)
            return event.player is not None and event.player is not ctrl

        def _discarded(game: 'GameState', event: Any, controller: Any) -> tuple[Any, Any]:
            # "It" is the discarded card as it is now, in its owner's graveyard.
            return event.card, object_stint_id(game, event.card)

        def _stash(game: 'GameState', controller: Any, discarded: tuple[Any, Any]) -> None:
            card, stint = discarded
            if not same_stint(game, card, stint):
                return
            exile(game, card)
            add_counter(game, card, 'stash', 1)

        game.trigger_manager.register(TriggerRegistration(
            event_type=DiscardsCardTriggeredEvent, condition=_opponent_discards, effect=_stash,
            source=self, controller=controller, capture=_discarded, printed=TinybonesBaubleBurglarAbility1))

    def get_activated_abilities(self, game: 'GameState') -> list:
        """Tap ability: each opponent discards a card. Activate only as a sorcery."""
        source = self

        def _discard_effect(game: 'GameState', controller: Any) -> None:
            from engine.game import discard
            if controller is None:
                return
            for player in game.players:
                if player is controller:
                    continue
                hand = game.get_hand(player)
                hand_cards = hand.get_all()
                if hand_cards:
                    chosen = choose_object(game, player, hand_cards, 'discard a card', source_card=source)
                    if chosen is not None:
                        discard(game, player, chosen)

        def _cost(game: 'GameState', src=source) -> bool:
            """Pay {3}{B}, tap. Only at sorcery speed."""
            from engine.casting import is_sorcery_speed
            controller = getattr(src, 'controller', None)
            if controller is None:
                return False
            if getattr(src, 'is_tapped', False):
                return False
            if not is_sorcery_speed(game, controller):
                return False
            cost = ManaCost.parse('{3}{B}')
            if not controller.mana_pool.can_pay(cost):
                return False
            controller.mana_pool.pay(cost)
            return True
        ability = ActivatedAbility(cost=_cost, effect=_discard_effect, description='{3}{B}, {T}: Each opponent discards a card. Activate only as a sorcery.', printed=TinybonesBaubleBurglarAbility3)
        ability.tap_cost = True
        return [ability]
