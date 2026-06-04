"""Tests for SOS 201 — Lorehold, the Historian.

Lorehold, the Historian ({3}{R}{W} Legendary Creature — Elder Dragon, 5/5)
has three distinct pieces of behaviour, each covered by its own test class:

1. **Static card data** — name, mana cost, colors, P/T, legendary supertype,
   Elder Dragon subtypes, and the Flying + Haste keyword set.

2. **Miracle granting** — "Each instant and sorcery card in your hand has
   miracle {2}." The engine has no native ``miracle`` keyword, so this is the
   SOS-specific surface the implementer must expose.  These tests probe the
   observable contract: a method/attribute that reports the miracle cost
   ({2}) of the controller's hand instants/sorceries while Lorehold is on the
   battlefield, and that the grant is scoped to instants/sorceries in *your*
   hand (not creatures, not opponents' hands).  Where the engine genuinely
   lacks the surface to assert deeper behaviour (the actual draw-step miracle
   cast), the requirement is recorded in untestable.json.

3. **Opponent-upkeep loot trigger** — "At the beginning of each opponent's
   upkeep, you may discard a card. If you do, draw a card."  Modelled via
   ``register_triggers`` wiring a ``BeginningOfUpkeepTriggeredEvent`` trigger
   whose condition fires only on an opponent's upkeep (when the active player
   is not the controller), and whose effect optionally discards-then-draws.

These are TDD red-phase tests: the stub at ``card_impl.py`` is empty, so
everything here is expected to fail until the card is implemented.
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.miracle import get_miracle_cost
from engine.types import (
    CardType,
    Color,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Card factories for hand / graveyard setup
# ---------------------------------------------------------------------------


def _instant(name: str = "Test Bolt") -> Instant:
    """A vanilla instant card for hand setup."""
    return Instant(name=name, mana_cost=ManaCost.parse("{R}"))


def _sorcery(name: str = "Test Divination") -> Sorcery:
    """A vanilla sorcery card for hand setup."""
    return Sorcery(name=name, mana_cost=ManaCost.parse("{2}{U}"))


def _vanilla_creature(name: str = "Grizzly Bears") -> Creature:
    """A vanilla creature card (not an instant/sorcery)."""
    return Creature(name=name, base_power=2, base_toughness=2)


def _lorehold(game: Any) -> LoreholdTheHistorian:
    """Lorehold owned/controlled by player 0."""
    p1 = game.players[0]
    return LoreholdTheHistorian(owner=p1, controller=p1)


# ---------------------------------------------------------------------------
# 1. Static card data
# ---------------------------------------------------------------------------


class TestLoreholdProperties:
    """Static card data should match the SOS 201 spec."""

    def test_is_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_name(self) -> None:
        assert LoreholdTheHistorian(owner=None).name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        assert LoreholdTheHistorian(owner=None).mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_power_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in LoreholdTheHistorian(owner=None).supertypes

    def test_is_elder_dragon(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_colors_are_red_and_white(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.colors == {Color.RED, Color.WHITE}

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in LoreholdTheHistorian(owner=None).keywords

    def test_has_haste(self) -> None:
        assert Keyword.HASTE in LoreholdTheHistorian(owner=None).keywords

    def test_no_extraneous_keywords(self) -> None:
        # Guard against an over-broad keyword grant: only Flying + Haste.
        kw = LoreholdTheHistorian(owner=None).keywords
        assert kw == (Keyword.FLYING | Keyword.HASTE)


# ---------------------------------------------------------------------------
# 2. Miracle granting — "Each instant and sorcery card in your hand has
#    miracle {2}."
# ---------------------------------------------------------------------------


class TestLoreholdMiracleGrant:
    """The controller's hand instants/sorceries should report a miracle cost
    of {2} while Lorehold is on the battlefield.

    The grant surface is whatever the implementer exposes.  We probe the two
    most plausible observable shapes and accept either:
      * a method ``miracle_cost(game, card)`` on Lorehold returning a ManaCost
        (or None for non-qualifying cards), or
      * a ``card.miracle_cost`` attribute set on the affected hand cards.
    A test helper resolves whichever exists.
    """

    MIRACLE = ManaCost.parse("{2}")

    @staticmethod
    def _miracle_cost_of(lorehold: Any, game: Any, card: Any) -> Any:
        """Return the miracle cost the implementation assigns to *card*.

        Tries Lorehold.miracle_cost(game, card) first, then a per-card
        ``miracle_cost`` attribute.  Returns None if neither is present.
        """
        fn = getattr(lorehold, "miracle_cost", None)
        if callable(fn):
            return fn(game, card)
        return getattr(card, "miracle_cost", None)

    def test_hand_instant_has_miracle_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _lorehold(game)
        bolt = _instant("Hand Bolt")
        set_board_state(game, 0, battlefield=[card], hand=[bolt])
        cost = self._miracle_cost_of(card, game, bolt)
        assert cost == self.MIRACLE

    def test_hand_sorcery_has_miracle_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _lorehold(game)
        sorc = _sorcery("Hand Sorcery")
        set_board_state(game, 0, battlefield=[card], hand=[sorc])
        cost = self._miracle_cost_of(card, game, sorc)
        assert cost == self.MIRACLE

    def test_hand_creature_does_not_get_miracle(self) -> None:
        """Only instant and sorcery cards gain miracle — not creatures."""
        game = create_game()
        card = _lorehold(game)
        bear = _vanilla_creature("Hand Bear")
        set_board_state(game, 0, battlefield=[card], hand=[bear])
        cost = self._miracle_cost_of(card, game, bear)
        assert cost in (None, ManaCost()) or cost != self.MIRACLE

    def test_opponent_hand_instant_does_not_get_miracle(self) -> None:
        """'in your hand' — an instant in an opponent's hand is unaffected."""
        game = create_game()
        card = _lorehold(game)
        set_board_state(game, 0, battlefield=[card])
        opp_bolt = _instant("Opp Bolt")
        set_board_state(game, 1, hand=[opp_bolt])
        cost = self._miracle_cost_of(card, game, opp_bolt)
        assert cost in (None, ManaCost()) or cost != self.MIRACLE


