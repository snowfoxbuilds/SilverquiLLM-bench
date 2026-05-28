"""Tests for SOS 4 — Together as One.

Together as One is a {6} sorcery with Converge:
  Target player draws X cards, Together as One deals X damage to any target,
  and you gain X life, where X is the number of colors of mana spent to cast
  this spell.

Tests bypass the casting pipeline by setting ``colors_spent`` and
``chosen_targets`` directly on the card, following the Wardens of the
Cycle (FDN 205) converge-test pattern.
"""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from test_utils import create_game


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"

    def test_mana_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}")

    def test_has_sorcery_card_type(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.SORCERY in card.card_types


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------


class TestTogetherAsOneTargeting:
    """get_targets() should advertise two target requirements:
    one for 'target player' and one for 'any target'."""

    def test_returns_two_target_requirements(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 2

    def test_each_requirement_is_target_requirement(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        reqs = card.get_targets(game)
        for req in reqs:
            assert isinstance(req, TargetRequirement)

    def test_first_target_accepts_player(self) -> None:
        """The first target requirement should accept a player object."""
        game = create_game()
        card = TogetherAsOne(owner=None)
        reqs = card.get_targets(game)
        player_req = reqs[0]
        # Players have a 'life' attribute
        assert player_req.filter_fn(game.players[0]) is True

    def test_second_target_accepts_player(self) -> None:
        """'Any target' should accept a player."""
        game = create_game()
        card = TogetherAsOne(owner=None)
        reqs = card.get_targets(game)
        any_req = reqs[1]
        assert any_req.filter_fn(game.players[0]) is True

    def test_second_target_accepts_creature(self) -> None:
        """'Any target' should accept a creature on the battlefield."""
        game = create_game()
        card = TogetherAsOne(owner=None)
        reqs = card.get_targets(game)
        any_req = reqs[1]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        assert any_req.filter_fn(bear) is True


# ---------------------------------------------------------------------------
# Converge — colors_spent attribute
# ---------------------------------------------------------------------------


class TestTogetherAsOneConverge:
    """The card should track colors_spent for the Converge mechanic.

    Following the FDN 205 (Wardens of the Cycle) pattern, the card should
    have a colors_spent attribute that defaults to 0 (or an empty list)
    and is used to determine X.
    """

    def test_colors_spent_attribute_exists(self) -> None:
        """Card should have a colors_spent attribute after construction."""
        card = TogetherAsOne(owner=None)
        assert hasattr(card, "colors_spent")


# ---------------------------------------------------------------------------
# Resolution — draw X cards for target player
# ---------------------------------------------------------------------------


class TestTogetherAsOneDrawCards:
    """Target player draws X cards where X = colors of mana spent."""

    def test_target_player_draws_x_cards(self) -> None:
        """With 3 colors spent, target player should draw 3 cards."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put some cards in the target player's library so draws succeed
        for i in range(5):
            dummy = Creature(name=f"Dummy{i}", base_power=1, base_toughness=1)
            dummy.owner = p2
            p2.zones[Zone.LIBRARY].add(dummy)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3

        # Target player is p2, damage target is also p2
        card.chosen_targets = [p2, p2]

        hand_before = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        hand_after = len(p2.zones[Zone.HAND].get_all())

        assert hand_after - hand_before == 3

    def test_caster_can_target_self_for_draw(self) -> None:
        """The caster can target themselves as the 'target player'."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        for i in range(5):
            dummy = Creature(name=f"Dummy{i}", base_power=1, base_toughness=1)
            dummy.owner = p1
            p1.zones[Zone.LIBRARY].add(dummy)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2

        # Target player is p1 (self), damage target is p2
        card.chosen_targets = [p1, p2]

        hand_before = len(p1.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        hand_after = len(p1.zones[Zone.HAND].get_all())

        assert hand_after - hand_before == 2


# ---------------------------------------------------------------------------
# Resolution — deal X damage to any target
# ---------------------------------------------------------------------------


class TestTogetherAsOneDamage:
    """Together as One deals X damage to any target."""

    def test_deals_x_damage_to_target_player(self) -> None:
        """With 3 colors spent, deal 3 damage to target player."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p1, p2]

        life_before = p2.life
        card.on_resolve(game)

        assert p2.life == life_before - 3

    def test_deals_x_damage_to_creature(self) -> None:
        """With 2 colors spent, deal 2 damage to a target creature."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        bear = Creature(
            name="Grizzly Bears",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p2).add(bear)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        card.chosen_targets = [p1, bear]

        damage_before = bear.damage_marked
        card.on_resolve(game)

        assert bear.damage_marked == damage_before + 2

    def test_five_colors_deals_five_damage(self) -> None:
        """With 5 colors spent (WUBRG), deal 5 damage."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        card.chosen_targets = [p2, p2]

        life_before = p2.life
        card.on_resolve(game)

        assert p2.life == life_before - 5


# ---------------------------------------------------------------------------
# Resolution — controller gains X life
# ---------------------------------------------------------------------------


class TestTogetherAsOneLifeGain:
    """The caster (controller) gains X life."""

    def test_controller_gains_x_life(self) -> None:
        """With 3 colors spent, controller gains 3 life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p2, p2]

        life_before = p1.life
        card.on_resolve(game)

        assert p1.life == life_before + 3

    def test_five_colors_gains_five_life(self) -> None:
        """With 5 colors spent, controller gains 5 life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        card.chosen_targets = [p2, p2]

        life_before = p1.life
        card.on_resolve(game)

        assert p1.life == life_before + 5


# ---------------------------------------------------------------------------
# Resolution — all three effects together
# ---------------------------------------------------------------------------


class TestTogetherAsOneFullResolution:
    """All three effects (draw, damage, life gain) should occur together."""

    def test_all_three_effects_with_three_colors(self) -> None:
        """With 3 colors spent: target draws 3, deal 3 damage, gain 3 life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put cards in p2's library for drawing
        for i in range(5):
            dummy = Creature(name=f"Dummy{i}", base_power=1, base_toughness=1)
            dummy.owner = p2
            p2.zones[Zone.LIBRARY].add(dummy)

        bear = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=4,
            base_toughness=4,
        )
        game.get_battlefield(p2).add(bear)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        # Target player = p2 (draws), damage target = bear
        card.chosen_targets = [p2, bear]

        p1_life_before = p1.life
        p2_hand_before = len(p2.zones[Zone.HAND].get_all())
        bear_damage_before = bear.damage_marked

        card.on_resolve(game)

        # p2 draws 3 cards
        assert len(p2.zones[Zone.HAND].get_all()) - p2_hand_before == 3
        # bear takes 3 damage
        assert bear.damage_marked - bear_damage_before == 3
        # p1 (controller) gains 3 life
        assert p1.life - p1_life_before == 3


# ---------------------------------------------------------------------------
# Edge cases — zero colors spent
# ---------------------------------------------------------------------------


class TestTogetherAsOneZeroColors:
    """When X = 0 (no colored mana spent), all effects do nothing."""

    def test_zero_colors_no_cards_drawn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p2, p2]

        hand_before = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        hand_after = len(p2.zones[Zone.HAND].get_all())

        assert hand_after == hand_before

    def test_zero_colors_no_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p2, p2]

        life_before = p2.life
        card.on_resolve(game)

        assert p2.life == life_before

    def test_zero_colors_no_life_gain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p2, p2]

        life_before = p1.life
        card.on_resolve(game)

        assert p1.life == life_before


