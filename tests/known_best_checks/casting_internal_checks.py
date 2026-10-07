"""Known-Best engine checks moved out of the Audited Engine Tests' test_casting.py:
they drive the engine directly or test its internals, in positions no
FDN card reaches through play, so they guard the Known-Best engine
without being graded against candidates (ADR-018)."""

from __future__ import annotations

import pytest
from cards.fdn.fdn_194.card_impl import EtaliPrimalStorm, EtaliPrimalStormAbility1
from cards.fdn.fdn_272.card_impl import Plains
from engine.card import (
    CardImpl,
    Creature,
    Instant,
)
from engine.casting import (
    cast_spell,
)
from engine.decisions import Decision
from engine.game_state import GameState
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_interface import Side, card, create_game
from test_utils import DeterministicPlayer

from table import Table, moves, off_stack, on_stack, taps

R, W, U = ManaType.RED, ManaType.WHITE, ManaType.BLUE
NO_NEW_TARGETS = Decision.no()


def _table(p0: Side | None = None, p1: Side | None = None, *, start=(Phase.PRECOMBAT_MAIN, 0)) -> Table:
    """A table for a game built at ``start``, player 0's precombat main phase
    by default."""
    return Table(create_game(p0 or Side(), p1 or Side(), start=start))


def _cast(t: Table, seat: int, spell, *choices, then=(), note: str = "") -> None:
    """``seat`` casts ``spell``, answering its questions with ``choices``."""
    t.act(seat, spell, choices=choices, then=[moves(spell, Zone.STACK), *then], note=note)


def _resolve(t: Table, *, then=(), choices=(), chooser: int | None = None, note: str = "") -> None:
    """Both players pass in turn, starting with the player asked, and the top
    of the stack resolves with ``then``; ``choices`` answer the questions the
    resolution asks ``chooser`` (by default the player who passes first)."""
    first = t.asked
    chooser = first if chooser is None else chooser
    t.pass_(first, choices=choices if chooser == first else ())
    t.pass_(1 - first, choices=choices if chooser != first else (), then=then, note=note)


def _make_game(
    *,
    phase: Phase = Phase.PRECOMBAT_MAIN,
    step: Step | None = None,
) -> GameState:
    """Create a minimal 2-player GameState at the specified phase/step."""
    p1 = DeterministicPlayer("Alice")
    p2 = DeterministicPlayer("Bob")
    game = GameState([p1, p2])
    game.phase = phase
    game.step = step
    return game


def _add_to_hand(game: GameState, player_idx: int, card: CardImpl) -> None:
    """Put *card* into the player's hand."""
    game.get_hand(game.players[player_idx]).add(card)


def _add_mana(player: DeterministicPlayer, mana_type: ManaType, amount: int) -> None:
    """Shortcut to add mana to a player's pool."""
    player.mana_pool.add(mana_type, amount)



# ---------------------------------------------------------------------------
# Timing — sorcery speed: active player, main phase, empty stack (307.1)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Timing helper tests — can_cast_at_instant_speed
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Casting — hand → stack → resolution → destination zone (601.2a, 608.3)
# ---------------------------------------------------------------------------







# ---------------------------------------------------------------------------
# Casting — timing (307.1, 302.1)
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
# Casting — paying the mana cost (601.2g-h)
# ---------------------------------------------------------------------------

class TestCastSpellManaPayment:
    """A spell is cast only when its mana cost can be paid, and paying it
    spends exactly that mana."""






    def test_zero_cost_spell_requires_no_mana(self):
        """A zero-cost spell can be cast with an empty pool."""
        game = _make_game()
        player = game.players[0]
        card = Instant(name="Pact", mana_cost=ManaCost())
        _add_to_hand(game, 0, card)
        # No mana added — pool is empty

        cast_spell(game, player, card)
        assert not game.stack.is_empty()



# ---------------------------------------------------------------------------
# Casting — card hooks
# ---------------------------------------------------------------------------