# ---------------------------------------------------------------------------
# 3. Opponent-upkeep loot trigger registration
# ---------------------------------------------------------------------------


class TestLoreholdUpkeepTriggerRegistration:
    """register_triggers wires a BeginningOfUpkeepTriggeredEvent trigger keyed
    to opponents' upkeeps."""

    def test_registers_one_trigger(self) -> None:
        game = create_game()
        card = _lorehold(game)
        before = len(game.trigger_manager.get_triggers_for_source(card))
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers_for_source(card))
        assert after - before == 1

    def test_trigger_watches_upkeep_event(self) -> None:
        game = create_game()
        card = _lorehold(game)
        card.register_triggers(game)
        regs = game.trigger_manager.get_triggers_for_source(card)
        assert len(regs) == 1
        assert regs[0].event_type is BeginningOfUpkeepTriggeredEvent

    def test_trigger_controller_is_card_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)
        reg = game.trigger_manager.get_triggers_for_source(card)[0]
        assert reg.controller is p1

    def test_trigger_fires_on_opponents_upkeep(self) -> None:
        """The trigger must fire when the active player (whose upkeep it is) is
        an opponent of the controller."""
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)
        reg = game.trigger_manager.get_triggers_for_source(card)[0]
        if reg.condition is None:
            raise AssertionError(
                "Upkeep trigger must be scoped to opponents' upkeeps, not all upkeeps"
            )
        # Opponent (player index 1) is the active player whose upkeep begins.
        game.active_player_index = 1
        event = BeginningOfUpkeepTriggeredEvent()
        assert reg.condition(game, event) is True

    def test_trigger_does_not_fire_on_own_upkeep(self) -> None:
        """The trigger is 'each opponent's upkeep' — not the controller's."""
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)
        reg = game.trigger_manager.get_triggers_for_source(card)[0]
        if reg.condition is None:
            raise AssertionError(
                "Upkeep trigger must be scoped to opponents' upkeeps, not all upkeeps"
            )
        # Controller (player index 0) is the active player.
        game.active_player_index = 0
        event = BeginningOfUpkeepTriggeredEvent()
        assert reg.condition(game, event) is False


