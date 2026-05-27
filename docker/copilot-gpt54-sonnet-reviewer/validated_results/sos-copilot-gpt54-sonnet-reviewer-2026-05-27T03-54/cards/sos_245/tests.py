"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.types import CardType, Color, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import cast_spell, create_game, set_board_state


class TestLectureNotes(Instant):
    """Simple instant used to verify granted affinity-for-creatures casting."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Lecture Notes")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{B}"))
        super().__init__(**kwargs)


class TestFinalProject(Sorcery):
    """Simple sorcery used to verify granted affinity-for-creatures casting."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Final Project")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        super().__init__(**kwargs)


def _student(name: str) -> Creature:
    """Return a simple vanilla creature for battlefield-counting setups."""
    return Creature(name=name, base_power=1, base_toughness=1)


def _register_witherbloom(game, witherbloom: WitherbloomTheBalancer) -> None:
    """Register Witherbloom's battlefield abilities and apply static effects."""
    witherbloom.register_triggers(game)
    witherbloom.register_replacement_effects(game)
    game.effect_manager.apply_all(game)


class TestWitherbloomTheBalancerProperties:
    """Static characteristics should match the SOS 245 spec."""

    def test_is_a_legendary_elder_dragon_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_has_expected_cost_colors_keywords_affinity_text_and_stats(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert card.colors == {Color.BLACK, Color.GREEN}
        assert card.color_identity == {Color.BLACK, Color.GREEN}
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert card.non_evergreen_keywords == {"Affinity"}
        assert card.base_power == 5
        assert card.base_toughness == 5
        assert card.rules_text == (
            "Affinity for creatures (This spell costs {1} less to cast for each "
            "creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures."
        )


class TestWitherbloomTheBalancerAffinity:
    """Affinity for creatures should reduce generic mana based on your creatures."""

    def test_self_affinity_counts_only_your_creatures(self) -> None:
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = WitherbloomTheBalancer(owner=player, controller=player)

        your_creatures = [_student("Pupil A"), _student("Pupil B"), _student("Pupil C")]
        opponent_creatures = [_student("Enemy A"), _student("Enemy B")]
        your_noncreature = Instant(name="Not a Creature")
        your_noncreature.card_types = {CardType.INSTANT}

        set_board_state(game, 0, battlefield=[*your_creatures, your_noncreature])
        set_board_state(game, 1, battlefield=opponent_creatures)

        assert get_cost_reduction(game, card, player) == 3

    def test_six_creatures_reduce_witherbloom_to_colored_mana_only(self) -> None:
        game = create_game()
        witherbloom = WitherbloomTheBalancer(owner=None)
        creatures = [_student(f"Student {n}") for n in range(6)]

        set_board_state(
            game,
            0,
            battlefield=creatures,
            hand=[witherbloom],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1},
        )

        cast_spell(game, 0, "Witherbloom, the Balancer")

        assert game.get_battlefield(game.players[0]).contains(witherbloom)
        assert game.players[0].mana_pool.total() == 0


class TestWitherbloomTheBalancerGrantedAffinity:
    """Witherbloom should grant affinity for creatures to your instants and sorceries."""

    def test_your_instants_and_sorceries_get_creature_count_cost_reduction(self) -> None:
        game = create_game()
        player = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=player, controller=player)
        your_instant = TestLectureNotes(owner=player, controller=player)
        your_sorcery = TestFinalProject(owner=player, controller=player)
        other_creatures = [_student("Researcher"), _student("Assistant")]

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, *other_creatures],
            hand=[your_instant, your_sorcery],
        )

        _register_witherbloom(game, witherbloom)

        assert get_cost_reduction(game, your_instant, player) == 3
        assert get_cost_reduction(game, your_sorcery, player) == 3

    def test_creature_spells_and_opponents_spells_do_not_gain_affinity(self) -> None:
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        witherbloom = WitherbloomTheBalancer(owner=player, controller=player)
        your_creature_spell = Creature(
            name="Campus Troll",
            owner=player,
            controller=player,
            mana_cost=ManaCost.parse("{3}{G}"),
            base_power=3,
            base_toughness=3,
        )
        opponent_instant = TestLectureNotes(owner=opponent, controller=opponent)

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, _student("Helper"), _student("Scribe")],
            hand=[your_creature_spell],
        )
        set_board_state(
            game,
            1,
            battlefield=[_student("Enemy Helper")],
            hand=[opponent_instant],
        )

        _register_witherbloom(game, witherbloom)

        assert get_cost_reduction(game, your_creature_spell, player) == 0
        assert get_cost_reduction(game, opponent_instant, opponent) == 0

    def test_granted_affinity_can_reduce_generic_cost_to_zero_but_not_colored_mana(self) -> None:
        game = create_game()
        player = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=player, controller=player)
        spell = TestLectureNotes(owner=player, controller=player)
        helpers = [_student("Helper A"), _student("Helper B"), _student("Helper C")]

        set_board_state(
            game,
            0,
            battlefield=[witherbloom, *helpers],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )

        _register_witherbloom(game, witherbloom)
        cast_spell(game, 0, "Lecture Notes")

        assert game.get_graveyard(player).contains(spell)
        assert not game.get_hand(player).contains(spell)
        assert player.mana_pool.total() == 0
        assert spell.total_mana_spent_to_cast == 1
        assert spell.colors_spent == [Color.BLACK]
        assert not game.players[0].zones[Zone.BATTLEFIELD].contains(spell)
