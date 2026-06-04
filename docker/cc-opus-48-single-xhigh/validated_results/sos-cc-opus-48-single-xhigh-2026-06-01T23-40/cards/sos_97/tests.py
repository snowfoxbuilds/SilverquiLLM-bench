"""Tests for SOS 97 — Ral Zarek, Guest Lecturer.

Ral Zarek, Guest Lecturer is a Legendary Planeswalker — Ral, {1}{B}{B},
starting loyalty 3, with four loyalty abilities:

    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X
        is the number of coins that came up heads.

The engine's planeswalker contract (see ``cards/fdn/fdn_44`` / ``fdn_234``):
``get_loyalty_abilities()`` returns a list of ``LoyaltyAbility`` objects whose
``effect`` closures read ``pw.controller`` and, for targeted abilities, a
``pw._resolve_target`` (single) / ``pw._resolve_targets`` (list) attribute that
test code sets directly. These tests exercise each ability's ``effect`` in
isolation by setting those attributes and calling ``effect(game)``.

Surveil decisions are exercised through the controller's ``choose_yes_no``
channel. The −7 ultimate now has a deterministic engine surface: coin flips go
through ``engine.game.flip_coin`` / ``flip_coins`` whose result a test forces
via ``game._forced_coin_flips`` (a deque of booleans consumed from the front),
the resolved heads count is recorded on ``pw._last_heads``, and the enforced
turn-skipping is observed through ``Player.skipped_turns`` and the turn rotation
in ``GameState.advance_phase`` / ``_select_next_active_player``. Both previously
engine-blocked pieces (exact coin-flip X and enforced turn-skipping) are now
asserted directly — see ``TestRalZarekUltimateDeterministic``.
"""

from __future__ import annotations

from collections import deque

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_creature_card(name: str, mv: int, owner=None):
    """A creature *card* (not yet a permanent) with mana value ``mv``.

    Mana value is encoded entirely as generic mana so ``mana_cost.cmc == mv``.
    """
    card = Creature(
        name=name,
        base_power=1,
        base_toughness=1,
        mana_cost=ManaCost.parse(f"{{{mv}}}") if mv > 0 else ManaCost(),
        owner=owner,
        controller=owner,
    )
    card.card_types = {CardType.CREATURE}
    return card


def _vanilla_library_card(name: str, owner=None):
    """A plain card object usable as a library card for surveil tests."""
    card = Creature(name=name, base_power=2, base_toughness=2, owner=owner, controller=owner)
    card.card_types = {CardType.CREATURE}
    return card


