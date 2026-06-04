"""Tests for SOS 4 — Together as One.

Together as One — ``{6}`` Sorcery (colorless).

    Converge — Target player draws X cards, Together as One deals X damage
    to any target, and you gain X life, where X is the number of colors of
    mana spent to cast this spell.

X is driven by the converge mechanic: the cast pipeline records the distinct
colors of mana spent on the card as ``colors_spent`` (a list of
:class:`engine.types.Color`).  The card's ``on_resolve`` reads that value to
compute X and then applies three effects in one resolution:

1. The chosen *target player* draws X cards.
2. The spell deals X damage to the chosen *any target* (creature/player).
3. The controller ("you") gains X life.

These tests follow the FDN converge reference (``fdn_205``) and the targeting
reference (``fdn_13``): static card data is verified up front, and the resolve
behaviour is exercised in isolation by setting ``colors_spent`` and
``chosen_targets`` directly, plus one end-to-end cast through the real
pipeline so the converge wiring is grounded in real mana payment.
"""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import (
    CardType,
    Color,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state, cast_spell


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bear(name: str = "Grizzly Bears", power: int = 2, toughness: int = 2) -> Creature:
    """A vanilla creature usable as a damage target."""
    c = Creature(name=name, base_power=power, base_toughness=toughness)
    c.card_types = {CardType.CREATURE}
    return c


def _stock_library(game, player_index: int, count: int) -> list[Creature]:
    """Put *count* distinct dummy cards into a player's library, return them."""
    cards = [_bear(name=f"Lib{player_index}-{i}") for i in range(count)]
    player = game.players[player_index]
    lib = player.zones[Zone.LIBRARY]
    for obj in lib.get_all():
        lib.remove(obj)
    for c in cards:
        c.owner = player
        c.controller = player
        lib.add(c)
    return cards


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)
        assert CardType.SORCERY in TogetherAsOne(owner=None).card_types

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")

    def test_not_a_creature(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.CREATURE not in card.card_types
        assert not isinstance(card, Creature)


# ---------------------------------------------------------------------------
# Targeting — "target player" and "any target"
# ---------------------------------------------------------------------------


class TestTogetherAsOneTargeting:
    """get_targets() advertises two targets: a player and 'any target'."""

    def test_returns_two_target_requirements(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 2
        for r in reqs:
            assert isinstance(r, TargetRequirement)

    def test_first_requirement_accepts_players_only(self) -> None:
        """The 'target player' requirement accepts players and rejects creatures."""
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[0]
        player = game.players[0]
        creature = _bear()
        assert req.filter_fn(player) is True
        assert req.filter_fn(creature) is False

    def test_second_requirement_accepts_any_target(self) -> None:
        """The 'any target' requirement accepts both players and creatures."""
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[1]
        player = game.players[0]
        creature = _bear()
        assert req.filter_fn(player) is True
        assert req.filter_fn(creature) is True

    def test_any_target_rejects_noncreature_nonplayer(self) -> None:
        """A noncreature permanent (e.g. a plain artifact-ish object) is not
        a legal 'any target'."""
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[1]
        non_creature = Creature(name="Not a creature")
        non_creature.card_types = set()  # strip CREATURE so it isn't a legal target
        assert req.filter_fn(non_creature) is False


# ---------------------------------------------------------------------------
# Converge: X = number of colors of mana spent
# ---------------------------------------------------------------------------


class TestTogetherAsOneConvergeDraw:
    """The target player draws X cards, where X = colors spent."""

    def test_zero_colors_draws_nothing(self) -> None:
        """All-colorless payment ({6} paid with {C}) means X=0: no cards drawn."""
        game = create_game()
        p1 = game.players[0]
        _stock_library(game, 0, 5)
        before = len(p1.zones[Zone.HAND].get_all())

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = []  # no colors spent → X = 0
        spell.chosen_targets = [p1, p1]
        spell.on_resolve(game)

        assert len(p1.zones[Zone.HAND].get_all()) == before

    def test_two_colors_target_player_draws_two(self) -> None:
        """Two distinct colors spent → the targeted player draws 2 cards."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 1, 5)
        before = len(p2.zones[Zone.HAND].get_all())

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.WHITE, Color.BLUE]  # X = 2
        # Target player = opponent (p2); damage target irrelevant here.
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) - before == 2

    def test_five_colors_target_player_draws_five(self) -> None:
        """All five colors spent → the targeted player draws 5 cards."""
        game = create_game()
        p1 = game.players[0]
        _stock_library(game, 0, 7)
        before = len(p1.zones[Zone.HAND].get_all())

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [
            Color.WHITE,
            Color.BLUE,
            Color.BLACK,
            Color.RED,
            Color.GREEN,
        ]  # X = 5
        spell.chosen_targets = [p1, p1]
        spell.on_resolve(game)

        assert len(p1.zones[Zone.HAND].get_all()) - before == 5

    def test_draw_goes_to_chosen_player_not_controller(self) -> None:
        """When the target player is the opponent, the controller does NOT draw."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 0, 5)
        _stock_library(game, 1, 5)
        p1_before = len(p1.zones[Zone.HAND].get_all())
        p2_before = len(p2.zones[Zone.HAND].get_all())

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.RED, Color.GREEN]  # X = 2
        spell.chosen_targets = [p2, p1]  # target player = opponent
        spell.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) - p2_before == 2
        assert len(p1.zones[Zone.HAND].get_all()) == p1_before


