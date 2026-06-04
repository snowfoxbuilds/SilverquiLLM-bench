"""Tests for SOS 4 — Together as One.

Together as One — {6} — Sorcery (Converge):

    Target player draws X cards, Together as One deals X damage to any
    target, and you gain X life, where X is the number of colors of mana
    spent to cast this spell.

X is driven by the Converge mechanic. The casting pipeline records the
distinct colors of mana spent as ``card.colors_spent`` (a list of
:class:`engine.types.Color`); the card's resolution reads ``len`` of that
list to determine X. These tests set ``colors_spent`` and ``chosen_targets``
directly — mirroring the FDN converge / targeting reference tests — so the
effect can be exercised in isolation without a full mana-payment harness.
"""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, Color, ManaCost, TargetRequirement, Zone
from test_utils import create_game


def _put_cards_in_library(game, player, count):
    """Stock *player*'s library with *count* vanilla cards so draws succeed.

    Returns the list of cards added (top of library is the last element).
    """
    cards = []
    for i in range(count):
        card = Creature(name=f"Filler {i}", base_power=1, base_toughness=1)
        card.owner = player
        card.controller = player
        game.get_library(player).add(card)
        cards.append(card)
    return cards


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")

    def test_not_a_creature(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.CREATURE not in card.card_types
        assert CardType.SORCERY in card.card_types


class TestTogetherAsOneTargeting:
    """get_targets() advertises a target player and an 'any target'."""

    def test_returns_two_target_requirements(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 2
        for req in reqs:
            assert isinstance(req, TargetRequirement)

    def test_player_target_accepts_player_rejects_creature(self) -> None:
        """First requirement = 'target player': accept players, reject creatures."""
        game = create_game()
        player_req = TogetherAsOne(owner=None).get_targets(game)[0]

        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}

        assert player_req.filter_fn(game.players[0]) is True
        assert player_req.filter_fn(creature) is False

    def test_any_target_accepts_player(self) -> None:
        """Second requirement = 'any target': accept a player."""
        game = create_game()
        any_req = TogetherAsOne(owner=None).get_targets(game)[1]
        assert any_req.filter_fn(game.players[0]) is True

    def test_any_target_accepts_creature(self) -> None:
        """Second requirement = 'any target': accept a creature."""
        game = create_game()
        any_req = TogetherAsOne(owner=None).get_targets(game)[1]

        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert any_req.filter_fn(creature) is True

    def test_any_target_rejects_noncreature_nonplayer(self) -> None:
        """'any target' must reject a non-creature permanent with no life."""
        game = create_game()
        any_req = TogetherAsOne(owner=None).get_targets(game)[1]

        from engine.card import Enchantment

        ench = Enchantment(name="Some Enchantment")
        assert any_req.filter_fn(ench) is False


class TestTogetherAsOneConvergeX:
    """X = number of colors of mana spent; reads len(colors_spent)."""

    def test_colors_spent_defaults_empty(self) -> None:
        """Before any payment, no colors have been spent (X would be 0)."""
        card = TogetherAsOne(owner=None)
        spent = getattr(card, "colors_spent", [])
        assert len(spent) == 0

    def test_two_colors_target_player_draws_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _put_cards_in_library(game, p2, 5)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = [Color.WHITE, Color.BLUE]
        # Target player (draws) = p2; any target (damage) = p1.
        card.chosen_targets = [p2, p1]

        before = len(game.get_hand(p2).get_all())
        card.on_resolve(game)
        after = len(game.get_hand(p2).get_all())
        assert after - before == 2

    def test_three_colors_deals_three_damage_to_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _put_cards_in_library(game, p1, 5)

        bear = Creature(name="Bear", owner=p2, controller=p2,
                        base_power=2, base_toughness=4)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(bear)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = [Color.WHITE, Color.BLUE, Color.RED]
        # Target player (draws) = p1; any target (damage) = bear.
        card.chosen_targets = [p1, bear]

        card.on_resolve(game)
        assert bear.damage_marked == 3

    def test_two_colors_deals_two_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _put_cards_in_library(game, p1, 5)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = [Color.BLACK, Color.GREEN]
        # Target player (draws) = p1; any target (damage) = p2.
        card.chosen_targets = [p1, p2]

        p2.life = 20
        card.on_resolve(game)
        assert p2.life == 18

    def test_controller_gains_x_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _put_cards_in_library(game, p2, 5)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = [Color.WHITE, Color.BLUE, Color.RED]
        card.chosen_targets = [p2, p2]

        p1.life = 20
        card.on_resolve(game)
        # Controller (p1) gains X = 3 life — NOT the target player.
        assert p1.life == 23

    def test_life_gain_goes_to_controller_not_target_player(self) -> None:
        """'you gain X life' refers to the caster, even when the draw target
        is a different player."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _put_cards_in_library(game, p2, 5)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = [Color.WHITE, Color.BLUE]
        # Draw target = p2; any target (damage) = p2 as well.
        card.chosen_targets = [p2, p2]

        p1.life = 20
        p2.life = 20
        card.on_resolve(game)
        # Controller (p1) gains X = 2 life — NOT the draw/target player.
        assert p1.life == 22
        # p2 took 2 damage from being the 'any target', not life gain.
        assert p2.life == 18


class TestTogetherAsOneZeroColors:
    """When no colored mana is spent, X = 0 and every clause is a no-op."""

    def test_zero_colors_draws_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _put_cards_in_library(game, p2, 5)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = []  # all generic / colorless payment
        card.chosen_targets = [p2, p1]

        before = len(game.get_hand(p2).get_all())
        card.on_resolve(game)
        after = len(game.get_hand(p2).get_all())
        assert after == before

    def test_zero_colors_deals_no_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = []
        card.chosen_targets = [p1, p2]

        p2.life = 20
        card.on_resolve(game)
        assert p2.life == 20

    def test_zero_colors_gains_no_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = []
        card.chosen_targets = [p2, p2]

        p1.life = 20
        card.on_resolve(game)
        assert p1.life == 20


class TestTogetherAsOneFiveColors:
    """A full five-color (WUBRG) payment makes X = 5 across all clauses."""

    def test_five_colors_full_effect(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _put_cards_in_library(game, p2, 10)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = [
            Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN,
        ]
        card.chosen_targets = [p2, p2]

        p1.life = 20
        p2.life = 20
        draw_before = len(game.get_hand(p2).get_all())
        card.on_resolve(game)

        # p2 draws 5.
        assert len(game.get_hand(p2).get_all()) - draw_before == 5
        # p2 takes 5 damage (any target).
        assert p2.life == 15
        # Controller gains 5 life.
        assert p1.life == 25


class TestTogetherAsOneResolutionRobustness:
    """Resolution should be safe when invoked without full setup."""

    def test_resolves_without_targets_is_noop(self) -> None:
        """With no chosen_targets, on_resolve must not raise."""
        game = create_game()
        p1 = game.players[0]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = [Color.WHITE]
        # chosen_targets unset.
        card.on_resolve(game)

    def test_resolves_without_colors_spent_is_noop(self) -> None:
        """With colors_spent unset (defaulting to empty), on_resolve must not
        raise and must produce no effect."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.chosen_targets = [p2, p2]
        p1.life = 20
        p2.life = 20
        card.on_resolve(game)
        assert p1.life == 20
        assert p2.life == 20
