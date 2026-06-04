"""Tests for SOS 1 — The Dawning Archaic (I/S cost reduction + attack recast)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import _resolve_top_of_stack, cast_spell, create_game, set_board_state


class _LifeGain(Instant):
    """A cheap instant that gains 5 life when it resolves."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Restore")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 5


def _inst(name: str) -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{2}"))


def _fire_attack(game: Any, archaic: Any) -> None:
    game.trigger_manager.fire_event(
        game, AttacksTriggeredEvent(creature=archaic, attacker=archaic)
    )
    _resolve_top_of_stack(game)


class TestArchaicProperties:
    def test_is_creature(self) -> None:
        assert isinstance(TheDawningArchaic(owner=None), Creature)

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_pt(self) -> None:
        c = TheDawningArchaic(owner=None)
        assert c.base_power == 7
        assert c.base_toughness == 7

    def test_legendary_avatar_reach(self) -> None:
        c = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in c.supertypes
        assert "Avatar" in c.subtypes
        assert Keyword.REACH in c.keywords


class TestArchaicCostReduction:
    def test_counts_instants_and_sorceries(self) -> None:
        game = create_game()
        p0, _ = game.players
        archaic = TheDawningArchaic(owner=p0, controller=p0)
        gy = [_inst("I1"), _inst("I2"), Sorcery(name="S1"), Creature(name="Bear")]
        set_board_state(game, 0, battlefield=[archaic], graveyard=gy)

        # Two instants + one sorcery count; the creature does not.
        assert archaic.cost_reduction(game) == 3

    def test_empty_graveyard_no_reduction(self) -> None:
        game = create_game()
        p0, _ = game.players
        archaic = TheDawningArchaic(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[])
        assert archaic.cost_reduction(game) == 0

    def test_reduced_cast_through_engine(self) -> None:
        game = create_game()
        p0, _ = game.players
        archaic = TheDawningArchaic(owner=p0, controller=p0)
        gy = [_inst("I1"), _inst("I2"), _inst("I3")]
        set_board_state(
            game,
            0,
            hand=[archaic],
            graveyard=gy,
            mana={ManaType.COLORLESS: 7},  # {10} - 3 I/S = {7}
        )

        cast_spell(game, 0, "The Dawning Archaic")

        assert game.get_battlefield(p0).contains(archaic)
        assert p0.mana_pool.total() == 0


class TestArchaicAttackRecast:
    def test_recasts_from_graveyard_and_exiles(self) -> None:
        game = create_game()
        p0, _ = game.players
        archaic = TheDawningArchaic(owner=p0, controller=p0)
        spell = _LifeGain(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell], life=20)
        archaic.register_triggers(game)

        p0._script.extend([True, spell])  # yes, then choose the spell
        _fire_attack(game, archaic)

        assert p0.life == 25  # the free-cast spell resolved
        assert p0.zones[Zone.EXILE].contains(spell)  # exiled, not in graveyard
        assert not game.get_graveyard(p0).contains(spell)

    def test_declined_keeps_spell_in_graveyard(self) -> None:
        game = create_game()
        p0, _ = game.players
        archaic = TheDawningArchaic(owner=p0, controller=p0)
        spell = _LifeGain(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell], life=20)
        archaic.register_triggers(game)

        p0._script.append(False)  # decline the "may"
        _fire_attack(game, archaic)

        assert p0.life == 20
        assert game.get_graveyard(p0).contains(spell)

    def test_no_instant_or_sorcery_does_nothing(self) -> None:
        game = create_game()
        p0, _ = game.players
        archaic = TheDawningArchaic(owner=p0, controller=p0)
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[archaic], graveyard=[creature], life=20)
        archaic.register_triggers(game)

        # No I/S available → trigger resolves without asking for a choice.
        _fire_attack(game, archaic)

        assert p0.life == 20
        assert game.get_graveyard(p0).contains(creature)
