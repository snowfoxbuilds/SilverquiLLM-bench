"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import CardImpl, Creature, Sorcery
from engine.casting import cast_spell as engine_cast_spell
from engine.types import Color, ManaCost, ManaType, Phase, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")


class TestTogetherAsOneTargeting:
    """Together as One targets one player and one any-target target."""

    def test_returns_two_target_requirements(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert isinstance(reqs[0], TargetRequirement)
        assert isinstance(reqs[1], TargetRequirement)

    def test_first_target_requirement_accepts_players_only(self) -> None:
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[0]
        player = game.players[0]
        creature = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)

        assert req.filter_fn(player) is True
        assert req.filter_fn(creature) is False

    def test_second_target_requirement_accepts_any_target(self) -> None:
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[1]
        player = game.players[0]
        creature = Creature(name="Hill Giant", base_power=3, base_toughness=3)
        non_target = CardImpl(name="Trinket")

        assert req.filter_fn(player) is True
        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_target) is False


class TestTogetherAsOneResolution:
    """Converge should scale the spell's draw, damage, and life gain together."""

    @staticmethod
    def _load_library(player, cards: list[CardImpl]) -> None:
        library = player.zones[Zone.LIBRARY]
        for card in library.get_all():
            library.remove(card)
        for card in cards:
            card.owner = player
            card.controller = player
            library.add(card)

    def test_on_resolve_without_chosen_targets_is_a_noop(self) -> None:
        game = create_game()
        caster = game.players[0]
        spell = TogetherAsOne(owner=caster, controller=caster)
        spell.colors_spent = [Color.WHITE, Color.BLUE]
        before_life = caster.life

        spell.on_resolve(game)

        assert caster.life == before_life

    def test_resolution_draws_damages_and_gains_life_for_each_color_spent(self) -> None:
        game = create_game()
        caster = game.players[0]
        draw_target = game.players[1]
        bear = Creature(
            name="Grizzly Bears",
            owner=draw_target,
            controller=draw_target,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 1, battlefield=[bear])
        self._load_library(
            draw_target,
            [
                Sorcery(name="Draw One", mana_cost=ManaCost.parse("{1}")),
                Sorcery(name="Draw Two", mana_cost=ManaCost.parse("{1}")),
                Sorcery(name="Draw Three", mana_cost=ManaCost.parse("{1}")),
            ],
        )

        spell = TogetherAsOne(owner=caster, controller=caster)
        spell.colors_spent = [Color.WHITE, Color.BLUE, Color.RED]
        spell.chosen_targets = [draw_target, bear]

        before_hand = len(draw_target.zones[Zone.HAND].get_all())
        before_damage = bear.damage_marked
        before_life = caster.life

        spell.on_resolve(game)

        assert len(draw_target.zones[Zone.HAND].get_all()) == before_hand + 3
        assert bear.damage_marked == before_damage + 3
        assert caster.life == before_life + 3

    def test_casting_with_only_colorless_mana_makes_x_zero(self) -> None:
        game = create_game()
        caster = game.players[0]
        draw_target = game.players[1]
        spell = TogetherAsOne(owner=caster, controller=caster)
        self._load_library(
            draw_target,
            [
                Sorcery(name="Draw One", mana_cost=ManaCost.parse("{1}")),
                Sorcery(name="Draw Two", mana_cost=ManaCost.parse("{1}")),
            ],
        )
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.COLORLESS: 6},
        )

        before_hand = len(draw_target.zones[Zone.HAND].get_all())
        before_target_life = draw_target.life
        before_caster_life = caster.life

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        caster._script.append(draw_target)
        caster._script.append(draw_target)

        engine_cast_spell(game, caster, spell)
        game.stack.pop().on_resolve(game)

        assert len(draw_target.zones[Zone.HAND].get_all()) == before_hand
        assert draw_target.life == before_target_life
        assert caster.life == before_caster_life
        assert caster.zones[Zone.GRAVEYARD].contains(spell)

    def test_casting_tracks_distinct_colors_spent_for_all_three_effects(self) -> None:
        game = create_game()
        caster = game.players[0]
        draw_target = game.players[1]
        spell = TogetherAsOne(owner=caster, controller=caster)
        self._load_library(
            draw_target,
            [
                Sorcery(name="Draw One", mana_cost=ManaCost.parse("{1}")),
                Sorcery(name="Draw Two", mana_cost=ManaCost.parse("{1}")),
                Sorcery(name="Draw Three", mana_cost=ManaCost.parse("{1}")),
            ],
        )
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

        before_hand = len(draw_target.zones[Zone.HAND].get_all())
        before_target_life = draw_target.life
        before_caster_life = caster.life

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        caster._script.append(draw_target)
        caster._script.append(draw_target)

        engine_cast_spell(game, caster, spell)
        game.stack.pop().on_resolve(game)

        assert len(draw_target.zones[Zone.HAND].get_all()) == before_hand + 3
        assert draw_target.life == before_target_life - 3
        assert caster.life == before_caster_life + 3
        assert caster.zones[Zone.GRAVEYARD].contains(spell)
