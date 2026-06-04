"""Tests for SOS 245 — Witherbloom, the Balancer.

Witherbloom is a {6}{B}{G} Legendary Elder Dragon (5/5) with:

* **Affinity for creatures** — "This spell costs {1} less to cast for each
  creature you control." (a self cost reduction)
* **Flying, deathtouch** (evergreen keywords)
* "Instant and sorcery spells you cast have affinity for creatures." (a static
  grant of the same affinity to the controller's instant/sorcery spells while
  Witherbloom is on the battlefield)

The cost-reduction model the engine exposes is ``CardImpl.cost_reduction(game)``
(the generic reduction for casting that card), consumed by
``engine.casting.get_cost_reduction`` which clamps the result to the generic
portion of the mana cost. These tests pin:

* Static card data (name, cost, types, P/T, supertype, subtypes, keywords,
  colors).
* Witherbloom's own Affinity for creatures (counts creatures you control,
  including itself; clamped to generic; opponent creatures excluded).
* The granted affinity to the controller's instant/sorcery spells, observed
  through the real ``cast_spell`` pipeline (the spell's ``mana_spent`` is
  reduced by the number of creatures the controller controls) and through the
  canonical ``get_cost_reduction`` query. Scope: only the controller's
  instant/sorcery spells, only while Witherbloom is on the battlefield.

TDD red phase — the stub is empty, so every assertion below is expected to fail
until Witherbloom is implemented.
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell as engine_cast_spell, get_cost_reduction
from engine.types import (
    CardType,
    Color,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _witherbloom(owner=None, controller=None) -> WitherbloomTheBalancer:
    return WitherbloomTheBalancer(owner=owner, controller=controller)


def _bear(name: str = "Grizzly Bears", power: int = 2, toughness: int = 2) -> Creature:
    return Creature(name=name, base_power=power, base_toughness=toughness)


def _instant(name: str = "Big Instant", cost: str = "{6}{B}") -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse(cost))


def _sorcery(name: str = "Big Sorcery", cost: str = "{6}{G}") -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse(cost))


def _ready_for_cast(game) -> None:
    """Put the game in a state where player 0 may cast a spell."""
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------

class TestWitherbloomProperties:
    """Static characteristics must match the SOS 245 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(_witherbloom(), Creature)

    def test_name(self) -> None:
        assert _witherbloom().name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        assert _witherbloom().mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_power_toughness(self) -> None:
        card = _witherbloom()
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in _witherbloom().supertypes

    def test_elder_dragon_subtypes(self) -> None:
        subtypes = _witherbloom().subtypes
        assert "Dragon" in subtypes
        assert "Elder" in subtypes

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in _witherbloom().keywords

    def test_has_deathtouch(self) -> None:
        assert Keyword.DEATHTOUCH in _witherbloom().keywords

    def test_is_black_and_green(self) -> None:
        colors = _witherbloom().colors
        assert Color.BLACK in colors
        assert Color.GREEN in colors

    def test_not_other_colors(self) -> None:
        colors = _witherbloom().colors
        assert Color.WHITE not in colors
        assert Color.BLUE not in colors
        assert Color.RED not in colors


# ---------------------------------------------------------------------------
# Witherbloom's own Affinity for creatures (self cost reduction)
# ---------------------------------------------------------------------------

