"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Artifact, Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.types import Color, Keyword, ManaCost, ManaType, Supertype
from test_utils import TestSetupError as SetupError, cast_spell, create_game, set_board_state


class TrainingCreature(Creature):
    """Simple creature used to exercise creature-counting affinity."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Training Creature")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)


class TrainingInstant(Instant):
    """Simple instant used to exercise granted affinity."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Training Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        super().__init__(**kwargs)
        self.times_resolved = 0

    def on_resolve(self, game) -> None:
        self.times_resolved += 1


class DoubleBlueInstant(Instant):
    """Instant with a colored requirement that affinity must not remove."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Double Blue Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        super().__init__(**kwargs)


class TrainingSorcery(Sorcery):
    """Simple sorcery used to exercise granted affinity casting."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Training Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        super().__init__(**kwargs)
        self.times_resolved = 0

    def on_resolve(self, game) -> None:
        self.times_resolved += 1


class TrainingCreatureSpell(Creature):
    """Creature spell used to verify the grant excludes non-instants/sorceries."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Training Creature Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)


class TestWitherbloomTheBalancerProperties:
    """Static card data should match the SOS 245 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(WitherbloomTheBalancer(owner=None), Creature)

    def test_name_and_mana_cost(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_is_legendary_elder_dragon(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_power_toughness_and_colors(self) -> None:
        card = WitherbloomTheBalancer(owner=None)

        assert card.base_power == 5
        assert card.base_toughness == 5
        assert card.colors == {Color.BLACK, Color.GREEN}

    def test_has_flying_and_deathtouch(self) -> None:
        keywords = WitherbloomTheBalancer(owner=None).keywords

        assert Keyword.FLYING in keywords
        assert Keyword.DEATHTOUCH in keywords


class TestWitherbloomTheBalancerSelfAffinity:
    """Witherbloom itself should have affinity for creatures."""

    def test_affinity_counts_only_creatures_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        ally_a = TrainingCreature(name="Ally A", owner=p1, controller=p1)
        ally_b = TrainingCreature(name="Ally B", owner=p1, controller=p1)
        artifact = Artifact(name="Training Relic", owner=p1, controller=p1)
        opposing_creature = TrainingCreature(name="Opponent Creature", owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[ally_a, ally_b, artifact], hand=[card])
        set_board_state(game, 1, battlefield=[opposing_creature])

        assert get_cost_reduction(game, card, p1) == 2

    def test_affinity_is_clamped_to_printed_generic_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            TrainingCreature(name=f"Creature {index}", owner=p1, controller=p1)
            for index in range(8)
        ]

        set_board_state(game, 0, battlefield=creatures, hand=[card])

        assert get_cost_reduction(game, card, p1) == 6

    def test_can_be_cast_for_reduced_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            TrainingCreature(name="Creature A", owner=p1, controller=p1),
            TrainingCreature(name="Creature B", owner=p1, controller=p1),
            TrainingCreature(name="Creature C", owner=p1, controller=p1),
        ]

        set_board_state(
            game,
            0,
            battlefield=creatures,
            hand=[card],
            mana={
                ManaType.BLACK: 1,
                ManaType.GREEN: 1,
                ManaType.COLORLESS: 3,
            },
        )

        cast_spell(game, 0, "Witherbloom, the Balancer")

        assert game.get_battlefield(p1).contains(card)

    def test_affinity_does_not_remove_colored_requirements(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            TrainingCreature(name=f"Creature {index}", owner=p1, controller=p1)
            for index in range(6)
        ]

        set_board_state(
            game,
            0,
            battlefield=creatures,
            hand=[card],
            mana={
                ManaType.BLACK: 1,
                ManaType.COLORLESS: 1,
            },
        )

        assert get_cost_reduction(game, card, p1) == 6

        with pytest.raises(SetupError):
            cast_spell(game, 0, "Witherbloom, the Balancer")


class TestWitherbloomTheBalancerGrantedAffinity:
    """Witherbloom should grant affinity for creatures to your instants and sorceries."""

    def test_grants_affinity_for_creatures_to_your_instants(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = TrainingInstant(owner=p1, controller=p1)
        creatures = [
            witherbloom,
            TrainingCreature(name="Creature A", owner=p1, controller=p1),
            TrainingCreature(name="Creature B", owner=p1, controller=p1),
        ]

        set_board_state(game, 0, battlefield=creatures, hand=[spell])

        assert get_cost_reduction(game, spell, p1) == 3

    def test_grants_affinity_for_creatures_to_your_sorceries_and_allows_reduced_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = TrainingSorcery(owner=p1, controller=p1)
        creatures = [
            witherbloom,
            TrainingCreature(name="Creature A", owner=p1, controller=p1),
            TrainingCreature(name="Creature B", owner=p1, controller=p1),
        ]

        set_board_state(
            game,
            0,
            battlefield=creatures,
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )

        cast_spell(game, 0, "Training Sorcery")

        assert spell.times_resolved == 1
        assert game.get_graveyard(p1).contains(spell)

    def test_granted_affinity_does_not_remove_colored_requirements(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = DoubleBlueInstant(owner=p1, controller=p1)
        creatures = [witherbloom] + [
            TrainingCreature(name=f"Creature {index}", owner=p1, controller=p1)
            for index in range(4)
        ]

        set_board_state(
            game,
            0,
            battlefield=creatures,
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )

        assert get_cost_reduction(game, spell, p1) == 1

        with pytest.raises(SetupError):
            cast_spell(game, 0, "Double Blue Instant")

    def test_granted_affinity_applies_only_to_instants_and_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        instant_spell = TrainingInstant(owner=p1, controller=p1)
        creature_spell = TrainingCreatureSpell(owner=p1, controller=p1)
        creatures = [
            witherbloom,
            TrainingCreature(name="Creature A", owner=p1, controller=p1),
            TrainingCreature(name="Creature B", owner=p1, controller=p1),
        ]

        set_board_state(game, 0, battlefield=creatures, hand=[instant_spell, creature_spell])

        assert get_cost_reduction(game, instant_spell, p1) == 3
        assert get_cost_reduction(game, creature_spell, p1) == 0

    def test_granted_affinity_does_not_apply_to_opponents_spells(self) -> None:
        game = create_game()
        p1, p2 = game.players
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        allied_spell = TrainingInstant(owner=p1, controller=p1)
        opposing_spell = TrainingInstant(owner=p2, controller=p2)
        allied_creatures = [
            witherbloom,
            TrainingCreature(name="Creature A", owner=p1, controller=p1),
            TrainingCreature(name="Creature B", owner=p1, controller=p1),
        ]

        set_board_state(game, 0, battlefield=allied_creatures, hand=[allied_spell])
        set_board_state(game, 1, hand=[opposing_spell])

        assert get_cost_reduction(game, allied_spell, p1) == 3
        assert get_cost_reduction(game, opposing_spell, p2) == 0
