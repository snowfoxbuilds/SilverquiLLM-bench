"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.casting import cast_spell, get_cost_reduction
from engine.card import Creature, Enchantment, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Supertype, Zone
from engine.zones import move_to_zone
from test_utils import create_game, set_board_state


def _put_onto_battlefield(game, player, permanent) -> None:
    player.zones[Zone.HAND].add(permanent)
    permanent.owner = player
    permanent.controller = player
    move_to_zone(game, permanent, Zone.HAND, Zone.BATTLEFIELD)


def _set_main_phase(game, active_player_index: int = 0) -> None:
    game.active_player_index = active_player_index
    game.priority_player_index = active_player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


class TestWitherbloomTheBalancerProperties:
    """Static characteristics should match the card spec."""

    def test_is_a_legendary_five_five_elder_dragon_with_flying_and_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes
        assert card.base_power == 5
        assert card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords


class TestWitherbloomTheBalancerSelfAffinity:
    """Witherbloom itself should have affinity for creatures."""

    def test_self_affinity_counts_only_creatures_you_control(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        your_creature_one = Creature(name="Pest 1", base_power=1, base_toughness=1)
        your_creature_two = Creature(name="Pest 2", base_power=1, base_toughness=1)
        your_noncreature = Enchantment(name="Campus Ritual")
        opposing_creature = Creature(name="Enemy Pest", base_power=1, base_toughness=1)

        set_board_state(
            game,
            0,
            battlefield=[your_creature_one, your_creature_two, your_noncreature],
        )
        set_board_state(game, 1, battlefield=[opposing_creature])

        assert get_cost_reduction(game, card, p1) == 2

    def test_self_affinity_is_clamped_by_generic_mana_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"Pest {index}", base_power=1, base_toughness=1)
            for index in range(8)
        ]

        set_board_state(game, 0, battlefield=creatures)

        assert get_cost_reduction(game, card, p1) == 6

    def test_casting_witherbloom_uses_its_self_affinity_discount(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"Pest {index}", owner=p1, controller=p1, base_power=1, base_toughness=1)
            for index in range(3)
        ]

        set_board_state(
            game,
            0,
            battlefield=creatures,
            hand=[card],
            mana={
                ManaType.COLORLESS: 3,
                ManaType.BLACK: 1,
                ManaType.GREEN: 1,
            },
        )
        _set_main_phase(game)

        cast_spell(game, p1, card)

        top = game.stack.peek()
        assert top is not None
        assert top.source is card
        assert card.mana_spent == 5
        assert p1.mana_pool.total() == 0


class TestWitherbloomTheBalancerGrantedAffinity:
    """Witherbloom should grant affinity for creatures to your instants and sorceries."""

    def test_your_instant_spell_gains_affinity_for_only_your_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        your_other_creature = Creature(name="Pest", base_power=1, base_toughness=1)
        opposing_creatures = [
            Creature(name=f"Enemy {index}", base_power=1, base_toughness=1)
            for index in range(3)
        ]
        spell = Instant(name="Balancing Lesson", mana_cost=ManaCost.parse("{4}{B}"))

        set_board_state(game, 0, battlefield=[your_other_creature])
        set_board_state(game, 1, battlefield=opposing_creatures)
        _put_onto_battlefield(game, p1, witherbloom)

        assert get_cost_reduction(game, spell, p1) == 2

    def test_your_sorcery_spell_also_gains_affinity_for_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        your_other_creatures = [
            Creature(name="Pest 1", base_power=1, base_toughness=1),
            Creature(name="Pest 2", base_power=1, base_toughness=1),
        ]
        spell = Sorcery(name="Necrotic Thesis", mana_cost=ManaCost.parse("{5}{G}"))

        set_board_state(game, 0, battlefield=your_other_creatures)
        _put_onto_battlefield(game, p1, witherbloom)

        assert get_cost_reduction(game, spell, p1) == 3

    def test_your_creature_spells_do_not_gain_affinity_from_witherbloom(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        your_other_creatures = [
            Creature(name="Pest 1", base_power=1, base_toughness=1),
            Creature(name="Pest 2", base_power=1, base_toughness=1),
        ]
        creature_spell = Creature(
            name="Ordinary Dragon",
            mana_cost=ManaCost.parse("{4}{G}"),
            base_power=4,
            base_toughness=4,
        )

        set_board_state(game, 0, battlefield=your_other_creatures)
        _put_onto_battlefield(game, p1, witherbloom)

        assert get_cost_reduction(game, creature_spell, p1) == 0

    def test_opponents_instant_spells_do_not_gain_affinity_from_witherbloom(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        your_other_creatures = [
            Creature(name="Pest 1", base_power=1, base_toughness=1),
            Creature(name="Pest 2", base_power=1, base_toughness=1),
        ]
        opposing_spell = Instant(name="Enemy Lecture", mana_cost=ManaCost.parse("{4}{B}"))

        set_board_state(game, 0, battlefield=your_other_creatures)
        _put_onto_battlefield(game, p1, witherbloom)

        assert get_cost_reduction(game, opposing_spell, p2) == 0

    def test_casting_an_instant_uses_witherblooms_granted_affinity_discount(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        your_other_creatures = [
            Creature(name="Pest 1", owner=p1, controller=p1, base_power=1, base_toughness=1),
            Creature(name="Pest 2", owner=p1, controller=p1, base_power=1, base_toughness=1),
        ]
        spell = Instant(
            name="Balancing Lesson",
            mana_cost=ManaCost.parse("{4}{B}"),
            owner=p1,
            controller=p1,
        )

        set_board_state(
            game,
            0,
            battlefield=your_other_creatures,
            hand=[spell],
            mana={
                ManaType.COLORLESS: 1,
                ManaType.BLACK: 1,
            },
        )
        _put_onto_battlefield(game, p1, witherbloom)
        _set_main_phase(game)

        cast_spell(game, p1, spell)

        top = game.stack.peek()
        assert top is not None
        assert top.source is spell
        assert spell.mana_spent == 2
        assert p1.mana_pool.total() == 0
