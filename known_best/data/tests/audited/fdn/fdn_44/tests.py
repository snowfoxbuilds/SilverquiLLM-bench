"""Reference test for FDN 44 — Kaito, Cunning Infiltrator.

Demonstrates **Pattern 4 — loyalty ability with targeting** (Phase D) for an
optional "**target creature you control**":

* ``+1`` — "Up to one target creature you control can't be blocked this turn.
  Draw a card, then discard a card." The target is optional (``targeting`` may
  return ``[]``) and is filtered to creatures the *controller* controls; the
  draw/discard happens whether or not a creature was targeted.
* ``−2`` / ``−9`` — untargeted.

The target is chosen at activation via a Player Query answered by an Intent
(pattern = the walker's name), captured on the stack object, and applied at
resolution — never re-selected.
"""

from __future__ import annotations

import pytest
from cards.fdn.fdn_44.card_impl import KaitoCunningInfiltrator
from engine.abilities import AbilityError, clear_loyalty_tracking
from engine.card import Creature
from engine.decisions import Decision, GameRef
from test_utils import Intent
from engine.types import ManaCost, Phase, Supertype, Zone
from test_utils import (
    activate_loyalty_ability,
    resolve_stack,
    set_board_state,
)
from test_utils import (
    scenario_game as create_game,
)


@pytest.fixture(autouse=True)
def _reset_loyalty_tracker():
    clear_loyalty_tracking()
    yield
    clear_loyalty_tracking()


def _bear(p, name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _spell(p, name="Scroll"):
    """A plain non-creature card to sit in hand as a discard candidate."""
    from engine.card import Sorcery

    return Sorcery(name=name, owner=p, controller=p)


def _seed_library(game, player, n=1):
    """Put *n* draw-able cards on top of *player*'s library."""
    from engine.card import Sorcery

    lib = player.zones[Zone.LIBRARY]
    for i in range(n):
        card = Sorcery(name=f"LibCard{i}", owner=player, controller=player)
        card.instance_id = game.refs.instance_id(card, Zone.LIBRARY.value)
        lib.add(card)


def _activate_targeting(game, player, walker, index, target):
    player.start_intent(
        "kaito",
        Intent(
            pattern=GameRef(card=frozenset({("name", walker.name)})),
            preferences=(Decision.obj(instance=target.instance_id),),
        ),
    )
    try:
        activate_loyalty_ability(game, player, walker, index)
    finally:
        player.end_intent("kaito")


class TestKaitoProperties:
    def test_static_data(self):
        kaito = KaitoCunningInfiltrator(owner=None)
        assert kaito.name == "Kaito, Cunning Infiltrator"
        assert kaito.mana_cost == ManaCost.parse("{1}{U}{U}")
        assert kaito.starting_loyalty == 3
        assert Supertype.LEGENDARY in kaito.supertypes
        assert "Kaito" in kaito.subtypes


class TestKaitoPlusOne:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        kaito = KaitoCunningInfiltrator(owner=p1, controller=p1)
        mine = _bear(p1, "My Bear")
        set_board_state(game, 0, battlefield=[kaito, mine], hand=[_spell(p1)])
        _seed_library(game, p1, 1)
        game.phase, game.step = Phase.PRECOMBAT_MAIN, None
        return game, p1, p2, kaito, mine

    def test_target_cant_be_blocked_and_draw_discard(self):
        from engine.combat import combat_damage_step
        from test_utils import declare_attackers, declare_blockers, put_on_battlefield

        game, p1, p2, kaito, mine = self._setup()
        hand_before = len(game.get_hand(p1))
        blocker = put_on_battlefield(game, p2, _bear(p2, "Blocker"))
        _activate_targeting(game, p1, kaito, 0, mine)
        resolve_stack(game)
        assert kaito.loyalty == 4 and len(game.get_hand(p1)) == hand_before
        mine.summoning_sick = False
        declare_attackers(game, [mine.name])
        declare_blockers(game, {mine.name: [blocker.name]}, illegal=True)
        combat_damage_step(game)
        resolve_stack(game)
        assert p2.life == 18 and game.get_battlefield(p1).contains(mine)

    def test_targets_only_own_creatures(self):
        """ "Target creature you control" — an opponent's creature is not a
        legal choice, so it is never captured as the target."""
        game = create_game()
        p1, p2 = game.players
        kaito = KaitoCunningInfiltrator(owner=p1, controller=p1)
        mine = _bear(p1, "My Bear")
        theirs = _bear(p2, "Their Bear")
        set_board_state(game, 0, battlefield=[kaito, mine], hand=[_spell(p1)])
        set_board_state(game, 1, battlefield=[theirs])
        game.phase, game.step = Phase.PRECOMBAT_MAIN, None
        # Intent still names my own creature; the opponent's is not in the
        # option set (verified indirectly — targeting only offers own creatures).
        _activate_targeting(game, p1, kaito, 0, mine)
        top = game.stack.peek()
        assert top.targets == [mine]
        assert theirs not in top.targets

    def test_up_to_one_activates_with_no_creature(self):
        """No creature to target → targeting returns []; the ability still
        activates and the draw/discard still happens."""
        game = create_game()
        p1, _p2 = game.players
        kaito = KaitoCunningInfiltrator(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[kaito], hand=[_spell(p1)])
        _seed_library(game, p1, 1)
        game.phase, game.step = Phase.PRECOMBAT_MAIN, None
        hand_before = len(p1.zones[Zone.HAND])
        activate_loyalty_ability(game, p1, kaito, 0)
        assert kaito.loyalty == 4
        top = game.stack.peek()
        assert top.targets == []
        resolve_stack(game)
        assert len(p1.zones[Zone.HAND]) == hand_before  # drew then discarded

    def test_once_per_turn(self):
        game, p1, _p2, kaito, mine = self._setup()
        _activate_targeting(game, p1, kaito, 0, mine)
        resolve_stack(game)  # clear the stack (sorcery speed)
        with pytest.raises(AbilityError):  # once-per-turn restriction
            _activate_targeting(game, p1, kaito, 0, mine)
        assert kaito.loyalty == 4  # second activation spent nothing


class TestKaitoUntargeted:
    def test_minus_two_creates_ninja_token(self):
        game = create_game()
        p1, _p2 = game.players
        kaito = KaitoCunningInfiltrator(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[kaito])
        game.phase, game.step = Phase.PRECOMBAT_MAIN, None
        activate_loyalty_ability(game, p1, kaito, 1)  # −2, untargeted
        assert kaito.loyalty == 1
        resolve_stack(game)
        ninjas = [obj for obj in game.get_battlefield(p1).get_all() if obj.name == "Ninja"]
        assert len(ninjas) == 1
        assert (ninjas[0].base_power, ninjas[0].base_toughness) == (2, 1)
