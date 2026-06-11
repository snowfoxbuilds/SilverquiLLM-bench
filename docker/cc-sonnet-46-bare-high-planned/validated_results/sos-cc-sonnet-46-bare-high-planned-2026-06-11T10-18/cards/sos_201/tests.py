"""Tests for Lorehold, the Historian (sos_201)."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import (
    advance_to_phase,
    create_game,
    set_board_state,
    _resolve_top_of_stack,
)


class SmallInstant(Instant):
    def __init__(self, name="SmallInstant", mv=1, **kwargs):
        kwargs.setdefault("name", name)
        kwargs.setdefault("mana_cost", ManaCost(generic=mv))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        pass


class SmallSorcery(Sorcery):
    def __init__(self, name="SmallSorcery", mv=1, **kwargs):
        kwargs.setdefault("name", name)
        kwargs.setdefault("mana_cost", ManaCost(generic=mv))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        pass


def test_flying_and_haste():
    """Lorehold has Flying and Haste."""
    card = LoreholdTheHistorian()
    assert Keyword.FLYING in card.keywords
    assert Keyword.HASTE in card.keywords


def test_miracle_casts_instant_on_draw():
    """Drawing an instant when Lorehold is on battlefield offers miracle {2} cast."""
    from engine.game import draw_card
    from engine.player import DeterministicPlayer

    game = create_game()
    p1 = game.players[0]

    lorehold = LoreholdTheHistorian()
    instant = SmallInstant(mv=5, name="BigInstant")  # normally costs {5}
    instant.owner = p1
    instant.controller = p1

    # Put lorehold on battlefield and instant in library.
    set_board_state(game, 0, battlefield=[lorehold])
    lorehold.controller = p1
    lorehold.register_triggers(game)

    game.get_library(p1).add(instant)

    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0

    # Player says yes to miracle, has {2} available.
    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(True)  # yes, cast with miracle

    p1.mana_pool.add(ManaType.COLORLESS, 2)

    draw_card(game, p1)

    # Trigger should have fired: instant was cast via miracle.
    # Resolve the spell on the stack.
    if not game.stack.is_empty():
        _resolve_top_of_stack(game)

    # Instant should be in graveyard (was cast and resolved), not in hand.
    hand = game.get_hand(p1).get_all()
    assert instant not in hand


def test_miracle_not_offered_for_creature():
    """Miracle offer is not made for non-instant/sorcery cards."""
    from engine.game import draw_card
    from engine.player import DeterministicPlayer

    game = create_game()
    p1 = game.players[0]

    lorehold = LoreholdTheHistorian()
    creature = Creature(
        name="TestCreature", base_power=2, base_toughness=2,
        mana_cost=ManaCost(generic=3)
    )
    creature.owner = p1
    creature.controller = p1

    set_board_state(game, 0, battlefield=[lorehold])
    lorehold.controller = p1
    lorehold.register_triggers(game)

    game.get_library(p1).add(creature)

    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0

    p1.mana_pool.add(ManaType.COLORLESS, 2)

    draw_card(game, p1)
    # Resolve the draw trigger (harmless for non-instant/sorcery cards).
    if not game.stack.is_empty():
        _resolve_top_of_stack(game)
    # No miracle cast — creature should still be in hand, stack empty.
    assert game.stack.is_empty()
    assert creature in game.get_hand(p1).get_all()


def test_miracle_only_first_draw():
    """Miracle is only offered on the first draw this turn, not subsequent draws."""
    from engine.game import draw_card
    from engine.player import DeterministicPlayer

    game = create_game()
    p1 = game.players[0]

    lorehold = LoreholdTheHistorian()
    instant1 = SmallInstant(name="Instant1", mv=5)
    instant2 = SmallInstant(name="Instant2", mv=5)
    for c in [instant1, instant2]:
        c.owner = p1
        c.controller = p1
        game.get_library(p1).add(c)

    set_board_state(game, 0, battlefield=[lorehold])
    lorehold.controller = p1
    lorehold.register_triggers(game)

    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0
    p1.mana_pool.add(ManaType.COLORLESS, 4)

    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(False)  # decline miracle on first draw

    draw_card(game, p1)  # first draw — miracle offered, declined

    # Second draw should NOT offer miracle again this turn.
    colorless_before = p1.mana_pool.get(ManaType.COLORLESS)
    draw_card(game, p1)  # second draw — no offer
    # Mana should be unchanged (no miracle payment).
    assert p1.mana_pool.get(ManaType.COLORLESS) == colorless_before


def test_opponent_upkeep_loot():
    """At opponent's upkeep, Lorehold controller may discard-then-draw."""
    from engine.events import BeginningOfUpkeepTriggeredEvent
    from engine.player import DeterministicPlayer

    game = create_game()
    p1 = game.players[0]
    p2 = game.players[1]

    lorehold = LoreholdTheHistorian()
    discard_card = SmallInstant(name="Fodder")
    draw_card_in_lib = SmallSorcery(name="Prize")

    for c in [discard_card]:
        c.owner = p1
        c.controller = p1

    draw_card_in_lib.owner = p1
    draw_card_in_lib.controller = p1

    set_board_state(game, 0, battlefield=[lorehold], hand=[discard_card])
    lorehold.controller = p1
    lorehold.register_triggers(game)
    game.get_library(p1).add(draw_card_in_lib)

    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(discard_card)  # choose card to discard
        p1._script.appendleft(True)          # yes, loot

    # Simulate opponent's upkeep.
    game.active_player_index = 1
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    _resolve_top_of_stack(game)

    # Fodder should be in graveyard, Prize in hand.
    assert discard_card in game.get_graveyard(p1).get_all()
    assert draw_card_in_lib in game.get_hand(p1).get_all()
