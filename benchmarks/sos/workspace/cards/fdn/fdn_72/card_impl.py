"""Card implementation for Tinybones, Bauble Burglar."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Zone
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

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
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        from benchmarks.sos.workspace.engine.game import exile, add_counter
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

    def get_activated_abilities(self, game: 'GameState') -> list:
        """Tap ability: each opponent discards a card. Activate only as a sorcery."""
        source = self

        def _discard_effect(game: 'GameState') -> None:
            from benchmarks.sos.workspace.engine.game import discard, exile, add_counter
            controller = getattr(source, 'controller', None)
            if controller is None:
                return
            for player in game.players:
                if player is controller:
                    continue
                hand = game.get_hand(player)
                hand_cards = hand.get_all()
                if hand_cards:
                    try:
                        chosen = player.choose_card(hand_cards, 'discard a card')
                    except Exception:
                        chosen = hand_cards[0]
                    if chosen is not None:
                        discard(game, player, chosen)
                        gy = player.zones[Zone.GRAVEYARD]
                        if gy.contains(chosen):
                            exile(game, chosen)
                            if not hasattr(chosen, 'counters'):
                                chosen.counters = {}
                            chosen.counters['stash'] = chosen.counters.get('stash', 0) + 1

        def _cost(game: 'GameState', src=source) -> bool:
            """Pay {3}{B}, tap. Only at sorcery speed."""
            from benchmarks.sos.workspace.engine.casting import is_sorcery_speed
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
        ability = ActivatedAbility(cost=_cost, effect=_discard_effect, description='{3}{B}, {T}: Each opponent discards a card. Activate only as a sorcery.')
        ability.tap_cost = True
        return [ability]
