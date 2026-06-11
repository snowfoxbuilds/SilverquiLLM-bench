"""Tests for Silverquill, the Disputant (sos_226)."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.types import Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state, _resolve_top_of_stack


class SimpleInstant(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "SimpleInstant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        pass


class BearCreature(Creature):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Bear")
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)


def test_flying_vigilance():
    """Silverquill has Flying and Vigilance."""
    sq = SilverquillTheDisputant()
    assert Keyword.FLYING in sq.keywords
    assert Keyword.VIGILANCE in sq.keywords


def test_casualty_copies_spell_when_creature_sacrificed():
    """Casting an instant with Silverquill on battlefield and sacrificing triggers a copy."""
    sq = SilverquillTheDisputant()
    game = create_game()
    p1 = game.players[0]

    bear = BearCreature()
    spell = SimpleInstant()

    set_board_state(game, 0, battlefield=[sq, bear], hand=[spell])
    sq.controller = p1
    sq.register_triggers(game)

    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0
    p1.mana_pool.add(ManaType.BLUE, 1)
    p1.mana_pool.add(ManaType.COLORLESS, 1)

    from engine.player import DeterministicPlayer
    if isinstance(p1, DeterministicPlayer):
        # For casualty: choose bear to sacrifice, say no to new targets
        p1._script.appendleft(False)  # no new targets
        p1._script.appendleft(bear)   # sacrifice this creature

    # Cast the instant (triggers E1 → Silverquill trigger)
    from engine.casting import cast_spell as _cast
    _cast(game, p1, spell)

    # Stack: [spell, casualty_trigger]  (trigger was pushed after E1 fired)
    # Resolve the trigger first (it's on top)
    _resolve_top_of_stack(game)

    # After full resolution, bear was sacrificed
    bf = game.get_battlefield(p1)
    assert bear not in bf.get_all()


def test_no_casualty_when_no_eligible_creature():
    """Without a creature with power >= 1, casualty trigger does nothing."""
    sq = SilverquillTheDisputant()
    game = create_game()
    p1 = game.players[0]

    spell = SimpleInstant()
    set_board_state(game, 0, battlefield=[sq], hand=[spell])
    sq.controller = p1
    sq.register_triggers(game)

    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0
    p1.mana_pool.add(ManaType.BLUE, 1)
    p1.mana_pool.add(ManaType.COLORLESS, 1)

    from engine.casting import cast_spell as _cast
    _cast(game, p1, spell)
    _resolve_top_of_stack(game)
    # No exception — trigger ran but found no eligible creatures


def test_casualty_copy_on_stack():
    """When creature is sacrificed, a copy of the spell is pushed onto the stack."""
    sq = SilverquillTheDisputant()
    game = create_game()
    p1 = game.players[0]

    bear = BearCreature()
    spell = SimpleInstant()

    set_board_state(game, 0, battlefield=[sq, bear], hand=[spell])
    sq.controller = p1
    sq.register_triggers(game)

    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0
    p1.mana_pool.add(ManaType.BLUE, 1)
    p1.mana_pool.add(ManaType.COLORLESS, 1)

    from engine.player import DeterministicPlayer
    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(False)  # no new targets
        p1._script.appendleft(bear)   # sacrifice bear

    from engine.casting import cast_spell as _cast
    _cast(game, p1, spell)

    # After casting, trigger is on stack above the spell
    # Resolve trigger → copy gets pushed → stack has [spell, copy]
    # Stack should have at least 2 items after trigger resolves with sacrifice
    from engine.state_based_actions import resolve_state_based_actions
    trigger_obj = game.stack.pop()  # casualty trigger
    trigger_obj.on_resolve(game)
    resolve_state_based_actions(game)

    # Stack should have the original spell + a copy
    assert len(game.stack) >= 2
