"""Tests for SOS 201 — Lorehold, the Historian.

Lorehold, the Historian is a {3}{R}{W} Legendary Creature — Elder Dragon
with power/toughness 5/5 and the following abilities:

1. Flying, haste (evergreen keywords).
2. "Each instant and sorcery card in your hand has miracle {2}." — a granted
   static ability (CR 702.94). The engine has no native draw-reveal-cast-for-
   miracle pipeline, so we test the observable portion of the contract: the
   card advertises the miracle cost ({2}) and stamps it onto the instant and
   sorcery cards in *its controller's* hand (and nothing else).
3. "At the beginning of each opponent's upkeep, you may discard a card. If you
   do, draw a card." — an optional rummage-style triggered ability that fires
   only on an *opponent's* upkeep.

These tests target the public card contract (static data, keyword flags,
combat-rule interactions through the engine, the trigger registration, and the
trigger's effect). They are written before implementation (TDD red phase).
"""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Land, Sorcery
from engine.combat import _can_attack, _can_block
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static characteristics
# ---------------------------------------------------------------------------


class TestLoreholdProperties:
    """Static card data should match the SOS 201 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(LoreholdTheHistorian(owner=None), Creature)

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

    def test_elder_dragon_subtypes(self) -> None:
        subtypes = LoreholdTheHistorian(owner=None).subtypes
        assert {"Elder", "Dragon"} <= subtypes

    def test_colors_are_red_white(self) -> None:
        """The spec lists colors R and W; cards advertise this via self.colors."""
        colors = set(getattr(LoreholdTheHistorian(owner=None), "colors", []))
        assert colors == {"R", "W"}


# ---------------------------------------------------------------------------
# Flying + haste keywords
# ---------------------------------------------------------------------------


class TestLoreholdKeywords:
    """Flying and haste keyword flags and their combat-rule consequences."""

    def test_has_flying_and_haste(self) -> None:
        kw = LoreholdTheHistorian(owner=None).keywords
        assert Keyword.FLYING in kw
        assert Keyword.HASTE in kw

    def test_haste_allows_attacking_while_summoning_sick(self) -> None:
        """Haste lets a freshly-cast Lorehold attack the turn it arrives."""
        card = LoreholdTheHistorian(owner=None)
        card.summoning_sick = True
        card.is_tapped = False
        assert _can_attack(card) is True

    def test_ground_creature_cannot_block_flying_lorehold(self) -> None:
        attacker = LoreholdTheHistorian(owner=None)
        ground = Creature(name="Ground Bear", base_power=2, base_toughness=2)
        ground.keywords = Keyword(0)
        ground.is_tapped = False
        assert _can_block(ground, attacker) is False

    def test_flying_creature_can_block_flying_lorehold(self) -> None:
        attacker = LoreholdTheHistorian(owner=None)
        flier = Creature(name="Air Bear", base_power=2, base_toughness=2)
        flier.keywords = Keyword.FLYING
        flier.is_tapped = False
        assert _can_block(flier, attacker) is True

    def test_reach_creature_can_block_flying_lorehold(self) -> None:
        attacker = LoreholdTheHistorian(owner=None)
        spider = Creature(name="Spider", base_power=1, base_toughness=4)
        spider.keywords = Keyword.REACH
        spider.is_tapped = False
        assert _can_block(spider, attacker) is True


# ---------------------------------------------------------------------------
# Miracle granting: "Each instant and sorcery card in your hand has miracle {2}"
# ---------------------------------------------------------------------------


def _make_instant(name: str, owner=None) -> Instant:
    spell = Instant(name=name, mana_cost=ManaCost.parse("{3}{U}"), owner=owner, controller=owner)
    return spell


def _make_sorcery(name: str, owner=None) -> Sorcery:
    spell = Sorcery(name=name, mana_cost=ManaCost.parse("{4}{B}"), owner=owner, controller=owner)
    return spell


class TestLoreholdMiracleGrant:
    """The granted miracle {2} static ability marks eligible hand cards.

    The engine has no native miracle pipeline, so the card exposes the
    granting as a method (``grant_miracle(game)``) that stamps the miracle
    cost onto each instant/sorcery card in *its controller's* hand. These
    tests exercise that contract.
    """

    def test_miracle_cost_is_two_generic(self) -> None:
        """The granted alternative cost is {2}."""
        card = LoreholdTheHistorian(owner=None)
        assert card.MIRACLE_COST == ManaCost.parse("{2}")

    def test_grants_miracle_to_instant_in_controller_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        bolt = _make_instant("Bolt", owner=p1)
        set_board_state(game, 0, battlefield=[lorehold], hand=[bolt])
        lorehold.grant_miracle(game)
        assert bolt.miracle_cost == ManaCost.parse("{2}")

    def test_grants_miracle_to_sorcery_in_controller_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        ritual = _make_sorcery("Ritual", owner=p1)
        set_board_state(game, 0, battlefield=[lorehold], hand=[ritual])
        lorehold.grant_miracle(game)
        assert ritual.miracle_cost == ManaCost.parse("{2}")

    def test_does_not_grant_miracle_to_noncast_types_in_hand(self) -> None:
        """Creatures and lands in hand are not instants/sorceries — no miracle."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        forest = Land(name="Forest", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold], hand=[bear, forest])
        lorehold.grant_miracle(game)
        assert getattr(bear, "miracle_cost", None) is None
        assert getattr(forest, "miracle_cost", None) is None

    def test_does_not_grant_miracle_to_opponent_hand(self) -> None:
        """'your hand' means the controller's hand, not the opponent's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        opp_spell = _make_instant("Opp Bolt", owner=p2)
        set_board_state(game, 0, battlefield=[lorehold])
        set_board_state(game, 1, hand=[opp_spell])
        lorehold.grant_miracle(game)
        assert getattr(opp_spell, "miracle_cost", None) is None


# ---------------------------------------------------------------------------
# Opponent's-upkeep loot trigger
# ---------------------------------------------------------------------------


class TestLoreholdUpkeepTriggerRegistration:
    """register_triggers wires a BeginningOfUpkeep trigger for this card."""

    def test_registers_an_upkeep_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        before = len(game.trigger_manager.get_triggers_for_source(card))
        card.register_triggers(game)
        after = game.trigger_manager.get_triggers_for_source(card)
        assert len(after) - before == 1
        assert after[0].event_type is BeginningOfUpkeepTriggeredEvent
        assert after[0].controller is p1


class TestLoreholdUpkeepTriggerCondition:
    """The trigger fires only on an opponent's upkeep, never the controller's."""

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        return game, p1, p2, card

    def test_does_not_fire_on_controllers_own_upkeep(self) -> None:
        game, p1, p2, card = self._setup()
        game.active_player_index = 0  # controller's own upkeep
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert game.stack.is_empty()

    def test_fires_on_opponents_upkeep(self) -> None:
        game, p1, p2, card = self._setup()
        game.active_player_index = 1  # opponent's upkeep
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert not game.stack.is_empty()
        stack_obj = game.stack.peek()
        assert stack_obj.source is card
        assert stack_obj.controller is p1


class TestLoreholdUpkeepTriggerEffect:
    """The optional 'discard a card, if you do draw a card' effect."""

    def _build_trigger_effect(self, game, controller):
        card = LoreholdTheHistorian(owner=controller, controller=controller)
        game.get_battlefield(controller).add(card)
        card.register_triggers(game)
        reg = game.trigger_manager.get_triggers_for_source(card)[0]
        return card, reg

    def test_yes_discards_chosen_card_and_draws(self) -> None:
        # Controller is player 0; library has a card to draw, hand has one to pitch.
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        to_discard = _make_sorcery("Pitch Me", owner=p1)
        # Put a card in the library so the draw has something to pull.
        drawn = Creature(name="Drawn Bear", base_power=1, base_toughness=1, owner=p1, controller=p1)
        set_board_state(game, 0, hand=[to_discard])
        game.get_library(p1).add(drawn)
        # Script: choose_yes_no -> True, choose_card -> to_discard.
        p1._script.append(to_discard)

        card, reg = self._build_trigger_effect(game, p1)
        reg.effect(game)

        # The chosen card is now in the graveyard...
        assert game.get_graveyard(p1).contains(to_discard)
        assert not game.get_hand(p1).contains(to_discard)
        # ...and the drawn card is now in hand.
        assert game.get_hand(p1).contains(drawn)
        assert not game.get_library(p1).contains(drawn)

    def test_no_does_not_discard_or_draw(self) -> None:
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        keep = _make_sorcery("Keep Me", owner=p1)
        drawn = Creature(name="Library Bear", base_power=1, base_toughness=1, owner=p1, controller=p1)
        set_board_state(game, 0, hand=[keep])
        game.get_library(p1).add(drawn)

        card, reg = self._build_trigger_effect(game, p1)
        reg.effect(game)

        # Declined: nothing discarded, nothing drawn.
        assert game.get_hand(p1).contains(keep)
        assert not game.get_graveyard(p1).contains(keep)
        assert game.get_library(p1).contains(drawn)
        assert len(game.get_hand(p1).get_all()) == 1

    def test_empty_hand_is_safe_noop(self) -> None:
        """With no card to discard the effect cannot 'do' anything, so no draw.

        'If you do, draw a card' only triggers the draw when a card was
        actually discarded. An empty hand means no discard and therefore no
        draw — and the effect must not raise.
        """
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        drawn = Creature(name="Library Bear", base_power=1, base_toughness=1, owner=p1, controller=p1)
        set_board_state(game, 0, hand=[])
        game.get_library(p1).add(drawn)

        card, reg = self._build_trigger_effect(game, p1)
        reg.effect(game)

        # Could not discard, so must not draw.
        assert game.get_library(p1).contains(drawn)
        assert len(game.get_hand(p1).get_all()) == 0


# ---------------------------------------------------------------------------
# Draw-time miracle: "You may cast it for its miracle cost when you draw it
# if it's the first card you drew this turn."
# ---------------------------------------------------------------------------


class TestLoreholdDrawTimeMiracle:
    """The deterministic at-draw miracle window built into ``draw_card``.

    With Lorehold on a player's battlefield, the FIRST card that player draws
    each turn is offered the miracle cast when it's an instant/sorcery. These
    tests drive the real engine ``draw_card`` and assert the full observable
    contract: the offer gating, the cast-for-{2} payment, the decline path,
    and the no-offer cases (non-first card, no granting permanent).

    Conventions: the controller is a ``DeterministicPlayer`` whose
    ``choose_yes_no`` is scripted via the ``scripts`` arg, and the drawn card
    is placed on top of the library (the last object added — see
    ``ZoneContainer`` / ``draw_card``'s ``library.top(1)``).
    """

    @staticmethod
    def _put_on_top(game, player, card) -> None:
        """Place *card* on top of *player*'s library (drawn next)."""
        game.get_library(player).add(card)

    def test_first_card_yes_casts_for_miracle_cost(self) -> None:
        """First-card instant + Lorehold + 'yes' → cast for {2}.

        Validates: the controller is offered the cast, ``miracle_cost`` is
        stamped, the card is paid for with {2} (pool drained, ``mana_spent``
        records the alternative cost's cmc), the card leaves hand and is on
        the stack (a StackObject was pushed), not still in hand.
        """
        game = create_game(scripts=([True], []))  # choose_yes_no -> yes
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        bolt = _make_instant("Miracle Bolt", owner=p1)
        # Exactly {2} generic available so we can prove the cost was paid.
        set_board_state(
            game, 0, battlefield=[lorehold], hand=[], mana={ManaType.COLORLESS: 2}
        )
        p1.cards_drawn_this_turn = 0
        self._put_on_top(game, p1, bolt)

        drawn = draw_card(game, p1)

        assert drawn is bolt
        # Offered + accepted: miracle cost stamped and the card was cast.
        assert bolt.miracle_cost == ManaCost.parse("{2}")
        assert not game.get_hand(p1).contains(bolt)  # left hand to be cast
        assert p1.zones[Zone.STACK].contains(bolt)    # now on the stack zone
        assert not game.stack.is_empty()              # a spell is on the stack
        assert game.stack.peek().source is bolt
        # The {2} miracle cost was paid: the pool is emptied and the recorded
        # mana spent equals the alternative cost's converted mana cost.
        assert p1.mana_pool.total() == 0
        assert bolt.mana_spent == 2

    def test_first_card_no_keeps_card_and_spends_no_mana(self) -> None:
        """First-card instant + Lorehold + 'no' → card stays in hand, no cost.

        Declining the offer must not move the card or spend mana. The
        ``miracle_cost`` may still be stamped (it is advertised before the
        yes/no prompt), but nothing is cast.
        """
        game = create_game(scripts=([False], []))  # choose_yes_no -> no
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        bolt = _make_instant("Declined Bolt", owner=p1)
        set_board_state(
            game, 0, battlefield=[lorehold], hand=[], mana={ManaType.COLORLESS: 2}
        )
        p1.cards_drawn_this_turn = 0
        self._put_on_top(game, p1, bolt)

        drawn = draw_card(game, p1)

        assert drawn is bolt
        # Declined: the card remains in hand and nothing went on the stack.
        assert game.get_hand(p1).contains(bolt)
        assert not p1.zones[Zone.STACK].contains(bolt)
        assert game.stack.is_empty()
        # No mana was spent.
        assert p1.mana_pool.total() == 2
        assert getattr(bolt, "mana_spent", None) is None

    def test_non_first_card_draw_is_not_offered(self) -> None:
        """A SECOND draw is never offered the miracle, even with Lorehold out.

        Draw a (non-spell) card first so ``cards_drawn_this_turn`` becomes 1,
        then draw the instant as the second card. The first-card gate fails,
        so there is no prompt, no cast, no stamp — the instant simply enters
        hand. The empty yes/no script proves no prompt was issued (a stray
        prompt would raise ``ScriptExhaustedError``).
        """
        game = create_game(scripts=([], []))  # no yes/no answers available
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        filler = Creature(
            name="Filler Bear", base_power=1, base_toughness=1, owner=p1, controller=p1
        )
        bolt = _make_instant("Late Bolt", owner=p1)
        set_board_state(
            game, 0, battlefield=[lorehold], hand=[], mana={ManaType.COLORLESS: 2}
        )
        p1.cards_drawn_this_turn = 0
        # bolt added first (bottom), filler added second (top → drawn first).
        self._put_on_top(game, p1, bolt)
        self._put_on_top(game, p1, filler)

        first = draw_card(game, p1)   # non-spell first card, no offer
        second = draw_card(game, p1)  # instant, but it is the 2nd card

        assert first is filler
        assert second is bolt
        assert p1.cards_drawn_this_turn == 2
        # No offer for the second card: it just enters hand untouched.
        assert game.get_hand(p1).contains(bolt)
        assert game.stack.is_empty()
        assert p1.mana_pool.total() == 2
        assert getattr(bolt, "miracle_cost", None) is None

    def test_no_miracle_grantor_means_no_offer(self) -> None:
        """First-card instant with NO granting permanent → no offer at all.

        Regression-safety for the draw hook's gate: when nothing the drawing
        player controls grants miracle, ``draw_card`` is a complete no-op
        beyond the normal draw — no prompt (empty script proves it), no stamp,
        no mana spent, card simply enters hand.
        """
        game = create_game(scripts=([], []))  # no yes/no answers available
        p1 = game.players[0]
        bolt = _make_instant("Ungranted Bolt", owner=p1)
        # No Lorehold (or any granting permanent) on the battlefield.
        set_board_state(
            game, 0, battlefield=[], hand=[], mana={ManaType.COLORLESS: 2}
        )
        p1.cards_drawn_this_turn = 0
        self._put_on_top(game, p1, bolt)

        drawn = draw_card(game, p1)

        assert drawn is bolt
        assert game.get_hand(p1).contains(bolt)
        assert game.stack.is_empty()
        assert p1.mana_pool.total() == 2
        assert getattr(bolt, "miracle_cost", None) is None
        # No prompt was consumed.
        assert p1.remaining_choices == 0

    def test_first_card_sorcery_also_offered_and_cast(self) -> None:
        """Sorceries get the miracle window too (not just instants).

        Mirrors the instant 'yes' path with a sorcery on top, proving the
        grant applies to both instant and sorcery card types at draw time.
        """
        game = create_game(scripts=([True], []))  # yes
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        ritual = _make_sorcery("Miracle Ritual", owner=p1)
        set_board_state(
            game, 0, battlefield=[lorehold], hand=[], mana={ManaType.COLORLESS: 2}
        )
        p1.cards_drawn_this_turn = 0
        self._put_on_top(game, p1, ritual)

        drawn = draw_card(game, p1)

        assert drawn is ritual
        assert ritual.miracle_cost == ManaCost.parse("{2}")
        assert not game.get_hand(p1).contains(ritual)
        assert p1.zones[Zone.STACK].contains(ritual)
        assert game.stack.peek().source is ritual
        assert p1.mana_pool.total() == 0
        assert ritual.mana_spent == 2