class TestCastSpellHooks:
    """A card's ``on_cast`` runs as it is cast, and a spell's effect happens
    only as it resolves."""

    def test_on_cast_callback_is_called(self):
        on_cast_log: list[str] = []

        class TrackedCreature(Creature):
            def on_cast(self, game: GameState) -> None:
                on_cast_log.append("on_cast")

        game = _make_game()
        player = game.players[0]
        card = TrackedCreature(
            name="Tracked",
            mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
            base_power=1, base_toughness=1,
        )
        _add_to_hand(game, 0, card)
        _add_mana(player, ManaType.GREEN, 1)

        cast_spell(game, player, card)
        assert on_cast_log == ["on_cast"]


    def test_on_cast_called_before_push_to_stack(self):
        """on_cast fires during cast_spell, before the StackObject is pushed."""
        stack_was_empty_during_on_cast: list[bool] = []

        class InspectorCreature(Creature):
            def on_cast(self, game: GameState) -> None:
                # At on_cast time the stack should still be empty
                # (StackObject push happens after on_cast)
                stack_was_empty_during_on_cast.append(game.stack.is_empty())

        game = _make_game()
        player = game.players[0]
        card = InspectorCreature(
            name="Inspector",
            mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
            base_power=1, base_toughness=1,
        )
        _add_to_hand(game, 0, card)
        _add_mana(player, ManaType.GREEN, 1)

        cast_spell(game, player, card)
        assert stack_was_empty_during_on_cast == [True]



# ---------------------------------------------------------------------------
# Casting — what can be cast at all
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Playing a land — a special action (305.1-305.3, 116.2a)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Permanent type detection
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Resolution — every permanent spell enters the battlefield (608.3)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# The stack — last in, first out, and targets chosen as a spell is cast
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Optional targets — "up to N target X" (115.1, 601.2c)
# ---------------------------------------------------------------------------






# ---------------------------------------------------------------------------
# Etali, Primal Storm — casting a spell without paying its mana cost
# ---------------------------------------------------------------------------

def _etali_attacks(spell, *, p0=(), p1=(), p0_hand=(), p1_hand=()):
    """Turn 1: player 0's Etali, Primal Storm attacks with ``spell`` on top of
    player 0's library and a Plains on top of player 1's; ``p0`` and ``p1``
    are more of each player's battlefield, ``p0_hand`` and ``p1_hand`` their
    hands. Returns the table, at the attack trigger's resolution, and player
    1's Plains."""
    etali, top = card(EtaliPrimalStorm), card(Plains)
    t = _table(
        Side(hand=list(p0_hand), battlefield=[etali, *p0], library=[spell, card(Plains)]),
        Side(hand=list(p1_hand), battlefield=list(p1), library=[top, card(Plains)]),
        start=(Step.BEGIN_COMBAT, 0),
    )
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, etali, then=[taps(etali), on_stack(EtaliPrimalStormAbility1, 0)])
    return t, top


def _etali_resolves(t, spell, top, *choices, then=(), note: str = ""):
    """Etali's trigger resolves: it exiles both top cards and player 0 casts
    ``spell`` without paying its mana cost, answering ``choices``."""
    _resolve(
        t,
        choices=[Decision.yes(), *choices],
        then=[
            off_stack(EtaliPrimalStormAbility1),
            moves(spell, Zone.EXILE),
            moves(top, Zone.EXILE),
            moves(spell, Zone.STACK),
            *then,
        ],
        note=note,
    )




# ---------------------------------------------------------------------------
# Spell-cast history — authoritative per-player, per-turn record
# ---------------------------------------------------------------------------







# ---------------------------------------------------------------------------
# Flashback — cast from the graveyard, then exiled (702.34a)
# ---------------------------------------------------------------------------

