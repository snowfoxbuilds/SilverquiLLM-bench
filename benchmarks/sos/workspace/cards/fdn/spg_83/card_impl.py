"""Card implementation for Fiend Artisan."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Artifact, Creature, Enchantment, Instant, ManaAbility, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, DURATION_PERMANENT, Layer, SubLayer
from benchmarks.sos.workspace.engine.types import CardType, Color, HybridManaSymbol, Keyword, ManaCost, ManaType, Supertype, Zone
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.cards.registry import CardRegistry

def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False

def _get_mana_value(card: Any) -> int:
    """Return the mana value (converted mana cost) of a card."""
    mc = getattr(card, 'mana_cost', None)
    if mc is None:
        return 0
    total = getattr(mc, 'generic', 0)
    pips = getattr(mc, 'pips', {})
    for count in pips.values():
        total += count
    hybrid = getattr(mc, 'hybrid', [])
    total += len(hybrid)
    return total

class FiendArtisan(Creature):
    """Fiend Artisan — {B/G}{B/G} — Creature — Nightmare

    Fiend Artisan's power and toughness are each equal to the number of
    creature cards in your graveyard.

    {X}{B/G}, {T}, Sacrifice another creature: Search your library for
    a creature card with mana value X or less, put it onto the
    battlefield, then shuffle. Activate only as a sorcery.

    SPG collector number 83.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Fiend Artisan')
        kwargs.setdefault('mana_cost', ManaCost.parse('{B/G}{B/G}'))
        kwargs.setdefault('base_power', 0)
        kwargs.setdefault('base_toughness', 0)
        kwargs.setdefault('subtypes', {'Nightmare'})
        kwargs.setdefault('rules_text', "Fiend Artisan's power and toughness are each equal to the number of creature cards in your graveyard.\n{X}{B/G}, {T}, Sacrifice another creature: Search your library for a creature card with mana value X or less, put it onto the battlefield, then shuffle your library. Activate only as a sorcery.")
        super().__init__(**kwargs)

    def _graveyard_creature_count(self) -> int:
        """Return the number of creature cards in the controller's graveyard."""
        controller = self.controller or self.owner
        if controller is None:
            return 0
        graveyard = controller.zones[Zone.GRAVEYARD]
        count = 0
        for card in graveyard.get_all():
            if CardType.CREATURE in getattr(card, 'card_types', set()):
                count += 1
        return count

    @property
    def power(self) -> int:
        """P/T = number of creature cards in your graveyard (CDA)."""
        return self._graveyard_creature_count()

    @property
    def toughness(self) -> int:
        """P/T = number of creature cards in your graveyard (CDA)."""
        return self._graveyard_creature_count()

    def register_triggers(self, game: Any) -> None:
        """Register characteristic-defining ability as a continuous effect."""
        source = self

        def _apply(g: Any) -> None:
            if not _is_on_battlefield(g, source):
                return
            count = source._graveyard_creature_count()
            source.modified_power = count
            source.modified_toughness = count
        game.effect_manager.add(ContinuousEffect(source=source, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.CHARACTERISTIC_DEFINING, apply=_apply, duration=DURATION_PERMANENT))

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            """Pay {X}{B/G}, tap, sacrifice another creature.

            The X value is read from ``src._x_value`` (set by the game
            engine or test harness before calling the ability).
            """
            from benchmarks.sos.workspace.engine.casting import is_sorcery_speed
            controller = getattr(src, 'controller', None)
            if controller is None:
                return False
            if not is_sorcery_speed(game, controller):
                return False
            if getattr(src, 'is_tapped', False):
                return False
            bf = game.get_battlefield(controller)
            other_creatures = [c for c in bf.get_all() if CardType.CREATURE in getattr(c, 'card_types', set()) and c is not src]
            if not other_creatures:
                return False
            x_value = getattr(src, '_x_value', 0)
            hybrid_cost = ManaCost(generic=x_value, hybrid=[HybridManaSymbol(option_a=ManaType.BLACK, option_b=ManaType.GREEN)])
            if not controller.mana_pool.can_pay(hybrid_cost):
                return False
            controller.mana_pool.pay(hybrid_cost)
            src.is_tapped = True
            sac_target = getattr(src, '_sacrifice_target', None)
            if sac_target is None:
                sac_target = other_creatures[0]
            if bf.contains(sac_target):
                from benchmarks.sos.workspace.engine.zones import move_to_zone
                move_to_zone(game, sac_target, Zone.BATTLEFIELD, Zone.GRAVEYARD)
            return True

        def _effect(game: Any) -> None:
            controller = source.controller or source.owner
            if controller is None:
                return
            x_value = getattr(source, '_x_value', 0)
            library = controller.zones[Zone.LIBRARY]
            candidates = [c for c in library.get_all() if CardType.CREATURE in getattr(c, 'card_types', set()) and _get_mana_value(c) <= x_value]
            if candidates:
                chosen = candidates[0]
                if hasattr(controller, 'choose_card'):
                    try:
                        chosen = controller.choose_card(candidates, f'Search for creature with MV ≤ {x_value}')
                    except Exception:
                        chosen = candidates[0]
                library.remove(chosen)
                chosen.owner = chosen.owner or controller
                chosen.controller = controller
                from benchmarks.sos.workspace.engine.zones import move_to_zone
                game.get_battlefield(controller).add(chosen)
                if hasattr(chosen, 'register_triggers'):
                    chosen.register_triggers(game)
                game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=chosen, controller=controller))
            library.shuffle()
        return [ActivatedAbility(cost=_cost, effect=_effect, description='{X}{B/G}, {T}, Sacrifice another creature: Search your library for a creature card with mana value X or less, put it onto the battlefield, then shuffle. Activate only as a sorcery.')]
