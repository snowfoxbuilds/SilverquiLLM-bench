"""Tests for SOS 201 — Lorehold, the Historian.

Lorehold, the Historian is a {3}{R}{W} Legendary Creature — Elder Dragon,
5/5, with:

1. **Flying, haste** — evergreen keywords (both in ``engine.types.Keyword``).
2. **Miracle granting** — "Each instant and sorcery card in your hand has
   miracle {2}." Miracle is NOT in the ``Keyword`` enum (and per KEY_DECISIONS
   we must not extend that enum), so the card models it as a custom mechanic.
   The tests here exercise the *granting contract*: a queryable miracle cost of
   {2} for instants/sorceries in the controller's hand, and no miracle for
   non-instant/non-sorcery cards or for cards outside the controller's hand.
   The "cast it when you draw it, if it's the first card you drew this turn"
   timing has no engine surface and is recorded in ``untestable.json``.
3. **Opponent-upkeep loot trigger** — "At the beginning of each opponent's
   upkeep, you may discard a card. If you do, draw a card." Modeled via
   ``register_triggers`` watching ``BeginningOfUpkeepTriggeredEvent`` with a
   condition that fires only when an opponent is the active player.

These tests define the TDD contract; ``card_impl.py`` is a stub, so they are
expected to fail until the card is implemented.
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _instant(name: str = "Test Instant") -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{1}{U}"))


def _sorcery(name: str = "Test Sorcery") -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse("{2}{R}"))


def _vanilla_creature(name: str = "Grizzly Bears") -> Creature:
    c = Creature(name=name, base_power=2, base_toughness=2)
    c.card_types = {CardType.CREATURE}
    return c


def _filler_hand_card(name: str = "Spare Card") -> Sorcery:
    """A discardable card so the loot trigger always has something to pitch."""
    return Sorcery(name=name, mana_cost=ManaCost.parse("{1}"))


def _miracle_cost(card_obj: LoreholdTheHistorian, game: Any, target: Any) -> Any:
    """Query Lorehold's granted miracle cost for *target*.

    The implementation may expose this contract under any of a few reasonable
    names; this helper probes them so the tests stay decoupled from the exact
    method spelling while still asserting the {2} miracle grant.
    """
    for attr in ("get_miracle_cost", "miracle_cost_for", "granted_miracle_cost"):
        fn = getattr(card_obj, attr, None)
        if callable(fn):
            return fn(game, target)
    raise AssertionError(
        "Lorehold must expose a miracle-cost query "
        "(get_miracle_cost/miracle_cost_for/granted_miracle_cost)"
    )


# ---------------------------------------------------------------------------
# Static card data
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

    def test_is_elder_dragon(self) -> None:
        subtypes = LoreholdTheHistorian(owner=None).subtypes
        assert "Elder" in subtypes
        assert "Dragon" in subtypes

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in LoreholdTheHistorian(owner=None).keywords

    def test_has_haste(self) -> None:
        assert Keyword.HASTE in LoreholdTheHistorian(owner=None).keywords

    def test_is_red_white(self) -> None:
        """Cost {3}{R}{W} — the card has both a red and a white pip."""
        pips = LoreholdTheHistorian(owner=None).mana_cost.pips
        from engine.types import ManaType

        assert pips.get(ManaType.RED, 0) >= 1
        assert pips.get(ManaType.WHITE, 0) >= 1


# ---------------------------------------------------------------------------
# Miracle granting
# ---------------------------------------------------------------------------


class TestLoreholdMiracleGrant:
    """Each instant and sorcery card in your hand has miracle {2}."""

    def test_instant_in_your_hand_gets_miracle_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        spell = _instant("Lightning Helix")
        set_board_state(game, 0, battlefield=[lorehold], hand=[spell])
        cost = _miracle_cost(lorehold, game, spell)
        assert cost == ManaCost.parse("{2}")

    def test_sorcery_in_your_hand_gets_miracle_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        spell = _sorcery("Reconstruct History")
        set_board_state(game, 0, battlefield=[lorehold], hand=[spell])
        cost = _miracle_cost(lorehold, game, spell)
        assert cost == ManaCost.parse("{2}")

    def test_creature_in_your_hand_gets_no_miracle(self) -> None:
        """Miracle is granted only to instants and sorceries."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        creature = _vanilla_creature("Hill Giant")
        set_board_state(game, 0, battlefield=[lorehold], hand=[creature])
        assert _miracle_cost(lorehold, game, creature) is None

    def test_opponent_hand_spell_gets_no_miracle(self) -> None:
        """The grant is restricted to cards in YOUR hand only."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        opp_spell = _instant("Opponent Bolt")
        set_board_state(game, 0, battlefield=[lorehold])
        set_board_state(game, 1, hand=[opp_spell])
        assert _miracle_cost(lorehold, game, opp_spell) is None

    def test_spell_in_graveyard_gets_no_miracle(self) -> None:
        """Only cards in hand are granted miracle, not other zones."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        gy_spell = _instant("Graveyard Bolt")
        set_board_state(game, 0, battlefield=[lorehold], graveyard=[gy_spell])
        assert _miracle_cost(lorehold, game, gy_spell) is None