class TestTogetherAsOneConvergeDamage:
    """The spell deals X damage to the chosen 'any target'."""

    def test_damage_to_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 0, 5)
        p2.life = 20

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.RED, Color.WHITE, Color.GREEN]  # X = 3
        spell.chosen_targets = [p1, p2]  # damage target = opponent player
        spell.on_resolve(game)

        assert p2.life == 17

    def test_damage_to_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 0, 5)
        bear = _bear()
        set_board_state(game, 1, battlefield=[bear])

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.BLUE, Color.BLACK]  # X = 2
        spell.chosen_targets = [p1, bear]  # damage target = creature
        spell.on_resolve(game)

        assert bear.damage_marked == 2

    def test_zero_colors_deals_no_damage(self) -> None:
        """X=0 → no damage is dealt to the target player."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 0, 5)
        p2.life = 20

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = []  # X = 0
        spell.chosen_targets = [p1, p2]
        spell.on_resolve(game)

        assert p2.life == 20


class TestTogetherAsOneConvergeLifeGain:
    """The controller gains X life."""

    def test_controller_gains_life_equal_to_colors(self) -> None:
        game = create_game()
        p1 = game.players[0]
        _stock_library(game, 0, 5)
        p1.life = 20

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.WHITE, Color.BLACK, Color.GREEN]  # X = 3
        spell.chosen_targets = [p1, p1]
        spell.on_resolve(game)

        assert p1.life == 23

    def test_life_gain_goes_to_controller_not_target_player(self) -> None:
        """'You gain X life' — life goes to the controller even when the
        target player (the one who draws) is the opponent."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 1, 5)
        p1.life = 20
        p2.life = 20

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.RED, Color.GREEN]  # X = 2
        spell.chosen_targets = [p2, p1]  # target player = opponent
        spell.on_resolve(game)

        assert p1.life == 22  # controller gains
        # Opponent's life unchanged by the life-gain clause (damage target
        # below is the controller, not the opponent).

    def test_zero_colors_no_life_gain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        _stock_library(game, 0, 5)
        p1.life = 20

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = []  # X = 0
        spell.chosen_targets = [p1, p1]
        spell.on_resolve(game)

        assert p1.life == 20


# ---------------------------------------------------------------------------
# All three clauses apply in a single resolution
# ---------------------------------------------------------------------------


class TestTogetherAsOneCombinedResolution:
    """A single resolution applies draw + damage + life gain together."""

    def test_all_three_effects_in_one_resolution(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 0, 5)  # controller draws
        bear = _bear(toughness=10)  # survives the damage so we can inspect it
        set_board_state(game, 1, battlefield=[bear])
        p1.life = 20
        hand_before = len(p1.zones[Zone.HAND].get_all())

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [
            Color.WHITE,
            Color.BLUE,
            Color.BLACK,
            Color.RED,
        ]  # X = 4
        # Target player = controller (draws), any target = opponent's bear.
        spell.chosen_targets = [p1, bear]
        spell.on_resolve(game)

        assert len(p1.zones[Zone.HAND].get_all()) - hand_before == 4  # drew X
        assert bear.damage_marked == 4  # dealt X damage
        assert p1.life == 24  # gained X life


