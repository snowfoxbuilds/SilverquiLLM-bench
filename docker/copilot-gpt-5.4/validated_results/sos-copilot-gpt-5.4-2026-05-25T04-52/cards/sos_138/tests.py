"""Tests for SOS 138 — Aberrant Manawurm."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_138.card_impl import AberrantManawurm
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import cast_spell, create_game, set_board_state


class TwoManaTestInstant(Instant):
    """Two-mana instant used to exercise Aberrant Manawurm."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Two-Mana Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        super().__init__(**kwargs)


class FourManaTestSorcery(Sorcery):
    """Four-mana sorcery used to exercise Aberrant Manawurm."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Four-Mana Test Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        super().__init__(**kwargs)


class TwoManaTestCreature(Creature):
    """Two-mana creature spell used to confirm only instants and sorceries trigger."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Two-Mana Test Creature")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)


class TestAberrantManawurmProperties:
    """Static card data should match the SOS 138 spec."""

    def test_is_wurm_creature_with_trample(self) -> None:
        card = AberrantManawurm(owner=None)
        assert isinstance(card, Creature)
        assert "Wurm" in card.subtypes
        assert Keyword.TRAMPLE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = AberrantManawurm(owner=None)
        assert card.name == "Aberrant Manawurm"
        assert card.mana_cost == ManaCost.parse("{3}{G}")
        assert card.base_power == 2
        assert card.base_toughness == 5


class TestAberrantManawurmTrigger:
    """Aberrant Manawurm should get temporary power from instant and sorcery spells."""

    def test_casting_a_two_mana_instant_gives_plus_two_power_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = TwoManaTestInstant(owner=p1, controller=p1)
        card = AberrantManawurm(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )
        card.register_triggers(game)

        cast_spell(game, 0, "Two-Mana Test Instant")

        assert card.power == 4
        assert card.toughness == 5
        assert game.get_graveyard(p1).contains(spell)

    def test_casting_a_four_mana_sorcery_gives_plus_four_power_and_the_bonus_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = FourManaTestSorcery(owner=p1, controller=p1)
        card = AberrantManawurm(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 3},
        )
        card.register_triggers(game)

        cast_spell(game, 0, "Four-Mana Test Sorcery")

        assert card.power == 6
        assert card.toughness == 5

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert card.power == 2
        assert card.toughness == 5

    def test_casting_a_creature_spell_does_not_trigger_the_power_bonus(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = TwoManaTestCreature(owner=p1, controller=p1)
        card = AberrantManawurm(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )
        card.register_triggers(game)

        cast_spell(game, 0, "Two-Mana Test Creature")

        assert card.power == 2
        assert card.toughness == 5