# ---------------------------------------------------------------------------
# Opponent-upkeep loot trigger — registration
# ---------------------------------------------------------------------------


class TestLoreholdLootTriggerRegistration:
    """register_triggers wires a BeginningOfUpkeepTriggeredEvent trigger."""

    def test_registers_one_upkeep_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        lorehold.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after - before == 1

    def test_registered_trigger_watches_upkeep_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        lorehold.register_triggers(game)
        regs = game.trigger_manager.get_triggers_for_source(lorehold)
        assert len(regs) == 1
        reg = regs[0]
        assert isinstance(reg, TriggerRegistration)
        assert reg.event_type is BeginningOfUpkeepTriggeredEvent

    def test_trigger_fires_on_opponent_upkeep(self) -> None:
        """Condition is satisfied when an opponent is the active player."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)
        reg = game.trigger_manager.get_triggers_for_source(lorehold)[0]
        # Opponent (player index 1) is the active player.
        game.active_player_index = 1
        if reg.condition is None:
            return
        assert reg.condition(game, BeginningOfUpkeepTriggeredEvent()) is True

    def test_trigger_does_not_fire_on_own_upkeep(self) -> None:
        """"each opponent's upkeep" — not the controller's own upkeep."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)
        reg = game.trigger_manager.get_triggers_for_source(lorehold)[0]
        # Controller (player index 0) is the active player.
        game.active_player_index = 0
        if reg.condition is None:
            # An always-fire trigger would be wrong here; force a real check.
            raise AssertionError(
                "Loot trigger must distinguish opponent upkeep from own upkeep"
            )
        assert reg.condition(game, BeginningOfUpkeepTriggeredEvent()) is False


# ---------------------------------------------------------------------------
# Opponent-upkeep loot trigger — effect
# ---------------------------------------------------------------------------


def _fire_opponent_upkeep(game: Any, lorehold: LoreholdTheHistorian) -> int:
    """Register Lorehold's triggers, fire an opponent's upkeep, and resolve.

    Returns the number of objects that were pushed onto the stack by the
    upkeep event — so tests can assert the loot trigger actually fired (a
    stub that registers nothing pushes zero and the assertion fails).
    """
    lorehold.register_triggers(game)
    game.active_player_index = 1  # opponent is active
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    pushed = len(game.stack.objects())
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
    return pushed