# ---------------------------------------------------------------------------
# Robustness / no-op safety
# ---------------------------------------------------------------------------


class TestTogetherAsOneResolveSafety:
    """on_resolve must not raise when targets/colors are unset."""

    def test_no_colors_spent_attribute_is_noop(self) -> None:
        """If colors_spent was never set (X treated as 0), resolution is a
        safe no-op that does not raise."""
        game = create_game()
        p1 = game.players[0]
        _stock_library(game, 0, 5)
        p1.life = 20
        hand_before = len(p1.zones[Zone.HAND].get_all())

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.chosen_targets = [p1, p1]
        # colors_spent intentionally left unset.
        spell.on_resolve(game)

        assert p1.life == 20
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before

    def test_no_targets_does_not_raise(self) -> None:
        """With no chosen_targets, resolution must not raise (life gain may
        still apply since 'you gain X life' is untargeted)."""
        game = create_game()
        p1 = game.players[0]
        _stock_library(game, 0, 5)
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.WHITE]  # X = 1
        # chosen_targets intentionally unset.
        spell.on_resolve(game)  # must not raise


# ---------------------------------------------------------------------------
# End-to-end cast through the real pipeline (grounds converge wiring)
# ---------------------------------------------------------------------------


class TestTogetherAsOneEndToEnd:
    """Cast through engine.casting so converge reads real payment colors."""

    def test_cast_with_three_colors_applies_x_equals_three(self) -> None:
        """Pay {6} with W+U+B+3 colorless: 3 distinct colors → X = 3.

        Target player = controller (draws 3); any target = opponent (takes 3
        damage); controller gains 3 life.
        """
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 0, 5)
        p1.life = 20
        p2.life = 20
        hand_setup = TogetherAsOne(owner=None)
        set_board_state(
            game,
            0,
            hand=[hand_setup],
            mana={
                ManaType.WHITE: 1,
                ManaType.BLUE: 1,
                ManaType.BLACK: 1,
                ManaType.COLORLESS: 3,
            },
        )
        hand_before = len(p1.zones[Zone.HAND].get_all())

        # Targets: first the target player (controller), then 'any target'
        # (the opponent). cast_spell scripts them in get_targets() order.
        cast_spell(game, 0, "Together as One", targets=[p1, p2])

        # X = 3 distinct colors spent (W, U, B).
        assert len(p1.zones[Zone.HAND].get_all()) - (hand_before - 1) == 3
        assert p2.life == 17  # 3 damage to opponent
        assert p1.life == 23  # controller gains 3 life

    def test_cast_with_all_colorless_is_x_zero(self) -> None:
        """Pay {6} entirely with colorless mana: 0 colors → X = 0 (no effects)."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 0, 5)
        p1.life = 20
        p2.life = 20
        set_board_state(
            game,
            0,
            hand=[TogetherAsOne(owner=None)],
            mana={ManaType.COLORLESS: 6},
        )
        hand_before = len(p1.zones[Zone.HAND].get_all())

        cast_spell(game, 0, "Together as One", targets=[p1, p2])

        # No cards drawn beyond the cast removing the spell from hand.
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before - 1
        assert p2.life == 20  # no damage
        assert p1.life == 20  # no life gain

    def test_spell_goes_to_graveyard_after_resolution(self) -> None:
        """As a sorcery, it is placed in its owner's graveyard on resolution."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 0, 5)
        set_board_state(
            game,
            0,
            hand=[TogetherAsOne(owner=None)],
            mana={
                ManaType.WHITE: 1,
                ManaType.GREEN: 1,
                ManaType.COLORLESS: 4,
            },
        )

        cast_spell(game, 0, "Together as One", targets=[p1, p2])

        gy_names = [getattr(c, "name", "") for c in p1.zones[Zone.GRAVEYARD].get_all()]
        assert "Together as One" in gy_names
