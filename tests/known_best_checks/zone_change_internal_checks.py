"""Known-Best engine checks moved out of the Audited Engine Tests' test_zone_change.py:
they drive the engine directly or test its internals, in positions no
FDN card reaches through play, so they guard the Known-Best engine
without being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_187.card_impl import Zombify
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_276.card_impl import Swamp
from cards.fdn.fdn_278.card_impl import Mountain
from engine.card import ActivatedAbility, Artifact, Creature
from engine.continuous_effects import (
    DURATION_END_OF_TURN,
    ContinuousEffect,
    Layer,
    SubLayer,
)
from engine.game import add_counter, gain_life, sacrifice
from engine.triggers import TriggerRegistration
from engine.types import Zone
from test_interface import Phase, Side, card, create_game
from test_utils import (
    behavioral_game,
    enter_permanent,
)

from table import Table, moves, taps


def _creature(name: str = "Test Creature", power: int = 1, toughness: int = 1) -> Creature:
    return Creature(name=name, base_power=power, base_toughness=toughness)


def _token(name: str = "Test Token") -> Creature:
    token = _creature(name)
    token.is_token = True
    return token


def _in_any_zone(game, obj) -> bool:
    return any(player.zones[zone].contains(obj) for player in game.players for zone in Zone)


def _with_two_plus_one_counters(game, player, card):
    enter_permanent(game, player, card)
    add_counter(game, card, "+1/+1", 2)
    return card






def _tap_and_cast(t, lands, spell, *, choices=(), then=()):
    """Player 0 taps ``lands`` and casts ``spell``, and both players pass."""
    for land in lands:
        t.act(0, land, then=[taps(land)])
    t.act(0, spell, choices=list(choices), then=[moves(spell, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=list(then))


def _bolt_then_zombify(lions):
    """Player 0, in their first main phase, kills their own Savannah Lions
    with Burst Lightning and returns it to the battlefield with Zombify."""
    bolt, zombify, mountain, swamp = card(BurstLightning), card(Zombify), card(Mountain), card(Swamp)
    plains = [card(Plains) for _ in range(3)]
    t = Table(create_game(
        Side(hand=[bolt, zombify], battlefield=[lions, mountain, swamp, *plains]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    ))
    _tap_and_cast(t, [mountain], bolt, choices=[lions],
                  then=[moves(bolt, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD)])
    _tap_and_cast(t, [swamp, *plains], zombify, choices=[lions],
                  then=[moves(zombify, Zone.GRAVEYARD), moves(lions, Zone.BATTLEFIELD)])
    return t
















def _pump(game, source, creatures, amount=3):
    """A resolved "creatures get +amount/+0 until end of turn" locked onto
    *creatures* (rule 611.2c)."""
    affected = list(creatures)

    def _apply(game) -> None:
        for creature in affected:
            creature.modified_power += amount

    return game.effect_manager.add(ContinuousEffect(
        source=source, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT,
        apply=_apply, duration=DURATION_END_OF_TURN, bound_to=affected,
    ))








def test_locked_effect_still_ends_at_cleanup():
    game = behavioral_game()
    p1 = game.players[0]
    creature = enter_permanent(game, p1, _creature("Pumped", 2, 2))
    _pump(game, _creature("Spell"), [creature])
    game.effect_manager.apply_all(game)
    assert creature.power == 5

    from engine.turn import cleanup_mechanical

    cleanup_mechanical(game)
    assert creature.power == 2


class _SacrificeForLife(Artifact):
    """Sacrifice this artifact: you gain 1 life."""

    def get_activated_abilities(self):
        def _cost(game, source) -> bool:
            sacrifice(game, source.controller, source)
            return True

        def _effect(game, controller) -> None:
            gain_life(game, controller, 1)

        return [ActivatedAbility(cost=_cost, effect=_effect)]




def _pending_power_reader(game, player, source):
    """Register an upkeep trigger on *source* that records "this creature's
    power" when it resolves, and fire it so it is pending."""
    from engine.events import BeginningOfUpkeepTriggeredEvent
    from engine.last_known import as_it_exists
    from engine.stack import battlefield_stint_id

    seen: list[int] = []

    def _effect(game, controller, stint) -> None:
        seen.append(as_it_exists(game, source, stint).power)

    game.trigger_manager.register(TriggerRegistration(
        event_type=BeginningOfUpkeepTriggeredEvent, condition=None, effect=_effect,
        source=source, controller=player,
        capture=lambda game, event, controller: battlefield_stint_id(game, source),
    ))
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    return seen




