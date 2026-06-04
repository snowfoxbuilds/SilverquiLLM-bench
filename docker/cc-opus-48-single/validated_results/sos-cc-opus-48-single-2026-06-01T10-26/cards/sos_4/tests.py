"""Tests for SOS 4 — Together as One.

Together as One ({6} Sorcery) has a single converge-driven resolution:

    Converge — Target player draws X cards, Together as One deals X damage
    to any target, and you gain X life, where X is the number of colors of
    mana spent to cast this spell.

The engine records the colors of mana spent during cost payment on the card
as ``colors_spent`` (a list of :class:`engine.mana.Color`; see
``engine.casting`` line ~229 and FDN 205 for the converge precedent).  X is
the number of *distinct* colors in that list.  Because the printed cost is a
pure ``{6}`` generic cost, the colors actually spent (and therefore X) depend
entirely on which mana the player used to pay — X ranges from 0 to 5.

These tests cover:

1. **Static card data** — name, mana cost, sorcery type.
2. **Targeting** — a target player (for the draw) and an "any target"
   (player or creature) for the damage.
3. **Converge X resolution** — draw X, deal X damage, gain X life, driven by
   the number of colors spent. Edge cases include X == 0 (no mana of any
   color spent) and X == 5 (all five colors).

These are TDD red-phase tests: the stub at ``card_impl.py`` is empty, so
everything here is expected to fail until the card is implemented.
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.mana import Color
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _vanilla_card(name: str = "Library Card") -> Sorcery:
    """A throwaway card to stock a library so draws have something to take."""
    return Sorcery(name=name, mana_cost=ManaCost.parse("{1}"))


def _vanilla_creature(name: str = "Grizzly Bears", toughness: int = 4) -> Creature:
    """A vanilla creature usable as a damage target."""
    return Creature(name=name, base_power=2, base_toughness=toughness)


def _fill_library(game: Any, player: Any, count: int) -> list[Any]:
    """Put *count* distinct cards into *player*'s library and return them."""
    cards = [_vanilla_card(f"Lib{i}") for i in range(count)]
    library = game.get_library(player)
    for obj in library.get_all():
        library.remove(obj)
    for c in cards:
        c.owner = player
        c.controller = player
        library.add(c)
    return cards