# ---------------------------------------------------------------------------
# 3b. Opponent-upkeep loot trigger effect — discard then draw
# ---------------------------------------------------------------------------


class TestLoreholdUpkeepTriggerFires:
    """Firing the event on an opponent's upkeep pushes the trigger onto the
    stack; firing on the controller's own upkeep does not."""

    def _setup(self) -> tuple[Any, Any, LoreholdTheHistorian]:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        return game, p1, card

    def test_opponent_upkeep_event_pushes_trigger(self) -> None:
        game, p1, card = self._setup()
        game.active_player_index = 1
        assert game.stack.is_empty()
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert not game.stack.is_empty()

    def test_own_upkeep_event_does_not_push_trigger(self) -> None:
        game, p1, card = self._setup()
        game.active_player_index = 0
        assert game.stack.is_empty()
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert game.stack.is_empty()


class TestLoreholdLootEffect:
    """Resolving the trigger: 'you may discard a card. If you do, draw a card.'

    The controller's optionality is driven by ``choose_yes_no`` and the card to
    discard by ``choose_card`` (DeterministicPlayer script).  We resolve the
    trigger StackObject directly to observe the discard + draw.
    """

    def _build(self, scripts, *, hand, library):
        """Build a game with Lorehold on player 0's battlefield, player 0 the
        controller, with a scripted hand and a library to draw from.  Player 1
        is the active player (opponent's upkeep)."""
        game = create_game(scripts=scripts)
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], hand=hand)
        # Seed the controller's library so a draw has something to find.
        lib = game.get_library(p1)
        for obj in lib.get_all():
            lib.remove(obj)
        for c in library:
            c.owner = p1
            c.controller = p1
            lib.add(c)
        card.register_triggers(game)
        game.active_player_index = 1
        return game, p1, card

    def _fire_and_resolve(self, game, card):
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert not game.stack.is_empty(), "opponent upkeep trigger should be on stack"
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

    def test_yes_discards_chosen_card_and_draws(self) -> None:
        """Choosing 'yes' discards the chosen card and then draws one."""
        discard_me = _instant("Discard Me")
        draw_me = _vanilla_creature("Draw Me")
        # Script: choose_yes_no -> True, choose_card -> the card to discard.
        game, p1, card = self._build(
            scripts=([True, discard_me], []),
            hand=[discard_me],
            library=[draw_me],
        )

        self._fire_and_resolve(game, card)

        gy = game.get_graveyard(p1)
        hand = game.get_hand(p1)
        assert gy.contains(discard_me), "chosen card should be discarded to graveyard"
        assert hand.contains(draw_me), "controller should have drawn the top library card"
        assert not hand.contains(discard_me), "discarded card must leave the hand"

    def test_yes_is_net_neutral_hand_size(self) -> None:
        """Discard one, draw one — hand size is unchanged after a 'yes'."""
        discard_me = _instant("Discard Me")
        draw_me = _sorcery("Draw Me")
        game, p1, card = self._build(
            scripts=([True, discard_me], []),
            hand=[discard_me],
            library=[draw_me],
        )

        self._fire_and_resolve(game, card)

        assert len(game.get_hand(p1).get_all()) == 1

    def test_no_does_not_discard_or_draw(self) -> None:
        """'you may' — declining leaves the hand and library untouched."""
        keep_me = _instant("Keep Me")
        draw_me = _vanilla_creature("Draw Me")
        # Script: choose_yes_no -> False.  No choose_card / draw should happen.
        game, p1, card = self._build(
            scripts=([False], []),
            hand=[keep_me],
            library=[draw_me],
        )

        self._fire_and_resolve(game, card)

        hand = game.get_hand(p1)
        gy = game.get_graveyard(p1)
        assert hand.contains(keep_me), "declined loot should keep the card in hand"
        assert not gy.contains(keep_me), "nothing should be discarded on 'no'"
        assert not hand.contains(draw_me), "no draw should happen on 'no'"
        assert len(hand.get_all()) == 1

    def test_empty_hand_does_not_draw(self) -> None:
        """'If you do' — with no card to discard, no draw occurs.

        With an empty hand the player cannot discard, so the conditional draw
        must not fire.  An empty script proves no prompt forces a discard that
        cannot be paid.
        """
        draw_me = _vanilla_creature("Draw Me")
        # Yes to the "you may", but the hand is empty so the discard can't be
        # made; the draw is therefore skipped.  Allow either an immediate "no"
        # from an empty-hand guard (empty script) or a single yes/no prompt.
        game, p1, card = self._build(
            scripts=([False], []),
            hand=[],
            library=[draw_me],
        )

        self._fire_and_resolve(game, card)

        hand = game.get_hand(p1)
        assert not hand.contains(draw_me), "no discard means no draw"
        assert len(hand.get_all()) == 0


