"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import CardImpl, Creature, Planeswalker, Sorcery
from engine.types import CardType, Color, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


ORACLE_TEXT = (
    "Converge — Target player draws X cards, Together as One deals X damage "
    "to any target, and you gain X life, where X is the number of colors of "
    "mana spent to cast this spell."
)


def _library_card(name: str) -> CardImpl:
    return CardImpl(name=name)


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")

    def test_rules_text(self) -> None:
        assert TogetherAsOne(owner=None).rules_text == ORACLE_TEXT


class TestTogetherAsOneTargeting:
    """The spell needs one player target and one damage target."""

    def test_get_targets_returns_player_target_then_any_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        reqs = TogetherAsOne(owner=p1, controller=p1).get_targets(game)

        bear = Creature(name="Target Bear", base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        relic = CardImpl(name="Test Relic")

        assert len(reqs) == 2
        assert isinstance(reqs[0], TargetRequirement)
        assert isinstance(reqs[1], TargetRequirement)

        player_req, damage_req = reqs
        assert player_req.filter_fn(p1) is True
        assert player_req.filter_fn(p2) is True
        assert player_req.filter_fn(bear) is False

        assert damage_req.filter_fn(p2) is True
        assert damage_req.filter_fn(bear) is True
        assert damage_req.filter_fn(relic) is False

    def test_any_target_filter_accepts_planeswalker(self) -> None:
        game = create_game()
        damage_req = TogetherAsOne(owner=None).get_targets(game)[1]
        walker = Planeswalker(name="Test Walker", starting_loyalty=4)

        assert damage_req.filter_fn(walker) is True


class TestTogetherAsOneResolution:
    """Converge count X should drive all three effects on resolution."""

    def test_two_colors_draws_two_deals_two_to_creature_and_gains_two(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        ogre = Creature(
            name="Hill Ogre",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        ogre.card_types = {CardType.CREATURE}

        set_board_state(game, 1, battlefield=[ogre])
        p2.zones[Zone.LIBRARY].add(_library_card("Card A"))
        p2.zones[Zone.LIBRARY].add(_library_card("Card B"))
        p2.zones[Zone.LIBRARY].add(_library_card("Card C"))

        spell.colors_spent = [Color.WHITE, Color.BLUE]
        spell.chosen_targets = [p2, ogre]
        spell.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) == 2
        assert len(p2.zones[Zone.LIBRARY].get_all()) == 1
        assert ogre.damage_marked == 2
        assert p1.life == 22

    def test_three_colors_can_damage_a_player_while_you_draw_and_gain_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)

        p1.zones[Zone.LIBRARY].add(_library_card("Draw 1"))
        p1.zones[Zone.LIBRARY].add(_library_card("Draw 2"))
        p1.zones[Zone.LIBRARY].add(_library_card("Draw 3"))

        spell.colors_spent = [Color.WHITE, Color.BLUE, Color.BLACK]
        spell.chosen_targets = [p1, p2]
        spell.on_resolve(game)

        assert len(p1.zones[Zone.HAND].get_all()) == 3
        assert p1.life == 23
        assert p2.life == 17

    def test_two_colors_can_damage_a_planeswalker_and_reduce_loyalty(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        walker = Planeswalker(
            name="Stoic Adept",
            owner=p2,
            controller=p2,
            starting_loyalty=5,
        )

        set_board_state(game, 1, battlefield=[walker])
        p2.zones[Zone.LIBRARY].add(_library_card("Card A"))
        p2.zones[Zone.LIBRARY].add(_library_card("Card B"))
        p2.zones[Zone.LIBRARY].add(_library_card("Card C"))

        spell.colors_spent = [Color.WHITE, Color.BLUE]
        spell.chosen_targets = [p2, walker]
        spell.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) == 2
        assert len(p2.zones[Zone.LIBRARY].get_all()) == 1
        assert walker.loyalty == 3
        assert p1.life == 22

    def test_cast_spell_can_target_planeswalker_and_lethal_damage_moves_it_to_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        walker = Planeswalker(
            name="Fading Spark",
            owner=p2,
            controller=p2,
            starting_loyalty=3,
        )

        set_board_state(
            game,
            0,
            hand=[spell],
            mana={
                ManaType.WHITE: 2,
                ManaType.BLUE: 2,
                ManaType.BLACK: 2,
            },
        )
        set_board_state(game, 1, battlefield=[walker])
        p2.zones[Zone.LIBRARY].add(_library_card("Draw A"))
        p2.zones[Zone.LIBRARY].add(_library_card("Draw B"))
        p2.zones[Zone.LIBRARY].add(_library_card("Draw C"))

        cast_spell(game, 0, "Together as One", targets=[p2, walker])

        assert len(p2.zones[Zone.HAND].get_all()) == 3
        assert len(p2.zones[Zone.LIBRARY].get_all()) == 0
        assert walker.loyalty == 0
        assert p1.life == 23
        assert not p2.zones[Zone.BATTLEFIELD].contains(walker)
        assert p2.zones[Zone.GRAVEYARD].contains(walker)

    def test_colorless_cast_makes_x_zero(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        bear = Creature(
            name="Runeclaw Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}

        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.COLORLESS: 6},
        )
        set_board_state(game, 1, battlefield=[bear])
        p2.zones[Zone.LIBRARY].add(_library_card("Only Card"))

        cast_spell(game, 0, "Together as One", targets=[p2, bear])

        assert len(p2.zones[Zone.HAND].get_all()) == 0
        assert len(p2.zones[Zone.LIBRARY].get_all()) == 1
        assert bear.damage_marked == 0
        assert p1.life == 20
        assert p1.zones[Zone.GRAVEYARD].contains(spell)

    def test_cast_spell_uses_distinct_colors_spent_for_x(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        drake = Creature(
            name="Wind Drake",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        drake.card_types = {CardType.CREATURE}

        set_board_state(
            game,
            0,
            hand=[spell],
            mana={
                ManaType.WHITE: 2,
                ManaType.BLUE: 2,
                ManaType.BLACK: 2,
            },
        )
        set_board_state(game, 1, battlefield=[drake])
        p2.zones[Zone.LIBRARY].add(_library_card("Draw A"))
        p2.zones[Zone.LIBRARY].add(_library_card("Draw B"))
        p2.zones[Zone.LIBRARY].add(_library_card("Draw C"))

        cast_spell(game, 0, "Together as One", targets=[p2, drake])

        assert len(p2.zones[Zone.HAND].get_all()) == 3
        assert len(p2.zones[Zone.LIBRARY].get_all()) == 0
        assert drake.damage_marked == 3
        assert p1.life == 23
        assert p1.zones[Zone.GRAVEYARD].contains(spell)