def _resolve_with_colors(game, spell, *, colors, targets) -> None:
    """Set converge colors + chosen targets on *spell* and resolve it.

    ``colors`` mirrors what the engine writes during payment: a list of
    :class:`Color`. ``targets`` is the resolved target list (player first
    for the draw, then the damage target).
    """
    spell.colors_spent = list(colors)
    spell.chosen_targets = list(targets)
    spell.on_resolve(game)


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)
        assert CardType.SORCERY in card.card_types

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost_is_six_generic(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")

    def test_not_a_creature(self) -> None:
        assert CardType.CREATURE not in TogetherAsOne(owner=None).card_types

    def test_no_power_toughness(self) -> None:
        card = TogetherAsOne(owner=None)
        assert not isinstance(card, Creature)


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------


class TestTogetherAsOneTargeting:
    """get_targets() advertises a target player and an 'any target'."""

    def test_returns_two_target_requirements(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TogetherAsOne(owner=p1, controller=p1)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert all(isinstance(r, TargetRequirement) for r in reqs)

    def test_player_target_accepts_a_player(self) -> None:
        """One requirement must accept a player (the 'target player draws')."""
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne(owner=p1, controller=p1)
        reqs = card.get_targets(game)
        # At least one requirement must accept a player object.
        assert any(r.filter_fn(p1) for r in reqs)
        assert any(r.filter_fn(p2) for r in reqs)

    def test_any_target_accepts_player_and_creature(self) -> None:
        """The damage target is 'any target' — a player or a creature."""
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne(owner=p1, controller=p1)
        reqs = card.get_targets(game)
        creature = _vanilla_creature()
        creature.owner = p2
        creature.controller = p2
        game.get_battlefield(p2).add(creature)
        # Some requirement accepts the creature as a legal damage target.
        assert any(r.filter_fn(creature) for r in reqs)

    def test_any_target_rejects_non_creature_permanent(self) -> None:
        """'any target' is a player, planeswalker, creature, or battle — not a
        plain non-creature permanent like a vanilla enchantment-less land."""
        from engine.card import Land

        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne(owner=p1, controller=p1)
        reqs = card.get_targets(game)
        land = Land(name="Forest")
        land.owner = p2
        land.controller = p2
        game.get_battlefield(p2).add(land)
        # No requirement should accept a land as an "any target".
        assert all(r.filter_fn(land) is False for r in reqs)


# ---------------------------------------------------------------------------
# Converge X resolution
# ---------------------------------------------------------------------------


class TestTogetherAsOneConvergeResolution:
    """on_resolve uses X = number of distinct colors of mana spent to drive
    draw count, damage dealt, and life gained."""

    def test_two_colors_draws_two_deals_two_gains_two(self) -> None:
        game = create_game(player1_life=20)
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        _fill_library(game, p1, 5)
        hand_before = len(game.get_hand(p1).get_all())
        opp_life_before = p2.life

        # X = 2 (e.g. paid {6} with two white + ... + two blue etc.)
        _resolve_with_colors(
            game, spell,
            colors=[Color.WHITE, Color.BLUE],
            targets=[p1, p2],
        )

        # Target player (p1) drew X = 2 cards.
        assert len(game.get_hand(p1).get_all()) - hand_before == 2
        # Together as One dealt X = 2 damage to the chosen any-target (p2).
        assert opp_life_before - p2.life == 2
        # Controller gained X = 2 life.
        assert p1.life == 22

    def test_x_counts_distinct_colors_not_pips(self) -> None:
        """Duplicate colors do not inflate X — X is distinct colors."""
        game = create_game(player1_life=20)
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        _fill_library(game, p1, 5)
        hand_before = len(game.get_hand(p1).get_all())
        opp_life_before = p2.life

        # Three red pips spent — still only ONE color.
        _resolve_with_colors(
            game, spell,
            colors=[Color.RED, Color.RED, Color.RED],
            targets=[p1, p2],
        )

        assert len(game.get_hand(p1).get_all()) - hand_before == 1
        assert opp_life_before - p2.life == 1
        assert p1.life == 21

    def test_five_colors_draws_five_deals_five_gains_five(self) -> None:
        game = create_game(player1_life=20)
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        _fill_library(game, p1, 10)
        hand_before = len(game.get_hand(p1).get_all())
        opp_life_before = p2.life

        _resolve_with_colors(
            game, spell,
            colors=[Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN],
            targets=[p1, p2],
        )

        assert len(game.get_hand(p1).get_all()) - hand_before == 5
        assert opp_life_before - p2.life == 5
        assert p1.life == 25

    def test_zero_colors_is_full_noop(self) -> None:
        """X == 0 (only generic/colorless mana spent): draw 0, deal 0, gain 0."""
        game = create_game(player1_life=20)
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        _fill_library(game, p1, 5)
        hand_before = len(game.get_hand(p1).get_all())
        opp_life_before = p2.life

        _resolve_with_colors(game, spell, colors=[], targets=[p1, p2])

        assert len(game.get_hand(p1).get_all()) == hand_before
        assert p2.life == opp_life_before
        assert p1.life == 20

    def test_damage_to_creature_target(self) -> None:
        """The 'any target' damage can be dealt to a creature (marks damage)."""
        game = create_game(player1_life=20)
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        _fill_library(game, p1, 5)
        creature = _vanilla_creature(toughness=4)
        creature.owner = p2
        creature.controller = p2
        game.get_battlefield(p2).add(creature)

        _resolve_with_colors(
            game, spell,
            colors=[Color.WHITE, Color.BLUE, Color.BLACK],
            targets=[p1, creature],
        )

        # X = 3 damage marked on the creature; opponent's life untouched.
        assert creature.damage_marked == 3
        assert p2.life == 20

    def test_life_gain_credited_to_controller_not_target_player(self) -> None:
        """'you gain X life' — the controller gains life, even when the draw
        target player is the opponent."""
        game = create_game(player1_life=20, player2_life=20)
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        _fill_library(game, p2, 5)
        p2_hand_before = len(game.get_hand(p2).get_all())

        # Target player for the draw is the OPPONENT; damage target is p2 too.
        _resolve_with_colors(
            game, spell,
            colors=[Color.RED, Color.GREEN],
            targets=[p2, p2],
        )

        # Opponent draws X = 2.
        assert len(game.get_hand(p2).get_all()) - p2_hand_before == 2
        # Controller (p1) — not the target player — gains the life.
        assert p1.life == 22

    def test_target_player_draws_not_controller(self) -> None:
        """The draw goes to the chosen target player, not necessarily the
        controller."""
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        _fill_library(game, p2, 5)
        p1_hand_before = len(game.get_hand(p1).get_all())
        p2_hand_before = len(game.get_hand(p2).get_all())

        _resolve_with_colors(
            game, spell,
            colors=[Color.WHITE],
            targets=[p2, p1],
        )

        # p2 was the target player → p2 drew; p1's hand unchanged by the draw.
        assert len(game.get_hand(p2).get_all()) - p2_hand_before == 1
        assert len(game.get_hand(p1).get_all()) == p1_hand_before


class TestTogetherAsOneResolutionRobustness:
    """Resolution must not raise on missing/partial state (defensive checks)."""

    def test_resolve_with_no_colors_spent_attr_is_noop(self) -> None:
        """If colors_spent was never set (X defaults to 0), resolution is a
        harmless no-op rather than an error."""
        game = create_game(player1_life=20)
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        _fill_library(game, p1, 3)
        spell.chosen_targets = [p1, p2]
        # No colors_spent assigned at all.
        spell.on_resolve(game)
        assert p1.life == 20
        assert p2.life == 20

    def test_resolve_with_no_targets_does_not_raise(self) -> None:
        """With colors spent but no chosen targets, resolution must not raise;
        the controller's own life gain still applies (it is not targeted)."""
        game = create_game(player1_life=20)
        p1 = game.players[0]
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.WHITE, Color.BLUE]
        # chosen_targets unset.
        spell.on_resolve(game)
        # 'you gain X life' is not targeted, so it should still resolve.
        assert p1.life == 22
