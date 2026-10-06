"""Known-Best engine checks moved out of the Audited Engine Tests' test_stack.py:
they drive the engine directly or test its internals, in positions no
FDN card reaches through play, so they guard the Known-Best engine
without being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_36.card_impl import ElementalistAdept
from cards.fdn.fdn_151.card_impl import Aetherize
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_248.card_impl import ThousandYearStorm, ThousandYearStormAbility1
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_278.card_impl import Mountain
from engine.game_state import GameState
from engine.stack import StackObject
from test_interface import Decision, Phase, Side, Step, Zone, card, create_game, player
from test_utils import DeterministicPlayer

from silverquillm.table import appears, copied, life, moves, off_stack, on_stack, taps

MAIN = (Phase.PRECOMBAT_MAIN, 0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_game() -> GameState:
    """Create a 2-player GameState with intent-based DeterministicPlayers."""
    p1 = DeterministicPlayer("Alice", life=20)
    p2 = DeterministicPlayer("Bob", life=20)
    return GameState([p1, p2])


def _make_stack_object(
    game: GameState,
    *,
    label: str = "spell",
    on_resolve=None,
    is_mana_ability: bool = False,
) -> StackObject:
    """Create a StackObject controlled by the active player."""
    return StackObject(
        source=label,
        controller=game.active_player,
        on_resolve=on_resolve or (lambda _g: None),
        is_mana_ability=is_mana_ability,
    )


# ===========================================================================
# StackObject dataclass
# ===========================================================================


# ===========================================================================
# Stack data structure
# ===========================================================================


# ===========================================================================
# An empty stack: everyone passes and the step ends
# ===========================================================================


# ===========================================================================
# Resolving the stack: last in, first out
# ===========================================================================


# ===========================================================================
# Responses resolve before what they respond to
# ===========================================================================


# ===========================================================================
# Mana abilities — immediate resolution (flag verification)
# ===========================================================================


# ===========================================================================
# check_state_based_actions stub
# ===========================================================================


# ===========================================================================
# GameState integration — stack initialization
# ===========================================================================


# ===========================================================================
# Playing through a turn
# ===========================================================================


def _storm_copies_second_bolt(t, first, second, target, *, new_target=None):
    """Player 0, with Thousand-Year Storm, casts ``first`` at player 1 and lets
    it resolve, then casts ``second`` at ``target``: Storm copies it once,
    keeping its target or, with ``new_target``, choosing that one."""
    t.act(0, first, choices=[player(1)], then=[moves(first, Zone.STACK), on_stack(ThousandYearStormAbility1, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(ThousandYearStormAbility1)])
    t.pass_(0)
    t.pass_(1, then=[moves(first, Zone.GRAVEYARD), life(1, 18)])
    _second_bolt_copied(t, second, target, new_target, opponent=1)


def _second_bolt_copied(t, second, target, new_target, *, opponent):
    t.act(0, second, choices=[target], then=[moves(second, Zone.STACK), on_stack(ThousandYearStormAbility1, 0)])
    retarget = [Decision.no()] if new_target is None else [Decision.yes(), new_target]
    t.pass_(0, choices=retarget)
    t.pass_(opponent, then=[off_stack(ThousandYearStormAbility1), copied(BurstLightning, 0)], note="the second spell is copied")


def _attacking_adept_bounced_and_recast(t, first, second, adept, aetherize, mountains, islands, *, new_target=None, target=None):
    """On player 1's turn the Elementalist Adept attacks; player 0 copies a
    Burst Lightning aimed at it (or at ``target``, the copy choosing the
    Adept), and player 1 answers with Aetherize, returning the Adept to hand,
    and casts it again: a new object."""
    t.pass_to(Step.DECLARE_ATTACKERS, 1)
    t.act(1, adept, then=[taps(adept)])
    t.pass_(1)
    t.act(0, mountains[0], then=[taps(mountains[0])])
    t.act(0, first, choices=[player(1)], then=[moves(first, Zone.STACK), on_stack(ThousandYearStormAbility1, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(ThousandYearStormAbility1)])
    t.pass_(1)
    t.pass_(0, then=[moves(first, Zone.GRAVEYARD), life(1, 18)])
    t.pass_(1)
    t.act(0, mountains[1], then=[taps(mountains[1])])
    _second_bolt_copied(t, second, target or adept, new_target, opponent=1)
    for island in islands[:4]:
        t.act(1, island, then=[taps(island)])
    t.act(1, aetherize, then=[moves(aetherize, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(aetherize, Zone.GRAVEYARD), moves(adept, Zone.HAND)])
    for island in islands[4:]:
        t.act(1, island, then=[taps(island)])
    t.act(1, adept, then=[moves(adept, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(adept, Zone.BATTLEFIELD)], note="the Elementalist Adept is back as a new object")


def _combat_board(target=None):
    first, second, adept, aetherize = card(BurstLightning), card(BurstLightning), card(ElementalistAdept), card(Aetherize)
    mountains = [card(Mountain), card(Mountain)]
    islands = [card(Island) for _ in range(6)]
    game = create_game(
        Side(hand=[first, second], battlefield=[ThousandYearStorm, *mountains]),
        Side(hand=[aetherize], battlefield=[adept, *islands, *([target] if target else [])], library=[Plains]),
        start=(Step.BEGIN_COMBAT, 1),
    )
    return game, first, second, adept, aetherize, mountains, islands




class TestMoveSpellOffStack:
    """move_spell_off_stack is the single primitive through which every spell
    leaves the stack. Countering (default) removes exactly the given
    StackObject and puts an ordinary spell in its owner's graveyard; the cast's
    departure replacement (flashback -> exile, rule 702.34a) is honoured for
    resolution and countering alike; a card is never moved twice; and a
    fizzled counter never moves a re-cast card."""

    def _instant(self, owner, name="Zap", *, flashback=False):
        from engine.card import Instant
        from engine.types import ManaCost

        card = Instant(name=name, mana_cost=ManaCost.parse("{U}"), owner=owner)
        card.controller = owner
        if flashback:
            card.flashback_cost = ManaCost.parse("{2}{U}")
        return card

    def _cast(self, game, player, card, from_zone, mode=None):
        """Free-cast *card* and return its StackObject (the cast helper's own
        return value — the occurrence identity of this one cast)."""
        from engine.casting import cast_spell_free

        if mode is None:
            so = cast_spell_free(game, player, card, from_zone)
        else:
            so = cast_spell_free(game, player, card, from_zone, mode=mode)
        assert so is game.stack.peek()  # the just-pushed occurrence
        assert so.source is card
        return so




    def _countered_by_the_second_counterspell(self, t, think, refute, offer):
        """Player 1 answers Think Twice with Refute, then An Offer You Can't
        Refuse on top; the Offer counters it first (two Treasures for its
        controller), leaving Refute aimed at a spell that is gone."""
        t.act(0, think, then=[moves(think, Zone.STACK)])
        t.pass_(0)
        t.act(1, refute, choices=[think], then=[moves(refute, Zone.STACK)])
        t.act(1, offer, choices=[think], then=[moves(offer, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(offer, Zone.GRAVEYARD), moves(think, Zone.GRAVEYARD), appears(0), appears(0)])



    def test_resolution_does_not_move_twice_when_on_resolve_moved(self):
        """resolving=True duplicate-move guard: an on_resolve that already
        moved its card out of the stack zone leaves nothing for the departure
        primitive to move."""
        from engine.card import Instant
        from engine.stack import resolve_top_of_stack
        from engine.types import ManaCost, Zone
        from test_utils import create_game

        class _SelfBouncer(Instant):
            def on_resolve(self, game):
                from engine.zones import move_to_zone

                move_to_zone(game, self, Zone.STACK, Zone.HAND)

        game = create_game()
        p = game.players[0]
        card = _SelfBouncer(name="Boomerang Trick", mana_cost=ManaCost.parse("{U}"), owner=p)
        card.controller = p
        game.get_hand(p).add(card)
        self._cast(game, p, card, Zone.HAND)

        resolve_top_of_stack(game)
        assert sum(1 for o in game.get_hand(p).get_all() if o is card) == 1
        assert not game.get_graveyard(p).contains(card)
        assert not game.get_exile(p).contains(card)