class TestLoreholdLootEffect:
    """you may discard a card; if you do, draw a card."""

    def test_discard_then_draw_keeps_hand_size(self) -> None:
        """Looting one card: hand size net-zero (pitch one, draw one)."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        pitch = _filler_hand_card("Pitch Me")
        library_card = _sorcery("Top of Library")
        set_board_state(game, 0, battlefield=[lorehold], hand=[pitch])
        # Seed the library so the draw has a card to find.
        p1.zones[Zone.LIBRARY].add(library_card)
        # Script: choose to discard (yes), then choose which card to pitch.
        p1._script.appendleft(pitch)
        p1._script.appendleft(True)

        before = len(game.get_hand(p1).get_all())
        pushed = _fire_opponent_upkeep(game, lorehold)
        after = len(game.get_hand(p1).get_all())
        # The loot trigger must actually fire on the opponent's upkeep.
        assert pushed >= 1
        # Net-zero: one discarded, one drawn.
        assert after == before
        assert game.get_graveyard(p1).contains(pitch)
        assert game.get_hand(p1).contains(library_card)

    def test_discard_card_goes_to_graveyard(self) -> None:
        """The discarded card ends up in the controller's graveyard."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        pitch = _filler_hand_card("Pitch Me")
        library_card = _sorcery("Top of Library")
        set_board_state(game, 0, battlefield=[lorehold], hand=[pitch])
        p1.zones[Zone.LIBRARY].add(library_card)
        p1._script.appendleft(pitch)
        p1._script.appendleft(True)

        _fire_opponent_upkeep(game, lorehold)
        assert game.get_graveyard(p1).contains(pitch)

    def test_drawn_card_enters_hand(self) -> None:
        """The looted draw moves the top library card into hand."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        pitch = _filler_hand_card("Pitch Me")
        library_card = _sorcery("Top of Library")
        set_board_state(game, 0, battlefield=[lorehold], hand=[pitch])
        p1.zones[Zone.LIBRARY].add(library_card)
        p1._script.appendleft(pitch)
        p1._script.appendleft(True)

        _fire_opponent_upkeep(game, lorehold)
        assert game.get_hand(p1).contains(library_card)
        assert not p1.zones[Zone.LIBRARY].contains(library_card)

    def test_declining_discard_draws_nothing(self) -> None:
        """"you may discard" — declining means no discard and no draw."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        pitch = _filler_hand_card("Keep Me")
        library_card = _sorcery("Top of Library")
        set_board_state(game, 0, battlefield=[lorehold], hand=[pitch])
        p1.zones[Zone.LIBRARY].add(library_card)
        # Script: decline (no).
        p1._script.appendleft(False)

        pushed = _fire_opponent_upkeep(game, lorehold)
        # The trigger must still fire on the opponent's upkeep (it is a "may").
        assert pushed >= 1
        # Card kept in hand, library untouched (no draw), nothing discarded.
        assert game.get_hand(p1).contains(pitch)
        assert p1.zones[Zone.LIBRARY].contains(library_card)
        assert not game.get_graveyard(p1).contains(pitch)

    def test_empty_hand_is_a_noop(self) -> None:
        """With no card to discard, the trigger does nothing and does not raise."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        library_card = _sorcery("Top of Library")
        set_board_state(game, 0, battlefield=[lorehold], hand=[])
        p1.zones[Zone.LIBRARY].add(library_card)
        # Decline (or there is simply nothing to discard).
        p1._script.appendleft(False)

        pushed = _fire_opponent_upkeep(game, lorehold)
        # The trigger still fires on the opponent's upkeep even with an empty hand.
        assert pushed >= 1
        # No discard happened and no card was drawn.
        assert p1.zones[Zone.LIBRARY].contains(library_card)
        assert len(game.get_hand(p1).get_all()) == 0


# ---------------------------------------------------------------------------
# Dynamic miracle draw-window
# ---------------------------------------------------------------------------


def _setup_lorehold_with_library_top(
    top_card: Any,
    *,
    on_battlefield: bool = True,
    mana: int = 2,
    drawn_already: int = 0,
) -> tuple[Any, Any, LoreholdTheHistorian | None]:
    """Build a game where *top_card* is the top of player 0's library.

    The miracle window draws the first card of the turn into hand and then
    offers to cast it for {2}; the controller therefore needs at least 2 mana
    in pool to actually pay the miracle cost. ``drawn_already`` seeds
    ``cards_drawn_this_turn`` so a test can simulate a second (non-first) draw.

    Returns ``(game, player0, lorehold_or_None)``. When ``on_battlefield`` is
    False, no Lorehold is created/registered, so no miracle grant is active.
    """
    game = create_game()
    p1 = game.players[0]
    lorehold: LoreholdTheHistorian | None = None

    if on_battlefield:
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(
            game, 0, battlefield=[lorehold], hand=[], mana={ManaType.COLORLESS: mana}
        )
        # Wiring up triggers also registers the dynamic miracle grant.
        lorehold.register_triggers(game)
    else:
        set_board_state(
            game, 0, battlefield=[], hand=[], mana={ManaType.COLORLESS: mana}
        )

    # Make sure ownership is set for the library card, then put it on top.
    top_card.owner = p1
    top_card.controller = p1
    p1.zones[Zone.LIBRARY].add(top_card)
    p1.cards_drawn_this_turn = drawn_already
    return game, p1, lorehold


def _on_stack(game: Any, card: Any) -> bool:
    """Return ``True`` if *card* is currently a spell on the stack."""
    return any(obj.source is card for obj in game.stack.objects())


class TestLoreholdMiracleDrawWindow:
    """The dynamic half of miracle — cast the first card drawn this turn for {2}.

    "(You may cast a card for its miracle cost when you draw it if it's the
    first card you drew this turn.)" These tests drive ``engine.game.draw_card``
    directly and script the controller's ``choose_yes_no`` answer to exercise the
    engine's additive miracle draw-window (``GameState.fire_miracle_window`` →
    ``engine.casting.cast_spell_alternative``).
    """

    def test_first_drawn_instant_offered_miracle_cast_for_two(self) -> None:
        """Drawing an instant as the first card of the turn casts it for {2}."""
        spell = Instant(name="Lightning Bolt", mana_cost=ManaCost.parse("{R}"))
        game, p1, _ = _setup_lorehold_with_library_top(spell, mana=2)
        # Accept the miracle offer.
        p1._script.appendleft(True)

        drawn = draw_card(game, p1)

        assert drawn is spell
        # The spell was cast: it left the hand and is on the stack as a spell.
        assert _on_stack(game, spell)
        assert not game.get_hand(p1).contains(spell)
        # The miracle {2} was paid from the pool (started with 2 generic mana).
        assert p1.mana_pool.total() == 0

    def test_first_drawn_sorcery_offered_miracle_cast_for_two(self) -> None:
        """A sorcery first-drawn under Lorehold is also castable for {2}."""
        spell = Sorcery(name="Reconstruct History", mana_cost=ManaCost.parse("{2}{R}"))
        game, p1, _ = _setup_lorehold_with_library_top(spell, mana=2)
        p1._script.appendleft(True)

        draw_card(game, p1)

        assert _on_stack(game, spell)
        assert not game.get_hand(p1).contains(spell)

    def test_miracle_cast_resolves_to_graveyard(self) -> None:
        """The miracle-cast spell resolves normally (instant → graveyard)."""
        spell = Instant(name="Lightning Bolt", mana_cost=ManaCost.parse("{R}"))
        game, p1, _ = _setup_lorehold_with_library_top(spell, mana=2)
        p1._script.appendleft(True)

        draw_card(game, p1)
        # Resolve the spell off the stack.
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        assert game.get_graveyard(p1).contains(spell)
        assert not game.get_hand(p1).contains(spell)

    def test_declining_keeps_first_drawn_spell_in_hand(self) -> None:
        """"You MAY cast" — declining leaves the drawn instant in hand, uncast."""
        spell = Instant(name="Lightning Bolt", mana_cost=ManaCost.parse("{R}"))
        game, p1, _ = _setup_lorehold_with_library_top(spell, mana=2)
        # Decline the miracle offer.
        p1._script.appendleft(False)

        draw_card(game, p1)

        assert game.stack.is_empty()
        assert game.get_hand(p1).contains(spell)
        # Declining costs no mana.
        assert p1.mana_pool.total() == 2

    def test_second_draw_same_turn_gets_no_miracle_window(self) -> None:
        """Only the FIRST card drawn this turn gets a miracle window."""
        spell = Instant(name="Lightning Bolt", mana_cost=ManaCost.parse("{R}"))
        # cards_drawn_this_turn already 1 → this draw is the second of the turn.
        game, p1, _ = _setup_lorehold_with_library_top(
            spell, mana=2, drawn_already=1
        )
        # No miracle should be offered, so no yes/no answer is consumed. If the
        # window wrongly fired, the script would be exhausted and raise.

        draw_card(game, p1)

        # No miracle window: the spell stays in hand and the stack is empty.
        assert game.stack.is_empty()
        assert game.get_hand(p1).contains(spell)
        assert p1.mana_pool.total() == 2

    def test_first_drawn_creature_gets_no_miracle_window(self) -> None:
        """Miracle is granted only to instants/sorceries — not creatures."""
        creature = _vanilla_creature("Hill Giant")
        game, p1, _ = _setup_lorehold_with_library_top(creature, mana=2)
        # No miracle should be offered for a creature, so no answer is scripted.

        drawn = draw_card(game, p1)

        assert drawn is creature
        assert game.stack.is_empty()
        assert game.get_hand(p1).contains(creature)
        assert p1.mana_pool.total() == 2

    def test_no_lorehold_means_no_miracle_window(self) -> None:
        """Without Lorehold's grant, drawing an instant fires no miracle window."""
        spell = Instant(name="Lightning Bolt", mana_cost=ManaCost.parse("{R}"))
        game, p1, lorehold = _setup_lorehold_with_library_top(
            spell, on_battlefield=False, mana=2
        )
        assert lorehold is None
        # No grant registered, so no yes/no answer is scripted.

        draw_card(game, p1)

        assert game.stack.is_empty()
        assert game.get_hand(p1).contains(spell)
        assert p1.mana_pool.total() == 2
