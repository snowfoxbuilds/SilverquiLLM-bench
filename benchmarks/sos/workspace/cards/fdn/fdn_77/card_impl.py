"""Card implementation for Zul Ashur, Lich Lord."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

class ZulAshurLichLord(Creature):
    """Zul Ashur, Lich Lord — {1}{B} — 2/2 — Legendary Zombie Warlock.

    Ward—Pay 2 life.
    {T}: You may cast target Zombie creature card from your graveyard
    this turn.

    FDN collector number 77.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Zul Ashur, Lich Lord')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{B}'))
        kwargs.setdefault('subtypes', {'Zombie', 'Warlock'})
        kwargs.setdefault('supertypes', {'Legendary'})
        kwargs.setdefault('keywords', Keyword.WARD)
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'Ward—Pay 2 life.\n{T}: You may cast target Zombie creature card from your graveyard this turn.')
        super().__init__(**kwargs)
        self._granted_castable: list[Any] = []

    def register_triggers(self, game: 'GameState') -> None:
        """Register end-of-turn cleanup to remove graveyard casting permission."""
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self

        def _cleanup_condition(game: Any, event: dict) -> bool:
            return True

        def _cleanup_effect(game: 'GameState') -> None:
            for card in source._granted_castable:
                if hasattr(card, '_castable_from_graveyard'):
                    del card._castable_from_graveyard
            source._granted_castable.clear()
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_cleanup_condition, effect=_cleanup_effect, source=self, controller=controller))

    def get_activated_abilities(self, game: 'GameState') -> list:
        """Tap ability: cast Zombie from graveyard this turn."""
        source = self

        def _tap_effect(game: 'GameState') -> None:
            controller = getattr(source, 'controller', None)
            if controller is None:
                return
            gy = controller.zones[Zone.GRAVEYARD]
            zombies = [c for c in gy.get_all() if CardType.CREATURE in getattr(c, 'card_types', set()) and 'Zombie' in getattr(c, 'subtypes', set())]
            if not zombies:
                return
            try:
                chosen = controller.choose_card(zombies, 'Zombie creature to cast from graveyard')
            except Exception:
                chosen = zombies[0] if zombies else None
            if chosen is not None:
                chosen._castable_from_graveyard = True
                source._granted_castable.append(chosen)
        ability = ActivatedAbility(cost=lambda game, src=self: not getattr(src, 'is_tapped', False), effect=_tap_effect, description='{T}: You may cast target Zombie creature card from your graveyard this turn.')
        ability.tap_cost = True
        return [ability]