def _ability_by_cost(pw, cost: int) -> LoyaltyAbility:
    """Return the single loyalty ability whose ``loyalty_cost`` equals *cost*."""
    matches = [a for a in pw.get_loyalty_abilities() if a.loyalty_cost == cost]
    assert len(matches) == 1, f"expected exactly one ability with cost {cost}"
    return matches[0]


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestRalZarekProperties:
    """Static card data should match the SOS 97 spec."""

    def test_is_planeswalker(self) -> None:
        assert isinstance(RalZarekGuestLecturer(owner=None), Planeswalker)

    def test_card_type_is_planeswalker(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert CardType.PLANESWALKER in card.card_types

    def test_name(self) -> None:
        assert RalZarekGuestLecturer(owner=None).name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_is_legendary(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_ral_subtype(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert "Ral" in card.subtypes

    def test_starting_loyalty_is_three(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.starting_loyalty == 3

    def test_current_loyalty_initialised_to_three(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.loyalty == 3


# ---------------------------------------------------------------------------
# Loyalty ability declaration
# ---------------------------------------------------------------------------

class TestRalZarekLoyaltyAbilityShape:
    """get_loyalty_abilities() declares the four printed abilities."""

    def test_returns_four_abilities(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        assert len(abilities) == 4

    def test_all_are_loyalty_abilities(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        for a in abilities:
            assert isinstance(a, LoyaltyAbility)

    def test_loyalty_costs_match_printed_values(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        costs = sorted(a.loyalty_cost for a in abilities)
        assert costs == [-7, -2, -1, 1]


# ---------------------------------------------------------------------------
# +1: Surveil 2
# ---------------------------------------------------------------------------

class TestRalZarekSurveil:
    """+1 surveils 2: look at top two cards of the controller's library, put
    any number into the graveyard and the rest back on top.

    The per-card keep/bin decision is taken via the controller's
    ``choose_yes_no`` (the codebase's standard "you may" decision channel).
    """

    def test_surveil_keeping_both_leaves_library_size_unchanged(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        top = _vanilla_library_card("Top Card", owner=p1)
        second = _vanilla_library_card("Second Card", owner=p1)
        # Library bottom -> top: [filler, second, top]; top of library is last.
        filler = _vanilla_library_card("Filler", owner=p1)
        lib = p1.zones[Zone.LIBRARY]
        for c in (filler, second, top):
            lib.add(c)

        before_lib = len(lib)
        before_gy = len(p1.zones[Zone.GRAVEYARD])

        # Decline to bin either of the surveilled cards.
        p1._script.extend([False, False])
        _ability_by_cost(pw, +1).effect(game)

        assert len(lib) == before_lib
        assert len(p1.zones[Zone.GRAVEYARD]) == before_gy

    def test_surveil_binning_both_moves_them_to_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        top = _vanilla_library_card("Top Card", owner=p1)
        second = _vanilla_library_card("Second Card", owner=p1)
        filler = _vanilla_library_card("Filler", owner=p1)
        lib = p1.zones[Zone.LIBRARY]
        for c in (filler, second, top):
            lib.add(c)

        # Bin both of the surveilled (top two) cards.
        p1._script.extend([True, True])
        _ability_by_cost(pw, +1).effect(game)

        gy_objs = p1.zones[Zone.GRAVEYARD].get_all()
        assert top in gy_objs
        assert second in gy_objs
        # The filler underneath the top two is untouched.
        assert lib.contains(filler)

    def test_surveil_never_moves_cards_to_hand(self) -> None:
        """Surveil only touches library/graveyard — never hand."""
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        for i in range(2):
            p1.zones[Zone.LIBRARY].add(_vanilla_library_card(f"C{i}", owner=p1))

        before_hand = len(p1.zones[Zone.HAND])
        p1._script.extend([False, False])
        _ability_by_cost(pw, +1).effect(game)
        assert len(p1.zones[Zone.HAND]) == before_hand

    def test_surveil_with_empty_library_is_a_safe_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        # Empty library — surveil 2 must not raise.
        _ability_by_cost(pw, +1).effect(game)
        assert len(p1.zones[Zone.LIBRARY]) == 0


# ---------------------------------------------------------------------------
# −1: Any number of target players each discard a card
# ---------------------------------------------------------------------------

class TestRalZarekDiscard:
    """−1 makes each targeted player discard a card."""

    def test_targeted_opponent_discards_a_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        opp_card = _vanilla_library_card("Opp Hand Card", owner=p2)
        set_board_state(game, 1, hand=[opp_card])

        before = len(p2.zones[Zone.HAND])
        pw._resolve_targets = [p2]
        # If the implementation prompts which card to discard, give it the card.
        p2._script.appendleft(opp_card)
        _ability_by_cost(pw, -1).effect(game)

        assert len(p2.zones[Zone.HAND]) == before - 1
        assert p2.zones[Zone.GRAVEYARD].contains(opp_card)

    def test_both_targeted_players_each_discard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        c1 = _vanilla_library_card("P1 Hand Card", owner=p1)
        c2 = _vanilla_library_card("P2 Hand Card", owner=p2)
        set_board_state(game, 0, hand=[c1])
        set_board_state(game, 1, hand=[c2])

        pw._resolve_targets = [p1, p2]
        p1._script.appendleft(c1)
        p2._script.appendleft(c2)
        _ability_by_cost(pw, -1).effect(game)

        assert len(p1.zones[Zone.HAND]) == 0
        assert len(p2.zones[Zone.HAND]) == 0

    def test_no_targets_chosen_is_a_noop(self) -> None:
        """"Any number" permits zero targets — nobody discards."""
        game = create_game()
        p1, p2 = game.players
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        c2 = _vanilla_library_card("P2 Hand Card", owner=p2)
        set_board_state(game, 1, hand=[c2])

        pw._resolve_targets = []
        _ability_by_cost(pw, -1).effect(game)
        # Untargeted player keeps their card.
        assert p2.zones[Zone.HAND].contains(c2)

    def test_targeted_player_with_empty_hand_is_safe(self) -> None:
        game = create_game()
        p1, p2 = game.players
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 1, hand=[])
        pw._resolve_targets = [p2]
        # Must not raise even though the player has nothing to discard.
        _ability_by_cost(pw, -1).effect(game)
        assert len(p2.zones[Zone.GRAVEYARD]) == 0


# ---------------------------------------------------------------------------
# −2: Return target creature card with mana value 3 or less from your
#     graveyard to the battlefield
# ---------------------------------------------------------------------------

class TestRalZarekReanimate:
    """−2 returns a low-mana-value creature card from the controller's own
    graveyard to the battlefield."""

    def test_returns_mv3_creature_to_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        target = _make_creature_card("Goblin", mv=3, owner=p1)
        set_board_state(game, 0, graveyard=[target])

        pw._resolve_target = target
        _ability_by_cost(pw, -2).effect(game)

        assert game.get_battlefield(p1).contains(target)
        assert not p1.zones[Zone.GRAVEYARD].contains(target)

    def test_zero_mana_value_creature_is_legal(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        target = _make_creature_card("Ornithopter", mv=0, owner=p1)
        set_board_state(game, 0, graveyard=[target])

        pw._resolve_target = target
        _ability_by_cost(pw, -2).effect(game)
        assert game.get_battlefield(p1).contains(target)

    def test_mana_value_four_creature_is_not_returned(self) -> None:
        """Mana value 4 exceeds the "3 or less" filter — the effect must not
        move the card to the battlefield."""
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        target = _make_creature_card("Big Beast", mv=4, owner=p1)
        set_board_state(game, 0, graveyard=[target])

        pw._resolve_target = target
        _ability_by_cost(pw, -2).effect(game)

        assert not game.get_battlefield(p1).contains(target)

    def test_noncreature_card_is_not_returned(self) -> None:
        """Only creature cards are legal targets."""
        from engine.card import Sorcery

        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)

        sorc = Sorcery(name="Cheap Sorcery", mana_cost=ManaCost.parse("{1}"), owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[sorc])

        pw._resolve_target = sorc
        _ability_by_cost(pw, -2).effect(game)
        assert not game.get_battlefield(p1).contains(sorc)

    def test_no_target_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = _make_creature_card("Goblin", mv=2, owner=p1)
        set_board_state(game, 0, graveyard=[target])
        # No _resolve_target set -> nothing happens.
        _ability_by_cost(pw, -2).effect(game)
        assert p1.zones[Zone.GRAVEYARD].contains(target)


# ---------------------------------------------------------------------------
# −7: Flip five coins. Target opponent skips their next X turns.
# ---------------------------------------------------------------------------

class TestRalZarekUltimate:
    """−7's structural contract: it exists at loyalty cost −7 and runs without
    raising when a target opponent is supplied. The randomised X (heads count)
    and enforced turn-skipping are asserted deterministically in
    ``TestRalZarekUltimateDeterministic`` below."""

    def test_ultimate_loyalty_cost_is_minus_seven(self) -> None:
        pw = RalZarekGuestLecturer(owner=None)
        ability = _ability_by_cost(pw, -7)
        assert ability.loyalty_cost == -7

    def test_ultimate_runs_with_target_opponent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = p2
        # Five coin flips + skip scheduling must execute without raising.
        _ability_by_cost(pw, -7).effect(game)

    def test_ultimate_with_no_target_is_a_safe_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        # No target -> must not raise and must not break game state.
        _ability_by_cost(pw, -7).effect(game)
        assert game.is_game_over is False


# ---------------------------------------------------------------------------
# −7 (deterministic): X == heads, head-count parametrisation, enforced skips,
#                     and the no-target no-op.
# ---------------------------------------------------------------------------

def _force_turn_wrap(game) -> None:
    """Drive the turn rotation forward by exactly one turn boundary.

    Jumps the game to the final step of the current turn (ENDING/CLEANUP) and
    calls ``advance_phase`` once. ``advance_phase`` only rotates the active
    player when it wraps past the last step of the sequence, so this exercises
    ``_select_next_active_player`` (and therefore the ``skipped_turns`` skip
    logic) deterministically without running full turns / priority loops.
    """
    game.phase = Phase.ENDING
    game.step = Step.CLEANUP
    game.advance_phase()


class TestRalZarekUltimateDeterministic:
    """−7 with the deterministic coin-flip + skip-turn surface in place.

    Coin flips are forced via ``game._forced_coin_flips`` (a deque of booleans
    consumed from the front; truthy == heads). The resolved heads count is read
    from ``pw._last_heads`` and the scheduled skips from the target opponent's
    ``Player.skipped_turns``. Turn enforcement is observed through
    ``GameState.advance_phase`` / ``_select_next_active_player``.
    """

    def test_x_equals_heads_count_and_schedules_that_many_skips(self) -> None:
        """Forced sequence with 3 heads -> X == 3, opponent skips 3 turns."""
        game = create_game()
        p1, p2 = game.players
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = p2

        # 5 flips, exactly 3 heads (truthy values).
        game._forced_coin_flips = deque([True, False, True, True, False])
        _ability_by_cost(pw, -7).effect(game)

        assert pw._last_heads == 3
        assert p2.skipped_turns == 3

    def test_all_heads_schedules_five_skips(self) -> None:
        """All five coins heads -> X == 5."""
        game = create_game()
        p1, p2 = game.players
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = p2

        game._forced_coin_flips = deque([True, True, True, True, True])
        _ability_by_cost(pw, -7).effect(game)

        assert pw._last_heads == 5
        assert p2.skipped_turns == 5

    def test_all_tails_schedules_no_skips(self) -> None:
        """All five coins tails -> X == 0, opponent skips nothing."""
        game = create_game()
        p1, p2 = game.players
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = p2

        game._forced_coin_flips = deque([False, False, False, False, False])
        _ability_by_cost(pw, -7).effect(game)

        assert pw._last_heads == 0
        assert p2.skipped_turns == 0

    def test_skip_counter_is_additive_across_two_ultimates(self) -> None:
        """A second −7 adds to (does not overwrite) the existing skip count."""
        game = create_game()
        p1, p2 = game.players
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = p2

        game._forced_coin_flips = deque([True, True, False, False, False])  # 2
        _ability_by_cost(pw, -7).effect(game)
        assert p2.skipped_turns == 2

        game._forced_coin_flips = deque([True, False, False, False, False])  # 1
        _ability_by_cost(pw, -7).effect(game)
        assert pw._last_heads == 1
        assert p2.skipped_turns == 3

    def test_opponent_is_not_active_while_skip_counter_positive(self) -> None:
        """While the opponent owes skips they never become the active player;
        the counter decrements once per skipped turn slot."""
        game = create_game()
        p1, p2 = game.players  # p1 == seat 0 (active), p2 == seat 1
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = p2

        # Force exactly 2 heads -> opponent skips their next 2 turns.
        game._forced_coin_flips = deque([True, True, False, False, False])
        _ability_by_cost(pw, -7).effect(game)
        assert p2.skipped_turns == 2

        # Turn 1: seat 0 active. The next two turn boundaries would each hand
        # seat 1 a turn, but both are skipped -> seat 0 stays active and the
        # counter decrements each time.
        assert game.active_player_index == 0

        _force_turn_wrap(game)
        assert game.active_player_index == 0          # p2's turn was skipped
        assert p2.skipped_turns == 1

        _force_turn_wrap(game)
        assert game.active_player_index == 0          # second skip consumed
        assert p2.skipped_turns == 0

    def test_opponent_takes_a_normal_turn_after_skips_are_exhausted(self) -> None:
        """Once the skip counter reaches 0 the opponent resumes normal turns."""
        game = create_game()
        p1, p2 = game.players
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = p2

        game._forced_coin_flips = deque([True, True, False, False, False])  # 2
        _ability_by_cost(pw, -7).effect(game)
        assert p2.skipped_turns == 2

        # Burn through both skipped slots.
        _force_turn_wrap(game)
        _force_turn_wrap(game)
        assert p2.skipped_turns == 0
        assert game.active_player_index == 0

        # The next boundary is no longer skipped: seat 1 (the opponent) finally
        # becomes the active player.
        _force_turn_wrap(game)
        assert game.active_player_index == 1
        assert p2.skipped_turns == 0

    def test_no_target_flips_but_schedules_no_skip(self) -> None:
        """With no chosen target the −7 still flips (records X) but nobody's
        skip counter increases — a safe no-op on the skip side."""
        game = create_game()
        p1, p2 = game.players
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        # Deliberately no pw._resolve_target.

        game._forced_coin_flips = deque([True, True, False, True, False])  # 3
        _ability_by_cost(pw, -7).effect(game)

        # Flips still happened and were recorded.
        assert pw._last_heads == 3
        # But nobody was scheduled to skip.
        assert p1.skipped_turns == 0
        assert p2.skipped_turns == 0
