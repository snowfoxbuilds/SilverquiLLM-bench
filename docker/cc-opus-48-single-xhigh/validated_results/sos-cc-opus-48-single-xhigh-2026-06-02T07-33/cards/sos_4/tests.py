"""Tests for SOS 4 — Together as One.

Together as One — {6} Sorcery (Converge):

    Converge — Target player draws X cards, Together as One deals X damage
    to any target, and you gain X life, where X is the number of colors of
    mana spent to cast this spell.

Contract derived from the oracle text and the engine's converge plumbing
(see ``engine/casting.py`` and ``cards/fdn/fdn_205``):

* X is the number of *distinct colors* of mana spent to cast the spell.
  The cast pipeline records this on the card as ``colors_spent`` — a list
  of :class:`engine.types.Color` produced from
  ``mana_pool.last_payment_colors``.  ``X == len(self.colors_spent)``.
* ``get_targets`` advertises two targets: a "target player" (for the draw)
  and an "any target" (player or creature) for the damage.
* On resolve the spell, in order, (1) makes the chosen target player draw
  X cards, (2) deals X damage to the any-target, and (3) makes the
  controller ("you") gain X life.
* All three clauses scale with the same X; X == 0 (e.g. paid entirely with
  generic mana) is a no-op for every clause.

Most tests drive ``on_resolve`` directly after setting ``chosen_targets``
and ``colors_spent`` (the established per-card test convention used by the
FDN reference tests).  One end-to-end test casts the spell through the real
pipeline so the engine itself populates ``colors_spent``.
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, Color, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stock_library(game: Any, player: Any, count: int) -> list[Any]:
    """Put *count* dummy creature cards in *player*'s library; return them."""
    library = game.get_library(player)
    # Clear whatever the game setup left there.
    for obj in library.get_all():
        library.remove(obj)
    cards = []
    for i in range(count):
        card = Creature(
            name=f"Library Card {i}",
            owner=player,
            controller=player,
            base_power=1,
            base_toughness=1,
        )
        library.add(card)
        cards.append(card)
    return cards


