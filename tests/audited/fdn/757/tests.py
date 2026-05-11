"""Audited tests for Vampire Nighthawk (FDN collector number 757) — flying + deathtouch + lifelink."""

from __future__ import annotations

import pytest

from card_impl import VampireNighthawk

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestVampireNighthawkProperties:
    def test_is_creature(self) -> None:
        card = VampireNighthawk(name="Vampire Nighthawk", owner=None)
        assert isinstance(card, Creature)

    def test_power(self) -> None:
        card = VampireNighthawk(name="Vampire Nighthawk", owner=None)
        assert card.power == 2

    def test_toughness(self) -> None:
        card = VampireNighthawk(name="Vampire Nighthawk", owner=None)
        assert card.toughness == 3

    def test_has_vampire_subtype(self) -> None:
        card = VampireNighthawk(name="Vampire Nighthawk", owner=None)
        assert "Vampire" in card.subtypes

    def test_has_shaman_subtype(self) -> None:
        card = VampireNighthawk(name="Vampire Nighthawk", owner=None)
        assert "Shaman" in card.subtypes


@pytest.mark.ability
class TestVampireNighthawkKeywords:
    def test_has_flying(self) -> None:
        card = VampireNighthawk(name="Vampire Nighthawk", owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_deathtouch(self) -> None:
        card = VampireNighthawk(name="Vampire Nighthawk", owner=None)
        assert Keyword.DEATHTOUCH in card.keywords

    def test_has_lifelink(self) -> None:
        card = VampireNighthawk(name="Vampire Nighthawk", owner=None)
        assert Keyword.LIFELINK in card.keywords

    def test_exact_keywords(self) -> None:
        card = VampireNighthawk(name="Vampire Nighthawk", owner=None)
        expected = Keyword.FLYING | Keyword.DEATHTOUCH | Keyword.LIFELINK
        assert card.keywords == expected


@pytest.mark.behavior
class TestVampireNighthawkBehavior:
    """Flying + deathtouch + lifelink behavior tests."""

    def test_flying_cannot_be_blocked_by_ground(self) -> None:
        """Ground creature cannot block Vampire Nighthawk."""
        from engine.combat import _can_block
        from engine.card import Creature

        nighthawk = VampireNighthawk(name="Vampire Nighthawk", owner=None)
        ground = Creature(name="Ground", owner=None)
        assert not _can_block(ground, nighthawk)

    def test_deathtouch_1_damage_is_lethal(self) -> None:
        """Deathtouch makes 1 damage lethal for assignment."""
        from engine.combat import _get_lethal_damage
        from engine.card import Creature

        nighthawk = VampireNighthawk(name="Vampire Nighthawk", owner=None)
        target = Creature(name="Big", owner=None, base_toughness=10)
        assert _get_lethal_damage(target, nighthawk) == 1

    def test_lifelink_gains_life_on_combat_damage(self) -> None:
        """Controller gains life equal to combat damage dealt."""
        from tests.test_utils import create_game, set_board_state, declare_attackers
        from engine.combat import combat_damage_step

        game = create_game()
        card = VampireNighthawk(name="Vampire Nighthawk", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        initial_life = game.players[0].life
        declare_attackers(game, ["Vampire Nighthawk"])
        combat_damage_step(game)
        assert game.players[0].life == initial_life + 2
