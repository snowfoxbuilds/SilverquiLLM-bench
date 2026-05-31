"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.casting import CastingError, cast_spell as cast_spell_to_stack
from engine.card import Creature, Instant, Sorcery
from engine.types import Color, Keyword, ManaCost, ManaType, Phase, Supertype
from test_utils import cast_spell, create_game, set_board_state


def _creature(name: str, owner) -> Creature:
    return Creature(
        name=name,
        owner=owner,
        controller=owner,
        base_power=1,
        base_toughness=1,
    )


def _set_precombat_main(game, player_index: int = 0) -> None:
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


class _BalancingBurst(Instant):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Balancing Burst")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        super().__init__(**kwargs)
        self.was_resolved = False

    def on_resolve(self, game) -> None:
        self.was_resolved = True


class _BalancingRitual(Sorcery):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Balancing Ritual")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        super().__init__(**kwargs)
        self.was_resolved = False

    def on_resolve(self, game) -> None:
        self.was_resolved = True


class _BalancingBeast(Creature):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Balancing Beast")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)


class TestWitherbloomTheBalancerProperties:
    def test_is_a_legendary_elder_dragon_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Witherbloom, the Balancer"
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_has_black_green_cost_colors_flying_deathtouch_and_five_five_stats(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert card.colors == {Color.BLACK, Color.GREEN}
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert card.base_power == 5
        assert card.base_toughness == 5


class TestWitherbloomTheBalancerAffinity:
    def test_cost_reduction_counts_only_creatures_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        balancer = WitherbloomTheBalancer(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[_creature("Pest One", p1), _creature("Pest Two", p1)],
        )
        set_board_state(
            game,
            1,
            battlefield=[_creature("Opponent Pest", p2)],
        )

        assert balancer.cost_reduction(game) == 2

    def test_can_be_cast_for_only_black_and_green_when_you_control_six_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        balancer = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [_creature(f"Pest {index}", p1) for index in range(6)]

        set_board_state(
            game,
            0,
            battlefield=creatures,
            hand=[balancer],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1},
        )

        cast_spell(game, 0, "Witherbloom, the Balancer")

        assert game.get_battlefield(p1).contains(balancer)


class TestWitherbloomTheBalancerGrantedAffinity:
    def test_grants_affinity_to_your_instant_spells_and_counts_witherbloom_itself(self) -> None:
        game = create_game()
        p1 = game.players[0]
        balancer = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = _BalancingBurst(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[balancer, _creature("Campus Pest", p1)],
            hand=[spell],
            mana={ManaType.GREEN: 1},
        )
        balancer.register_triggers(game)

        cast_spell(game, 0, "Balancing Burst")

        assert spell.was_resolved is True
        assert game.get_graveyard(p1).contains(spell)

    def test_grants_affinity_to_your_sorcery_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        balancer = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = _BalancingRitual(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[
                balancer,
                _creature("Pest One", p1),
                _creature("Pest Two", p1),
            ],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )
        balancer.register_triggers(game)

        cast_spell(game, 0, "Balancing Ritual")

        assert spell.was_resolved is True
        assert game.get_graveyard(p1).contains(spell)

    def test_reduces_instants_but_not_creature_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        balancer = WitherbloomTheBalancer(owner=p1, controller=p1)
        instant_spell = _BalancingBurst(owner=p1, controller=p1)
        creature_spell = _BalancingBeast(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[
                balancer,
                _creature("Pest One", p1),
                _creature("Pest Two", p1),
            ],
            hand=[instant_spell, creature_spell],
            mana={ManaType.GREEN: 2},
        )
        balancer.register_triggers(game)

        cast_spell(game, 0, "Balancing Burst")

        _set_precombat_main(game, 0)
        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell_to_stack(game, p1, creature_spell)

        assert instant_spell.was_resolved is True
        assert game.get_graveyard(p1).contains(instant_spell)
        assert game.get_hand(p1).contains(creature_spell)

    def test_reduces_only_your_instants_and_sorceries(self) -> None:
        game = create_game()
        p1, p2 = game.players
        balancer = WitherbloomTheBalancer(owner=p1, controller=p1)
        your_spell = _BalancingBurst(owner=p1, controller=p1)
        opponent_spell = _BalancingBurst(owner=p2, controller=p2)

        set_board_state(
            game,
            0,
            battlefield=[
                balancer,
                _creature("Pest One", p1),
                _creature("Pest Two", p1),
            ],
            hand=[your_spell],
            mana={ManaType.GREEN: 1},
        )
        set_board_state(
            game,
            1,
            hand=[opponent_spell],
            mana={ManaType.GREEN: 1},
        )
        balancer.register_triggers(game)

        cast_spell(game, 0, "Balancing Burst")

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell_to_stack(game, p2, opponent_spell)

        assert your_spell.was_resolved is True
        assert game.get_graveyard(p1).contains(your_spell)
        assert game.get_hand(p2).contains(opponent_spell)