# ---------------------------------------------------------------------------
# Edge case — no chosen targets
# ---------------------------------------------------------------------------


class TestTogetherAsOneNoTargets:
    """When chosen_targets is empty or not set, on_resolve should not raise."""

    def test_no_chosen_targets_does_not_raise(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        # No chosen_targets set — should not crash
        card.on_resolve(game)

    def test_empty_chosen_targets_does_not_raise(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = []
        card.on_resolve(game)


# ---------------------------------------------------------------------------
# Converge with list of Color objects (engine pipeline format)
# ---------------------------------------------------------------------------


class TestTogetherAsOneConvergeWithColorList:
    """The casting pipeline sets colors_spent as a list of Color enums.
    The card should handle both int and list formats for X calculation."""

    def test_colors_spent_as_list_determines_x(self) -> None:
        """When colors_spent is a list of Color objects from the engine,
        X should equal the length of distinct colors."""
        from engine.types import Color

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        # Simulate the engine setting colors_spent as a list of Color enums
        card.colors_spent = [Color.WHITE, Color.BLUE, Color.RED]
        card.chosen_targets = [p2, p2]

        life_before = p2.life
        card.on_resolve(game)

        # X should be 3 (three distinct colors)
        assert p2.life == life_before - 3

    def test_colors_spent_as_list_gains_life(self) -> None:
        """Life gain should also work with list-based colors_spent."""
        from engine.types import Color

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = [Color.BLACK, Color.GREEN]
        card.chosen_targets = [p2, p2]

        life_before = p1.life
        card.on_resolve(game)

        assert p1.life == life_before + 2