class TestWitherbloomSelfAffinity:
    """Witherbloom costs {1} less for each creature you control."""

    def test_no_creatures_no_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _witherbloom(owner=p1, controller=p1)
        # Empty battlefield -> no reduction.
        assert card.cost_reduction(game) == 0

    def test_reduction_counts_creatures_you_control(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _witherbloom(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[_bear(), _bear("Bear Two")])
        # Two other creatures you control -> reduction of 2.
        card.controller = p1
        assert card.cost_reduction(game) == 2

    def test_reduction_counts_itself_when_on_battlefield(self) -> None:
        """While Witherbloom is on the battlefield with one other creature,
        the affinity reduction counts both creatures you control."""
        game = create_game()
        p1 = game.players[0]
        card = _witherbloom(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card, _bear()])
        assert card.cost_reduction(game) == 2

    def test_opponent_creatures_excluded(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _witherbloom(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[_bear()])
        set_board_state(game, 1, battlefield=[_bear("Enemy Bear"), _bear("Enemy Two")])
        card.controller = p1
        # Only the single creature you control counts.
        assert card.cost_reduction(game) == 1

    def test_noncreature_permanents_not_counted(self) -> None:
        """Affinity for *creatures* must not count noncreature permanents."""
        from engine.card import CardImpl

        game = create_game()
        p1 = game.players[0]
        card = _witherbloom(owner=p1, controller=p1)
        artifact = CardImpl(
            name="Some Artifact",
            mana_cost=ManaCost.parse("{2}"),
            card_types={CardType.ARTIFACT},
        )
        set_board_state(game, 0, battlefield=[_bear(), artifact])
        card.controller = p1
        # Only the one creature counts; the artifact does not.
        assert card.cost_reduction(game) == 1

    def test_get_cost_reduction_clamped_to_generic(self) -> None:
        """The reduction can never reduce below the generic portion; with more
        creatures than the {6} generic, the engine clamps the reduction to 6."""
        game = create_game()
        p1 = game.players[0]
        card = _witherbloom(owner=p1, controller=p1)
        creatures = [_bear(f"Bear {i}") for i in range(8)]
        set_board_state(game, 0, battlefield=[card] + creatures)
        # 9 creatures controlled, but generic is only {6}.
        reduction = get_cost_reduction(game, card, p1)
        assert reduction == 6

    def test_get_cost_reduction_matches_creature_count_under_generic(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _witherbloom(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card, _bear(), _bear("Bear Two")])
        # 3 creatures controlled, well under {6} generic -> reduction of 3.
        assert get_cost_reduction(game, card, p1) == 3


# ---------------------------------------------------------------------------
# Granted affinity — instant/sorcery spells you cast
# ---------------------------------------------------------------------------

class TestWitherbloomGrantedAffinity:
    """Instant and sorcery spells you cast have affinity for creatures while
    Witherbloom is on the battlefield."""

    def test_instant_cost_reduced_through_real_cast(self) -> None:
        """Casting your own instant while Witherbloom + creatures are out pays
        less mana (mana_spent reflects the affinity reduction)."""
        game = create_game()
        p1 = game.players[0]
        wither = _witherbloom(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wither, _bear(), _bear("Bear Two")])
        _ready_for_cast(game)

        spell = _instant(cost="{6}{B}")  # generic 6, one black pip
        set_board_state(game, 0, hand=[spell])
        # Plenty of mana so the cast always succeeds regardless of reduction.
        p1.mana_pool.add(ManaType.BLACK, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 10)

        engine_cast_spell(game, p1, spell)

        # Three creatures controlled -> {6} generic reduced by 3 -> pays 3+1 = 4.
        assert spell.mana_spent == 4

    def test_sorcery_cost_reduced_through_real_cast(self) -> None:
        """Sorceries you cast also gain affinity for creatures."""
        game = create_game()
        p1 = game.players[0]
        wither = _witherbloom(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wither, _bear()])
        _ready_for_cast(game)

        spell = _sorcery(cost="{6}{G}")
        set_board_state(game, 0, hand=[spell])
        p1.mana_pool.add(ManaType.GREEN, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 10)

        engine_cast_spell(game, p1, spell)

        # Two creatures controlled (Witherbloom + bear) -> 6 - 2 = 4 generic;
        # plus the {G} pip -> 5 mana spent.
        assert spell.mana_spent == 5

    def test_granted_reduction_visible_via_get_cost_reduction(self) -> None:
        """The granted affinity is visible through the canonical
        get_cost_reduction query for a controller instant while Witherbloom is
        on the battlefield."""
        game = create_game()
        p1 = game.players[0]
        wither = _witherbloom(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wither, _bear(), _bear("Bear Two")])

        spell = _instant(cost="{6}{B}")
        spell.owner = p1
        # 3 creatures controlled -> reduction of 3.
        assert get_cost_reduction(game, spell, p1) == 3

    def test_no_reduction_without_witherbloom_on_battlefield(self) -> None:
        """Without Witherbloom on the battlefield, a plain instant gets no
        affinity reduction even with creatures present."""
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[_bear(), _bear("Bear Two")])

        spell = _instant(cost="{6}{B}")
        spell.owner = p1
        assert get_cost_reduction(game, spell, p1) == 0

    def test_opponent_spell_not_granted_affinity(self) -> None:
        """Witherbloom only grants affinity to *your* instant/sorcery spells.
        An opponent's instant gets no reduction from your Witherbloom."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        wither = _witherbloom(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wither, _bear(), _bear("Bear Two")])
        # Opponent also controls creatures, but they don't matter here.
        set_board_state(game, 1, battlefield=[_bear("Enemy Bear")])

        opp_spell = _instant(name="Opp Instant", cost="{6}{B}")
        opp_spell.owner = p2
        # The opponent's spell is not "a spell you cast" from Witherbloom's
        # controller's perspective, so no reduction.
        assert get_cost_reduction(game, opp_spell, p2) == 0

    def test_creature_spell_not_granted_affinity(self) -> None:
        """The grant is restricted to instant and sorcery spells — a creature
        spell you cast gets no affinity from Witherbloom."""
        game = create_game()
        p1 = game.players[0]
        wither = _witherbloom(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wither, _bear(), _bear("Bear Two")])

        creature_spell = Creature(
            name="Vanilla Beast",
            mana_cost=ManaCost.parse("{6}{G}"),
            base_power=4,
            base_toughness=4,
        )
        creature_spell.owner = p1
        assert get_cost_reduction(game, creature_spell, p1) == 0

    def test_granted_reduction_clamped_to_generic(self) -> None:
        """The granted affinity is also clamped to the spell's generic cost."""
        game = create_game()
        p1 = game.players[0]
        wither = _witherbloom(owner=p1, controller=p1)
        creatures = [_bear(f"Bear {i}") for i in range(5)]
        set_board_state(game, 0, battlefield=[wither] + creatures)

        # Generic of {2}{B} is only 2, but 6 creatures are controlled.
        spell = _instant(cost="{2}{B}")
        spell.owner = p1
        assert get_cost_reduction(game, spell, p1) == 2