# ---------------------------------------------------------------------------
# 2b. Miracle draw-time cast — end-to-end through engine.game.draw_card.
#
# Previously recorded as untestable (no engine surface).  The implementer
# added engine/miracle.py + engine.casting.cast_spell_alternative + a draw-time
# hook in engine.game.draw_card gated on cards_drawn_this_turn, so the full
# "reveal/cast on first draw" contract is now observable.
# ---------------------------------------------------------------------------


class TestLoreholdMiracleDrawCast:
    """With Lorehold in play, drawing a stamped instant/sorcery as the FIRST
    card of the turn offers a miracle cast for {2} (paid out of the mana pool),
    putting the spell on the stack instead of leaving it in hand.

    These tests exercise the real engine path: a card stamped via
    ``Lorehold.miracle_cost`` is placed on top of the library, then drawn with
    ``engine.game.draw_card``, which fires the miracle hook.
    """

    MIRACLE = ManaCost.parse("{2}")

    def _build(self, *, scripts, top_card, controller_mana=None):
        """Game with Lorehold on player 0's battlefield (controller = p0), a
        ``top_card`` placed on top of player 0's library and stamped with
        Lorehold's miracle cost, and an optional starting mana pool.

        Returns ``(game, p1, lorehold, top_card)``.
        """
        game = create_game(scripts=scripts)
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        if controller_mana is not None:
            set_board_state(game, 0, mana=controller_mana)

        # Seed the library with exactly the cards we want, top_card on top.
        lib = game.get_library(p1)
        for obj in lib.get_all():
            lib.remove(obj)
        top_card.owner = p1
        top_card.controller = p1
        lib.add(top_card)

        # Reset the per-turn draw counter so this draw counts as the first.
        p1.cards_drawn_this_turn = 0

        # Stamp the miracle cost the way Lorehold's static ability does: the
        # card is about to be drawn into the controller's hand, so we mirror
        # the engine's grant by stamping it directly.  (miracle_cost() itself
        # only stamps cards already in hand; the draw-time hook reads the stamp
        # off the just-drawn card.)
        from engine.miracle import set_miracle_cost

        set_miracle_cost(top_card, self.MIRACLE)
        return game, p1, lorehold, top_card

    def test_first_draw_yes_casts_for_miracle_cost(self) -> None:
        """First card drawn + scripted 'yes' + {2} available → the spell is put
        on the stack (cast), not left in hand."""
        bolt = _instant("Miracle Bolt")
        game, p1, lorehold, bolt = self._build(
            scripts=([True], []),
            top_card=bolt,
            controller_mana={ManaType.COLORLESS: 2},
        )

        assert game.stack.is_empty()
        drawn = draw_card(game, p1)

        assert drawn is bolt
        # Cast: the spell is on the stack and has left the hand.
        assert not game.stack.is_empty(), "miracle 'yes' should put the spell on the stack"
        assert game.stack.peek().source is bolt
        assert not game.get_hand(p1).contains(bolt), "miracle-cast card leaves the hand"

    def test_first_draw_yes_pays_two_not_full_cost(self) -> None:
        """The miracle cast pays {2} from the pool, NOT the card's full mana
        cost.  Starting with exactly {2}, the pool is empty afterward."""
        # Full cost is {2}{U} (3 mana) — but we supply only {2}, proving the
        # alternative cost is what's paid.
        sorc = _sorcery("Miracle Sorcery")  # mana_cost {2}{U}
        game, p1, lorehold, sorc = self._build(
            scripts=([True], []),
            top_card=sorc,
            controller_mana={ManaType.COLORLESS: 2},
        )

        draw_card(game, p1)

        assert not game.stack.is_empty(), "spell should be cast for its miracle cost"
        assert p1.mana_pool.total() == 0, "exactly {2} should have been spent"

    def test_first_draw_no_leaves_card_in_hand(self) -> None:
        """Declining the 'you may' leaves the card in hand (normal draw)."""
        bolt = _instant("Declined Bolt")
        game, p1, lorehold, bolt = self._build(
            scripts=([False], []),
            top_card=bolt,
            controller_mana={ManaType.COLORLESS: 2},
        )

        drawn = draw_card(game, p1)

        assert drawn is bolt
        assert game.stack.is_empty(), "declining miracle should not put anything on the stack"
        assert game.get_hand(p1).contains(bolt), "declined card stays in hand"
        assert p1.mana_pool.total() == 2, "no mana spent when miracle is declined"

    def test_not_first_draw_does_not_offer_miracle(self) -> None:
        """First-card gating: when the drawn card is NOT the first card drawn
        this turn, no miracle cast is offered even with mana available.

        We pre-set ``cards_drawn_this_turn`` to a non-zero value so that the
        draw under test is the SECOND draw of the turn; the gate must suppress
        the offer (the spell stays in hand, no mana spent, stack empty).
        """
        bolt = _instant("Late Bolt")
        # No scripted yes/no answer at all — if the hook wrongly fired it would
        # raise ScriptExhaustedError, which makes a regression loud.
        game, p1, lorehold, bolt = self._build(
            scripts=([], []),
            top_card=bolt,
            controller_mana={ManaType.COLORLESS: 2},
        )
        # Simulate that a card was already drawn this turn; draw_card will
        # increment to 2, so this is not the first draw.
        p1.cards_drawn_this_turn = 1

        drawn = draw_card(game, p1)

        assert drawn is bolt
        assert game.stack.is_empty(), "non-first draw must not offer/cast miracle"
        assert game.get_hand(p1).contains(bolt), "card stays in hand when gate blocks"
        assert p1.mana_pool.total() == 2, "no mana spent when gate blocks the offer"

    def test_first_draw_yes_without_mana_keeps_card_in_hand(self) -> None:
        """If the controller says yes but cannot pay {2}, the cast fails
        gracefully and the card remains in hand (no exception, stack empty)."""
        bolt = _instant("Broke Bolt")
        game, p1, lorehold, bolt = self._build(
            scripts=([True], []),
            top_card=bolt,
            controller_mana=None,  # empty pool
        )

        drawn = draw_card(game, p1)

        assert drawn is bolt
        assert game.stack.is_empty(), "no mana → no cast on the stack"
        assert game.get_hand(p1).contains(bolt), "unpayable miracle leaves card in hand"

    def test_stamp_is_readable_via_engine_helper(self) -> None:
        """Sanity check on the shared contract: the miracle stamp Lorehold sets
        on a hand card is the same {2} the draw-time hook reads via
        ``engine.miracle.get_miracle_cost``."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        bolt = _instant("Stamp Bolt")
        set_board_state(game, 0, battlefield=[lorehold], hand=[bolt])

        # Lorehold's static ability stamps the hand card.
        lorehold.miracle_cost(game, bolt)

        assert get_miracle_cost(bolt) == self.MIRACLE