def _colors(*letters: str) -> list[Color]:
    """Build a ``colors_spent``-style list of Color values from letters."""
    mapping = {
        "W": Color.WHITE,
        "U": Color.BLUE,
        "B": Color.BLACK,
        "R": Color.RED,
        "G": Color.GREEN,
    }
    return [mapping[ch] for ch in letters]


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")

    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)
        assert CardType.SORCERY in TogetherAsOne(owner=None).card_types

    def test_not_a_creature(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.CREATURE not in card.card_types
        # No power/toughness — it is not a creature.
        assert not hasattr(card, "base_power") or not isinstance(card, Creature)


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------


class TestTogetherAsOneTargeting:
    """get_targets advertises a target player and an any-target."""

    def test_returns_two_target_requirements(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TogetherAsOne(owner=p1, controller=p1)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 2
        for req in reqs:
            assert isinstance(req, TargetRequirement)

    def test_player_target_accepts_a_player(self) -> None:
        """The first requirement (target player) must accept players."""
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne(owner=p1, controller=p1)
        player_req = card.get_targets(game)[0]
        assert player_req.filter_fn(p1) is True
        assert player_req.filter_fn(p2) is True

    def test_player_target_rejects_a_creature(self) -> None:
        """A creature is not a legal target for the "target player" clause."""
        game = create_game()
        p1 = game.players[0]
        card = TogetherAsOne(owner=p1, controller=p1)
        player_req = card.get_targets(game)[0]
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        assert player_req.filter_fn(bear) is False

    def test_any_target_accepts_player_and_creature(self) -> None:
        """The second requirement ("any target") accepts players and creatures."""
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne(owner=p1, controller=p1)
        any_req = card.get_targets(game)[1]
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        assert any_req.filter_fn(p2) is True
        assert any_req.filter_fn(bear) is True


# ---------------------------------------------------------------------------
# Converge value (X)
# ---------------------------------------------------------------------------


class TestTogetherAsOneConvergeValue:
    """X equals the number of distinct colors of mana spent."""

    def test_zero_colors_is_a_noop(self) -> None:
        """Paid with only generic/colorless mana → X == 0 → nothing happens."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, p2, 5)
        p1.life = 20
        p2.life = 20
        p2_hand_before = len(game.get_hand(p2).get_all())

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = []  # X == 0
        card.chosen_targets = [p2, p2]  # target player p2, damage to p2
        card.on_resolve(game)

        assert len(game.get_hand(p2).get_all()) == p2_hand_before  # no draw
        assert p2.life == 20  # no damage
        assert p1.life == 20  # no life gain

    def test_two_colors_yields_x_equals_two(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, p1, 5)
        p1.life = 20
        p2.life = 20

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = _colors("W", "U")  # two colors
        card.chosen_targets = [p1, p2]  # p1 draws, p2 takes damage
        before_hand = len(game.get_hand(p1).get_all())
        card.on_resolve(game)

        assert len(game.get_hand(p1).get_all()) == before_hand + 2
        assert p2.life == 18
        assert p1.life == 22

    def test_five_colors_yields_x_equals_five(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, p1, 5)
        p1.life = 20
        p2.life = 20

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = _colors("W", "U", "B", "R", "G")
        card.chosen_targets = [p1, p2]
        before_hand = len(game.get_hand(p1).get_all())
        card.on_resolve(game)

        assert len(game.get_hand(p1).get_all()) == before_hand + 5
        assert p2.life == 15
        assert p1.life == 25

    def test_duplicate_color_pips_count_once(self) -> None:
        """X counts distinct colors, not pips. WW => 1 color (engine dedupes,
        but the card must use the distinct-color count it is given)."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, p1, 3)
        p1.life = 20
        p2.life = 20

        card = TogetherAsOne(owner=p1, controller=p1)
        # last_payment_colors is already de-duplicated by the engine; a single
        # white color here represents paying WW (one distinct color).
        card.colors_spent = _colors("W")
        card.chosen_targets = [p1, p2]
        before_hand = len(game.get_hand(p1).get_all())
        card.on_resolve(game)

        assert len(game.get_hand(p1).get_all()) == before_hand + 1
        assert p2.life == 19
        assert p1.life == 21


# ---------------------------------------------------------------------------
# Draw clause
# ---------------------------------------------------------------------------


class TestTogetherAsOneDraw:
    """The chosen target player draws X cards."""

    def test_target_player_draws_x_cards(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lib_cards = _stock_library(game, p2, 4)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = _colors("B", "R", "G")  # X == 3
        card.chosen_targets = [p2, p1]  # p2 (opponent) draws
        card.on_resolve(game)

        hand = game.get_hand(p2).get_all()
        assert len(hand) == 3
        # The three top cards moved from library to hand.
        for drawn in lib_cards[-3:]:
            assert drawn in hand
        assert len(game.get_library(p2).get_all()) == 1

    def test_controller_can_be_the_drawing_player(self) -> None:
        """"Target player" may be the controller — they draw and gain life."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, p1, 4)
        p1.life = 20

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = _colors("W", "G")  # X == 2
        card.chosen_targets = [p1, p2]  # p1 draws and (as controller) gains life
        before_hand = len(game.get_hand(p1).get_all())
        card.on_resolve(game)

        assert len(game.get_hand(p1).get_all()) == before_hand + 2
        assert p1.life == 22


# ---------------------------------------------------------------------------
# Damage clause
# ---------------------------------------------------------------------------


class TestTogetherAsOneDamage:
    """Together as One deals X damage to the any-target."""

    def test_damage_to_player_reduces_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, p1, 3)
        p2.life = 20

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = _colors("R", "U", "G")  # X == 3
        card.chosen_targets = [p1, p2]  # damage to player p2
        card.on_resolve(game)

        assert p2.life == 17

    def test_damage_to_creature_marks_damage(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, p1, 3)

        bear = Creature(
            name="Grizzly Bears",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(bear)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = _colors("R", "W")  # X == 2
        card.chosen_targets = [p1, bear]  # damage to the bear
        assert bear.damage_marked == 0
        card.on_resolve(game)

        assert bear.damage_marked == 2

    def test_lethal_damage_to_creature_kills_it_via_sba(self) -> None:
        """X damage >= toughness destroys the creature once SBAs run."""
        from engine.state_based_actions import resolve_state_based_actions

        game = create_game()
        p1, p2 = game.players
        _stock_library(game, p1, 3)

        bear = Creature(
            name="Grizzly Bears",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(bear)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = _colors("R", "W", "B")  # X == 3 (>= toughness 2)
        card.chosen_targets = [p1, bear]
        card.on_resolve(game)
        resolve_state_based_actions(game)

        assert not game.get_battlefield(p2).contains(bear)
        assert game.get_graveyard(p2).contains(bear)


# ---------------------------------------------------------------------------
# Life-gain clause
# ---------------------------------------------------------------------------


class TestTogetherAsOneLifeGain:
    """The controller ("you") gains X life — not the target player."""

    def test_controller_gains_x_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, p2, 4)
        p1.life = 20

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = _colors("W", "U", "B", "R")  # X == 4
        card.chosen_targets = [p2, p2]  # p2 draws + takes damage
        card.on_resolve(game)

        assert p1.life == 24  # you (controller) gain 4 life

    def test_life_gain_goes_to_controller_not_target_player(self) -> None:
        """When an opponent is the target player, only the controller gains
        life (and the opponent does not gain life from this clause)."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, p2, 4)
        p1.life = 20
        p2.life = 20

        # Direct the damage at an opponent creature so neither player's life
        # is touched by the damage clause — isolating the lifegain clause.
        bear = Creature(
            name="Grizzly Bears",
            owner=p2,
            controller=p2,
            base_power=4,
            base_toughness=4,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(bear)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = _colors("W", "G")  # X == 2
        # p2 is the target player (draws); the damage target is the bear.
        card.chosen_targets = [p2, bear]
        card.on_resolve(game)

        # Only the controller gains life.
        assert p1.life == 22
        # Target player p2 does not gain life from the lifegain clause.
        assert p2.life == 20
        assert bear.damage_marked == 2


# ---------------------------------------------------------------------------
# Full cast pipeline (engine populates colors_spent)
# ---------------------------------------------------------------------------


class TestTogetherAsOneFullCast:
    """End-to-end cast where the engine records the colors of mana spent."""

    def test_cast_with_three_colors_drives_x_equals_three(self) -> None:
        from engine.casting import cast_spell as engine_cast_spell

        game = create_game()
        p1, p2 = game.players
        _stock_library(game, p1, 5)
        p1.life = 20
        p2.life = 20

        spell = TogetherAsOne(owner=p1, controller=p1)
        # {6}: pay with three distinct colors + three colorless => X == 3.
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={
                ManaType.WHITE: 1,
                ManaType.BLUE: 1,
                ManaType.RED: 1,
                ManaType.COLORLESS: 3,
            },
        )

        # Sorcery-speed timing for the engine cast.
        from engine.types import Phase

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        # Script the two target choices: target player p1 (draws), any-target p2.
        p1._script.appendleft(p2)
        p1._script.appendleft(p1)

        before_hand = len(game.get_hand(p1).get_all()) - 1  # minus the spell itself
        engine_cast_spell(game, p1, spell)

        # Resolve the spell off the stack.
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert len(game.get_hand(p1).get_all()) == before_hand + 3
        assert p2.life == 17
        assert p1.life == 23
