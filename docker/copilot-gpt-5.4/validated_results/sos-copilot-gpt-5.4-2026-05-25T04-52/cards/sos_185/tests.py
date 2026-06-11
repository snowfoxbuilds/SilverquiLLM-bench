"""Tests for SOS 185 — Elemental Mascot."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_185.card_impl import ElementalMascot
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CheapTestInstant(Instant):
    """Simple instant used to exercise Opus triggers."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Cheap Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class FiveManaTestSorcery(Sorcery):
    """Simple sorcery used to exercise the five-mana Opus threshold."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Five-Mana Test Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}"))
        super().__init__(**kwargs)


class TestElementalMascotProperties:
    """Static card data should match the SOS 185 spec."""

    def test_is_elemental_bird_with_flying_and_vigilance(self) -> None:
        card = ElementalMascot(owner=None)

        assert isinstance(card, Creature)
        assert "Elemental" in card.subtypes
        assert "Bird" in card.subtypes
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = ElementalMascot(owner=None)

        assert card.name == "Elemental Mascot"
        assert card.mana_cost == ManaCost.parse("{1}{U}{R}")
        assert card.base_power == 1
        assert card.base_toughness == 4


class TestElementalMascotOpus:
    """Elemental Mascot should pump itself and impulse draw off large spells."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ElementalMascot(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_an_instant_gives_plus_one_power_until_end_of_turn_without_exiling(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = ElementalMascot(owner=p1, controller=p1)
        spell = CheapTestInstant(owner=p1, controller=p1)
        top = CardImpl(name="Top Card", owner=p1, controller=p1)
        game.get_library(p1).add(top)

        set_board_state(game, 0, battlefield=[card], hand=[spell], mana={ManaType.BLUE: 1})
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        resolve_top(game)

        assert card.power == 2
        assert card.toughness == 4
        assert game.get_exile(p1).get_all() == []
        assert game.get_library(p1).contains(top)

    def test_granted_plus_one_power_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = ElementalMascot(owner=p1, controller=p1)
        spell = CheapTestInstant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[spell], mana={ManaType.BLUE: 1})
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)
        assert card.power == 2

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert card.power == 1
        assert card.toughness == 4

    def test_five_or_more_mana_spell_exiles_top_card_and_grants_controller_only_play_permission_until_end_of_next_turn(
        self,
    ) -> None:
        game = create_game()
        p1, p2 = game.players
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = ElementalMascot(owner=p1, controller=p1)
        spell = FiveManaTestSorcery(owner=p1, controller=p1)
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        top = CardImpl(name="Top Card", owner=p1, controller=p1)
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(top)

        set_board_state(game, 0, battlefield=[card], hand=[spell], mana={ManaType.BLUE: 5})
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        permissions = game.get_exile_play_permissions(player=p1)

        assert card.power == 2
        assert game.get_exile(p1).contains(top)
        assert not game.get_library(p1).contains(top)
        assert game.get_library(p1).contains(bottom)
        assert game.can_player_play_exiled_card(p1, top) is True
        assert game.can_player_play_exiled_card(p2, top) is False
        assert len(permissions) == 1
        assert permissions[0].card is top
        assert permissions[0].source is card

    def test_exiled_card_permission_expires_after_controllers_next_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = ElementalMascot(owner=p1, controller=p1)
        spell = FiveManaTestSorcery(owner=p1, controller=p1)
        top = CardImpl(name="Top Card", owner=p1, controller=p1)
        game.get_library(p1).add(top)

        set_board_state(game, 0, battlefield=[card], hand=[spell], mana={ManaType.BLUE: 5})
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert game.can_player_play_exiled_card(p1, top) is True

        for _ in range(12):
            game.advance_phase()
        assert game.can_player_play_exiled_card(p1, top) is True

        for _ in range(12):
            game.advance_phase()
        assert game.can_player_play_exiled_card(p1, top) is True

        for _ in range(12):
            game.advance_phase()
        assert game.can_player_play_exiled_card(p1, top) is False

    def test_casting_a_creature_spell_does_not_trigger_opus(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = ElementalMascot(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Practice Performer",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{U}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[creature_spell],
            mana={ManaType.BLUE: 2},
        )
        card.register_triggers(game)

        cast_spell_paid(game, p1, creature_spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is creature_spell