class TestFlashbackDisposition:
    """Think Twice ({1}{U} instant: draw a card; flashback {2}{U}) is cast
    from its owner's graveyard by flashback and exiled as it leaves the stack;
    cast any other way it goes to the graveyard as usual."""

    def _flashback_instant(self, player):
        card = Instant(name="Recall", mana_cost=ManaCost.parse("{1}{U}"), owner=player)
        card.controller = player
        card.flashback_cost = ManaCost.parse("{2}{U}")
        return card


    def test_flashback_capable_graveyard_cast_without_mode_keeps_graveyard(self):
        """The mode is never inferred: the SAME flashback-capable card,
        free-cast from the graveyard without selecting flashback (a
        Underworld-Breach-style graveyard cast), is NOT exiled."""
        from engine.casting import cast_spell_free
        from engine.stack import resolve_top_of_stack
        from engine.types import Zone

        game = _make_game()
        p = game.players[0]
        card = self._flashback_instant(p)
        game.get_graveyard(p).add(card)

        cast_spell_free(game, p, card, Zone.GRAVEYARD)
        (so,) = [s for s in game.stack._items if s.source is card]
        assert so.departure_zone is None

        resolve_top_of_stack(game)
        assert game.get_graveyard(p).contains(card)
        assert not game.get_exile(p).contains(card)

    def test_non_flashback_free_cast_keeps_graveyard(self):
        """A card with no flashback cost, free-cast from the graveyard, keeps the
        default graveyard disposition (no silent exile)."""
        from engine.casting import cast_spell_free
        from engine.stack import resolve_top_of_stack
        from engine.types import Zone

        game = _make_game()
        p = game.players[0]
        card = Instant(name="Plain", mana_cost=ManaCost.parse("{U}"), owner=p)
        card.controller = p
        game.get_graveyard(p).add(card)

        cast_spell_free(game, p, card, Zone.GRAVEYARD)
        (so,) = [s for s in game.stack._items if s.source is card]
        assert so.departure_zone is None

        resolve_top_of_stack(game)
        assert game.get_graveyard(p).contains(card)
        assert not game.get_exile(p).contains(card)


    # -- rejected mode claims are ATOMIC: every check runs before any mutation,
    #    so controller, owner, zones, stack, cast history, and target state are
    #    byte-for-byte what they were. Each negative test snapshots that state
    #    before the claim and asserts it unchanged after the CastingError.

    @staticmethod
    def _observable_state(game, card):
        """Snapshot everything a rejected flashback claim must leave untouched."""
        from engine.types import Zone

        return {
            "controller": card.controller,
            "owner": card.owner,
            "zones": [
                (i, zone.name, tuple(id(o) for o in player.zones[zone].get_all()))
                for i, player in enumerate(game.players)
                for zone in Zone
                if zone in player.zones
            ],
            "stack": tuple(id(so) for so in game.stack._items),
            "cast_history": [
                (
                    tuple(id(s) for s in player._instant_sorcery_casts),
                    player._instant_sorcery_cast_turn,
                )
                for player in game.players
            ],
            "chosen_targets": getattr(card, "chosen_targets", None),
            "is_tapped": getattr(card, "is_tapped", None),
        }

    def _assert_rejected_claim_untouched(self, game, player, card, from_zone):
        """The FLASHBACK claim raises CastingError and mutates nothing."""
        from engine.casting import CastingError, CastMode, cast_spell_free

        before = self._observable_state(game, card)
        with pytest.raises(CastingError):
            cast_spell_free(game, player, card, from_zone, mode=CastMode.FLASHBACK)
        assert self._observable_state(game, card) == before





    def test_flashback_mode_wrong_ownership_rejected(self):
        """Flashback is ownership-compatible: a card OWNED by another player is
        not flashback-castable, even from a graveyard the caster can reach
        (rule 702.34a casts from its owner's graveyard). Rejected atomically."""
        from engine.types import Zone

        game = _make_game()
        p1, p2 = game.players
        card = self._flashback_instant(p2)  # owned (and controlled) by p2
        game.get_graveyard(p1).add(card)  # misplaced into p1's graveyard

        self._assert_rejected_claim_untouched(game, p1, card, Zone.GRAVEYARD)
        assert game.get_graveyard(p1).contains(card)
        assert card.owner is p2
        assert card.controller is p2



# ---------------------------------------------------------------------------
# Targeting a spell — the spell on the stack, not its card (115.1, 608.2b)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Cast triggers — "whenever you cast" (601.2i, 603.2)
# ---------------------------------------------------------------------------

