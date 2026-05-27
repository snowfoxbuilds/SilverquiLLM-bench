"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Instant, Land, Sorcery
from engine.casting import resolve_top
from engine.types import CardType, Color, ManaCost, ManaType, Phase, Zone
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state


class TestImprovisationCapstoneProperties:
    """Static characteristics from the card spec."""

    def test_is_a_red_sorcery_lesson_named_improvisation_capstone(self) -> None:
        card = ImprovisationCapstone(owner=None)

        assert isinstance(card, Sorcery)
        assert card.name == "Improvisation Capstone"
        assert CardType.SORCERY in card.card_types
        assert "Lesson" in card.subtypes
        assert card.colors == {Color.RED}

    def test_mana_cost_matches_the_spec(self) -> None:
        assert ImprovisationCapstone(owner=None).mana_cost == ManaCost.parse("{5}{R}{R}")


class TestImprovisationCapstoneResolution:
    """Resolution contract for the spell's library-exile and free-cast effect."""

    @staticmethod
    def _auto_accept_choices(player) -> None:
        player.choose_yes_no = lambda _prompt: True
        player.choose = lambda options, _description: options[0] if options else None
        player.choose_card = lambda cards, _description: cards[0] if cards else None
        player.choose_target = lambda options, _requirement: options[0] if options else None

    def test_exiles_from_the_top_until_total_mana_value_is_four_or_greater(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bottom_card = Instant(name="Bottom Note", mana_cost=ManaCost.parse("{U}"))
        second_card = Instant(name="Second Note", mana_cost=ManaCost.parse("{1}{R}"))
        top_card = Instant(name="Top Note", mana_cost=ManaCost.parse("{1}{U}"))

        p1.zones[Zone.LIBRARY].add(bottom_card)
        p1.zones[Zone.LIBRARY].add(second_card)
        p1.zones[Zone.LIBRARY].add(top_card)
        p1.choose_yes_no = lambda _prompt: False

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.get_exile(p1).contains(top_card)
        assert game.get_exile(p1).contains(second_card)
        assert not game.get_exile(p1).contains(bottom_card)
        assert game.get_library(p1).contains(bottom_card)
        assert game.stack.is_empty()

    def test_may_cast_any_number_of_revealed_spells_without_paying_mana_costs(self) -> None:
        game = create_game()
        p1 = game.players[0]
        self._auto_accept_choices(p1)

        bottom_card = Instant(name="Bottom Card", mana_cost=ManaCost.parse("{U}"))
        lower_spell = Sorcery(name="Theory Burst", mana_cost=ManaCost.parse("{1}{R}"))
        middle_land = Land(name="Training Grounds")
        top_spell = Instant(name="Flash Note", mana_cost=ManaCost.parse("{1}{U}"))

        p1.zones[Zone.LIBRARY].add(bottom_card)
        p1.zones[Zone.LIBRARY].add(lower_spell)
        p1.zones[Zone.LIBRARY].add(middle_land)
        p1.zones[Zone.LIBRARY].add(top_spell)

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        stack_names = {obj.source.name for obj in game.stack.objects()}
        assert stack_names == {"Flash Note", "Theory Burst"}
        assert all(obj.controller is p1 for obj in game.stack.objects())
        assert game.get_exile(p1).contains(middle_land)
        assert not game.get_exile(p1).contains(top_spell)
        assert not game.get_exile(p1).contains(lower_spell)
        assert game.get_library(p1).contains(bottom_card)
        assert p1.mana_pool.total() == 0


class TestImprovisationCapstoneParadigm:
    """Paradigm should exile the original and recur from future first main phases."""

    @staticmethod
    def _auto_accept_choices(player) -> None:
        player.choose_yes_no = lambda _prompt: True
        player.choose = lambda options, _description: options[0] if options else None
        player.choose_card = lambda cards, _description: cards[0] if cards else None
        player.choose_target = lambda options, _requirement: options[0] if options else None

    def _cast_original(self):
        game = create_game()
        p1, p2 = game.players
        self._auto_accept_choices(p1)

        capstone = ImprovisationCapstone(owner=None)
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        cast_spell(game, 0, "Improvisation Capstone")
        return game, p1, p2, capstone

    def test_original_spell_is_exiled_after_it_resolves(self) -> None:
        game, p1, _p2, capstone = self._cast_original()

        assert game.get_exile(p1).contains(capstone)
        assert not game.get_graveyard(p1).contains(capstone)

    def test_paradigm_triggers_on_your_next_precombat_main_not_other_main_phases(self) -> None:
        game, p1, p2, capstone = self._cast_original()

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        assert game.stack.is_empty()

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p2
        assert game.stack.is_empty()

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p1
        assert len(game.stack.objects()) == 1

        resolve_top(game)

        assert len(game.stack.objects()) == 1
        copy_obj = game.stack.peek()
        assert copy_obj is not None
        assert copy_obj.is_spell is True
        assert copy_obj.source.name == "Improvisation Capstone"
        assert copy_obj.source is not capstone
        assert game.get_exile(p1).contains(capstone)

        resolve_top(game)

        assert game.stack.is_empty()
        assert game.get_exile(p1).contains(capstone)
        assert not game.get_graveyard(p1).contains(capstone)

    def test_paradigm_repeats_on_later_first_main_phases_without_duplicating(self) -> None:
        game, p1, _p2, _capstone = self._cast_original()

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert len(game.stack.objects()) == 1
        resolve_top(game)
        assert len(game.stack.objects()) == 1
        resolve_top(game)
        assert game.stack.is_empty()

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.stack.is_empty()

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert len(game.stack.objects()) == 1
        resolve_top(game)

        assert len(game.stack.objects()) == 1
        copy_obj = game.stack.peek()
        assert copy_obj is not None
        assert copy_obj.is_spell is True
        assert copy_obj.source.name == "Improvisation Capstone"
