"""Tests for SOS 4 — Together as One.

Together as One is a Sorcery with Converge:
  "Target player draws X cards, Together as One deals X damage to any target,
   and you gain X life, where X is the number of colors of mana spent to cast
   this spell."

Test strategy:
- Static properties: name, mana_cost, card_type must match spec.
- converge_colors attribute defaults to 0.
- cost_reduction() returns 0 (no cost discount).
- on_resolve with converge_colors=0: no draws, no damage, no life gain.
- on_resolve with converge_colors=2: target player draws 2, deals 2 damage, controller gains 2.
- on_resolve with converge_colors=5: all effects at X=5.
- chosen_targets[0] = player who draws, chosen_targets[1] = damage target.
- Damage can target a creature or a player.
- Controller (not target player) gains the life.
"""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_library_cards(n: int) -> list[Creature]:
    """Create n vanilla 1/1 creatures to use as library filler."""
    return [Creature(name=f"Filler_{i}", base_power=1, base_toughness=1) for i in range(n)]


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------

class TestTogetherAsOneProperties:
    """Card data must match the SOS 4 spec."""

    def test_is_sorcery_subclass(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")

    def test_has_sorcery_card_type(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.SORCERY in card.card_types


# ---------------------------------------------------------------------------
# Converge attribute & cost_reduction
# ---------------------------------------------------------------------------

class TestTogetherAsOneConverge:
    """converge_colors attribute and cost_reduction baseline."""

    def test_converge_colors_defaults_to_zero(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.converge_colors == 0

    def test_cost_reduction_returns_zero(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        assert card.cost_reduction(game) == 0


# ---------------------------------------------------------------------------
# Resolution with converge_colors = 0 (X = 0 → no effects)
# ---------------------------------------------------------------------------

class TestTogetherAsOneResolveXZero:
    """When converge_colors=0, all three effects are null (X=0)."""

    def test_x_zero_target_player_draws_no_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Give p2 a library so draws could happen
        fillers = _make_library_cards(5)
        for c in fillers:
            p2.zones[Zone.LIBRARY].add(c)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.converge_colors = 0
        # chosen_targets[0] = draw target (p2), chosen_targets[1] = damage target (p2)
        spell.chosen_targets = [p2, p2]
        hand_before = len(p2.zones[Zone.HAND].get_all())
        spell.on_resolve(game)
        hand_after = len(p2.zones[Zone.HAND].get_all())
        assert hand_after == hand_before

    def test_x_zero_no_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.converge_colors = 0
        spell.chosen_targets = [p2, p2]
        life_before = p2.life
        spell.on_resolve(game)
        assert p2.life == life_before

    def test_x_zero_no_damage_to_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target_creature = Creature(name="TargetBear", base_power=2, base_toughness=2,
                                   owner=p2, controller=p2)
        game.get_battlefield(p2).add(target_creature)
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.converge_colors = 0
        spell.chosen_targets = [p2, target_creature]
        spell.on_resolve(game)
        assert target_creature.damage_marked == 0

    def test_x_zero_controller_gains_no_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.converge_colors = 0
        spell.chosen_targets = [p2, p2]
        life_before = p1.life
        spell.on_resolve(game)
        assert p1.life == life_before


# ---------------------------------------------------------------------------
# Resolution with converge_colors = 2 (X = 2)
# ---------------------------------------------------------------------------

class TestTogetherAsOneResolveXTwo:
    """With converge_colors=2 all three effects scale to X=2."""

    def test_x_two_target_player_draws_two_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        fillers = _make_library_cards(5)
        for c in fillers:
            p2.zones[Zone.LIBRARY].add(c)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.converge_colors = 2
        spell.chosen_targets = [p2, p2]
        hand_before = len(p2.zones[Zone.HAND].get_all())
        spell.on_resolve(game)
        hand_after = len(p2.zones[Zone.HAND].get_all())
        assert hand_after - hand_before == 2

    def test_x_two_deals_two_damage_to_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target_creature = Creature(name="TargetBear", base_power=3, base_toughness=3,
                                   owner=p2, controller=p2)
        game.get_battlefield(p2).add(target_creature)
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.converge_colors = 2
        spell.chosen_targets = [p2, target_creature]
        spell.on_resolve(game)
        assert target_creature.damage_marked == 2

    def test_x_two_controller_gains_two_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        life_before = p1.life
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.converge_colors = 2
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)
        assert p1.life == life_before + 2


# ---------------------------------------------------------------------------
# Resolution with converge_colors = 5 (X = 5, maximum)
# ---------------------------------------------------------------------------

class TestTogetherAsOneResolveXFive:
    """With converge_colors=5 (all five WUBRG colors) all effects scale to X=5."""

    def test_x_five_target_player_draws_five_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        fillers = _make_library_cards(10)
        for c in fillers:
            p2.zones[Zone.LIBRARY].add(c)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.converge_colors = 5
        spell.chosen_targets = [p2, p2]
        hand_before = len(p2.zones[Zone.HAND].get_all())
        spell.on_resolve(game)
        hand_after = len(p2.zones[Zone.HAND].get_all())
        assert hand_after - hand_before == 5

    def test_x_five_deals_five_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        life_before = p2.life
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.converge_colors = 5
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)
        assert p2.life == life_before - 5

    def test_x_five_controller_gains_five_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        life_before = p1.life
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.converge_colors = 5
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)
        assert p1.life == life_before + 5


# ---------------------------------------------------------------------------
# Target semantics
# ---------------------------------------------------------------------------

class TestTogetherAsOneTargeting:
    """chosen_targets[0] = draw player, chosen_targets[1] = damage target."""

    def test_draw_target_is_first_chosen_target_not_controller(self) -> None:
        """Player 2 (not controller) is the draw target; only p2's hand should grow."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        fillers = _make_library_cards(5)
        for c in fillers:
            p2.zones[Zone.LIBRARY].add(c)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.converge_colors = 3
        # p2 draws, p2 also receives damage
        spell.chosen_targets = [p2, p2]
        p1_hand_before = len(p1.zones[Zone.HAND].get_all())
        spell.on_resolve(game)
        p1_hand_after = len(p1.zones[Zone.HAND].get_all())
        # Controller (p1) draws NOTHING; only target player draws
        assert p1_hand_after == p1_hand_before

    def test_damage_target_is_second_chosen_target(self) -> None:
        """Only chosen_targets[1] receives damage — not chosen_targets[0]."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Put a creature on p2's side as the damage target
        target_creature = Creature(name="DamageTarget", base_power=4, base_toughness=4,
                                   owner=p2, controller=p2)
        game.get_battlefield(p2).add(target_creature)
        # p2 is chosen_targets[0] (draws), target_creature is chosen_targets[1] (damage)
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.converge_colors = 2
        spell.chosen_targets = [p2, target_creature]
        life_p2_before = p2.life
        spell.on_resolve(game)
        # Player p2 should NOT have taken life loss (damage went to creature)
        assert p2.life == life_p2_before
        # Creature receives the damage
        assert target_creature.damage_marked == 2

    def test_controller_gains_life_not_draw_target(self) -> None:
        """Life gain accrues to the controller, not the draw target."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        fillers = _make_library_cards(5)
        for c in fillers:
            p2.zones[Zone.LIBRARY].add(c)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.converge_colors = 3
        spell.chosen_targets = [p2, p2]
        p1_life_before = p1.life
        p2_life_before = p2.life
        spell.on_resolve(game)
        # p1 (controller) gains life
        assert p1.life == p1_life_before + 3
        # p2 lost 3 life from damage, not gained
        assert p2.life == p2_life_before - 3
