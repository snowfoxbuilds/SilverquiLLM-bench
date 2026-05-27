"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.casting import cast_spell as cast_without_resolution
from engine.types import CardType, ManaCost, ManaType, Phase, TargetRequirement, Zone
from engine.zones import move_to_zone
from test_utils import cast_spell, create_game, set_board_state


class TestTogetherAsOneProperties:
    """Static characteristics from the card spec."""

    def test_is_a_sorcery_with_the_printed_mana_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)
        assert CardType.SORCERY in card.card_types
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")


class TestTogetherAsOneTargeting:
    """Together as One has one player target and one independent damage target."""

    def test_get_targets_requires_a_player_and_an_any_target_choice(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne(owner=p1, controller=p1)

        reqs = card.get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert all(isinstance(req, TargetRequirement) for req in reqs)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[1].zone == Zone.BATTLEFIELD

        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        non_target = Sorcery(name="Not a legal target")

        assert reqs[0].filter_fn(p1) is True
        assert reqs[0].filter_fn(p2) is True
        assert reqs[0].filter_fn(creature) is False

        assert reqs[1].filter_fn(p1) is True
        assert reqs[1].filter_fn(creature) is True
        assert reqs[1].filter_fn(non_target) is False


class TestTogetherAsOneResolution:
    """Converge sets one X value for the card's three linked effects."""

    @staticmethod
    def _seed_library(game, player, count: int, prefix: str) -> None:
        library = game.get_library(player)
        for obj in library.get_all():
            library.remove(obj)
        for i in range(count):
            card = Sorcery(name=f"{prefix} {i}", mana_cost=ManaCost.parse("{1}"))
            card.owner = player
            card.controller = player
            library.add(card)

    @staticmethod
    def _target_creature() -> Creature:
        creature = Creature(name="Target Bear", base_power=4, base_toughness=4)
        creature.card_types = {CardType.CREATURE}
        return creature

    @staticmethod
    def _configured_spell() -> TogetherAsOne:
        spell = TogetherAsOne(owner=None)
        spell.name = "Together as One"
        spell.mana_cost = ManaCost.parse("{6}")
        spell.card_types = {CardType.SORCERY}
        return spell

    def test_single_color_payment_makes_x_one_for_draw_damage_and_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        self._seed_library(game, p2, 2, "Opponent Card")

        spell = self._configured_spell()
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.GREEN: 6},
            life=20,
        )
        set_board_state(game, 1, life=20)

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(game.get_hand(p2).get_all()) == 1
        assert p2.life == 19
        assert p1.life == 21

    def test_three_distinct_colors_make_x_three_even_though_six_mana_was_paid(self) -> None:
        game = create_game()
        p1, p2 = game.players
        self._seed_library(game, p1, 4, "Draw Card")
        creature = self._target_creature()

        spell = self._configured_spell()
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={
                ManaType.WHITE: 1,
                ManaType.BLUE: 1,
                ManaType.BLACK: 1,
                ManaType.COLORLESS: 3,
            },
            life=20,
        )
        set_board_state(game, 1, battlefield=[creature])

        cast_spell(game, 0, "Together as One", targets=[p1, creature])

        assert len(game.get_hand(p1).get_all()) == 3
        assert creature.damage_marked == 3
        assert p1.life == 23

    def test_all_colorless_payment_makes_x_zero(self) -> None:
        game = create_game()
        p1, p2 = game.players
        self._seed_library(game, p2, 2, "Opponent Card")

        spell = self._configured_spell()
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.COLORLESS: 6},
            life=20,
        )
        set_board_state(game, 1, life=20)

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(game.get_hand(p2).get_all()) == 0
        assert p2.life == 20
        assert p1.life == 20

    def test_if_damage_target_is_gone_the_draw_and_life_effects_still_happen(self) -> None:
        game = create_game()
        p1, p2 = game.players
        self._seed_library(game, p2, 3, "Opponent Card")
        creature = self._target_creature()
        spell = self._configured_spell()

        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.COLORLESS: 4},
            life=20,
        )
        set_board_state(game, 1, battlefield=[creature], life=20)

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        choices = iter([p2, creature])
        p1.choose_target = lambda _options, _requirement: next(choices)

        cast_without_resolution(game, p1, spell)
        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.GRAVEYARD)

        stack_obj = game.stack.pop()
        stack_obj.on_resolve(game)

        assert len(game.get_hand(p2).get_all()) == 2
        assert p2.life == 20
        assert p1.life == 22
        assert creature.damage_marked == 0
