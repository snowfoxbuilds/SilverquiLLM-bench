"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Instant, Land
from engine.types import CardType, ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


class _NoOpInstant(Instant):
    """Trivial {0} instant used to fire SpellCastTriggeredEvent."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ping")
        kwargs.setdefault("mana_cost", ManaCost.parse("{0}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        pass


class TestGreatHallProperties:
    def test_is_land(self) -> None:
        assert isinstance(GreatHallOfTheBiblioplex(owner=None), Land)

    def test_name(self) -> None:
        assert (
            GreatHallOfTheBiblioplex(owner=None).name
            == "Great Hall of the Biblioplex"
        )

    def test_no_mana_cost(self) -> None:
        assert GreatHallOfTheBiblioplex(owner=None).mana_cost == ManaCost()

    def test_card_type_land(self) -> None:
        c = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in c.card_types

    def test_not_initially_creature(self) -> None:
        c = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.CREATURE not in c.card_types


class TestGreatHallManaAbilities:
    def test_colorless_mana(self) -> None:
        game = create_game()
        p0, _ = game.players
        hall = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[hall])

        ability = hall.get_mana_abilities()[0]
        assert ability.cost(game, hall) is True
        ability.mana_produced(game)

        assert p0.mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped
        # A tapped land cannot pay the tap cost again.
        assert ability.cost(game, hall) is False

    def test_any_color_mana_pays_life(self) -> None:
        game = create_game(scripts=([ManaType.RED], []))
        p0, _ = game.players
        hall = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[hall], life=20)

        ability = hall.get_mana_abilities()[1]
        assert ability.cost(game, hall) is True
        ability.mana_produced(game)

        assert p0.mana_pool.get(ManaType.RED) == 1
        assert p0.life == 19
        assert hall.is_tapped


class TestGreatHallAnimate:
    def test_animate_becomes_creature(self) -> None:
        game = create_game()
        p0, _ = game.players
        hall = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})

        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is True
        ability.effect(game)

        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types  # still a land
        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4
        # Mana was spent.
        assert p0.mana_pool.total() == 0

    def test_animate_pump_on_instant_cast(self) -> None:
        game = create_game()
        p0, _ = game.players
        hall = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
            hand=[_NoOpInstant(owner=p0, controller=p0)],
        )

        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is True
        ability.effect(game)

        cast_spell(game, 0, "Ping")
        game.effect_manager.apply_all(game)

        assert hall.power == 3  # +1/+0 until end of turn
        assert hall.toughness == 4
        # Recalculation is idempotent.
        game.effect_manager.apply_all(game)
        assert hall.power == 3

    def test_animate_only_if_not_already_creature(self) -> None:
        # Animating a second time is a no-op, so only one pump trigger is
        # registered: casting one instant grants exactly +1/+0, not +2/+0.
        game = create_game()
        p0, _ = game.players
        hall = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 10},
            hand=[_NoOpInstant(owner=p0, controller=p0)],
        )

        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is True
        ability.effect(game)
        # Second activation: still a creature → no-op.
        ability.effect(game)

        cast_spell(game, 0, "Ping")
        game.effect_manager.apply_all(game)

        assert hall.power == 3
